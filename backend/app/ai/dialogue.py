"""Rule-based dialogue manager for the patient intake chat (no generative model).

Each turn it looks at EVERYTHING the patient has said so far, extracts symptoms with the existing
extractor, asks the most useful missing question (one at a time, never the same twice), and when it
has enough (or the question budget is spent) explains a PRELIMINARY department suggestion from the
existing routing rules. Urgent symptoms short-circuit the questions and give emergency guidance.

Safety: it never diagnoses, prescribes or reassures. The department is always provisional and
staff confirm it. The chosen display/speaking language is never used as a symptom or feature.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.ai import text_processing
from app.ai.dialogue_text import (
    CLAUSE_BREAKS,
    DEPARTMENT_NAMES,
    NATIVE_GLOSSARY,
    NEGATION_AFTER,
    NEGATION_BEFORE,
    NO_WORDS,
    REGION_WORDS,
    SEVERITY_NATIVE,
    SIDE_WORDS,
    SYMPTOM_NAMES,
    TEMPLATES,
)
from app.ai.lexicon import term_for_phrase

DIALOGUE_ENGINE = "dialogue-v1"

# Reported terms that always get emergency guidance instead of more questions.
RED_FLAG_TERMS = {"chest pain", "breathing difficulty", "fainting"}
PAIN_LIKE = {"stomach pain", "chest pain", "headache", "back pain", "knee pain", "joint pain", "neck pain",
             "ear pain", "toothache", "body pain", "pain (location not stated)", "burning urination"}


# ---------------------------------------------------------------- native-script glossary

def _norm_native(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = re.sub("[​‌‍‎‏]", "", s)
    s = s.replace("ي", "ی").replace("ك", "ک").replace("ە", "ہ")
    return re.sub(r"\s+", " ", s)


_NUM_WORDS = {
    "hi": {"एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7,
           "आठ": 8, "नौ": 9, "दस": 10},
    "ur": {"ایک": 1, "دو": 2, "تین": 3, "چار": 4, "پانچ": 5, "چھ": 6, "سات": 7, "آٹھ": 8, "نو": 9, "دس": 10},
}
_UNITS = {
    "hi": {"दिन": "days", "हफ्ते": "weeks", "हफ़्ते": "weeks", "सप्ताह": "weeks", "घंटे": "hours",
           "महीने": "months"},
    "ur": {"دن": "days", "ہفتے": "weeks", "گھنٹے": "hours", "مہینے": "months"},
}
_SINCE_YESTERDAY = {"hi": "कल से", "ur": "کل سے"}


def _duration_phrase(t: str, lang: str) -> str | None:
    if _SINCE_YESTERDAY[lang] in t:
        return "since yesterday"
    nums = "|".join(["[0-9]+", *map(re.escape, _NUM_WORDS[lang])])
    units = "|".join(map(re.escape, _UNITS[lang]))
    m = re.search(rf"({nums})\s*({units})\s*(?:से|سے)", t)
    if not m:
        return None
    n = int(m.group(1)) if m.group(1).isdigit() else _NUM_WORDS[lang][m.group(1)]
    return f"for {n} {_UNITS[lang][m.group(2)]}"


@dataclass
class GlossHit:
    term: str
    negated: bool


def _clause_bounds(t: str, start: int, end: int) -> tuple[int, int]:
    left = max([t.rfind(b, 0, start) + len(b) for b in CLAUSE_BREAKS if t.rfind(b, 0, start) != -1] or [0])
    rights = [t.find(b, end) for b in CLAUSE_BREAKS if t.find(b, end) != -1]
    return left, (min(rights) if rights else len(t))


def native_gloss(text: str, lang: str) -> tuple[str, list[GlossHit]]:
    """Short English sentences ("I have fever.") for symptoms found by literal Hindi/Urdu phrases.

    Used only as input to the English extractor and classifier. It is NOT shown as a translation.
    """
    if lang not in ("hi", "ur"):
        return "", []
    t = _norm_native(text)
    found: list[tuple[int, int, str]] = []
    for term, (_en, hi, ur) in NATIVE_GLOSSARY.items():
        for phrase in (hi if lang == "hi" else ur):
            p, i = _norm_native(phrase), 0
            while (i := t.find(p, i)) != -1:
                found.append((i, i + len(p), term))
                i += 1
    found.sort(key=lambda c: (-(c[1] - c[0]), c[0]))  # longest phrase wins an overlap
    chosen: list[tuple[int, int, str]] = []
    for s, e, term in found:
        if all(e <= cs or s >= ce for cs, ce, _ in chosen):
            chosen.append((s, e, term))
    chosen.sort()
    hits: list[GlossHit] = []
    for s, e, term in chosen:
        cs, ce = _clause_bounds(t, s, e)
        after, before = t[e:ce], t[cs:s]
        negated = any(c in after[:28] for c in NEGATION_AFTER[lang]) or any(
            c in before[-16:] for c in NEGATION_BEFORE[lang])
        if not any(h.term == term and h.negated == negated for h in hits):
            hits.append(GlossHit(term, negated))
    duration = _duration_phrase(t, lang)
    sentences, used_duration = [], False
    for h in hits:
        en = NATIVE_GLOSSARY[h.term][0]
        if h.negated:
            sentences.append(f"I do not have {en}.")
        elif duration and not used_duration:
            sentences.append(f"I have {en} {duration}.")
            used_duration = True
        else:
            sentences.append(f"I have {en}.")
    return " ".join(sentences), hits


def merge_analysis_text(translation: str | None, gloss: str, hits: list[GlossHit]) -> str:
    """English text used for analysis: the translation, plus glossary sentences for symptoms the
    translation did not contain (so a mistranslated medical word does not hide a symptom)."""
    base = (translation or "").strip()
    if not hits:
        return base
    if not base:
        return gloss
    seen = {m.term for m in text_processing.extract(base).mentions}
    extra = [s for s, h in zip(_per_hit_sentences(gloss), hits) if h.term not in seen]
    return (base + " " + " ".join(extra)).strip() if extra else base


def _per_hit_sentences(gloss: str) -> list[str]:
    return [s.strip() + "." for s in gloss.split(".") if s.strip()]


# ---------------------------------------------------------------- answers to questions

def _contains_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def is_no(text: str, lang: str) -> bool:
    t = _norm_native(text).strip().strip(".!?।۔").lower()
    return len(t) <= 25 and any(t == w or t.startswith(w + " ") for w in NO_WORDS["en"] + NO_WORDS.get(lang, []))


def parse_answer(slot: str | None, en_text: str, native_text: str, lang: str) -> dict:
    """Pull structured details out of a reply to a question. Always keeps the patient's own words."""
    details: dict = {}
    if slot is None:
        return details
    en = (en_text or "").lower()
    nat = _norm_native(native_text or "")
    if slot in ("abdomen", "pain_location"):
        loc = {}
        if re.search(r"\b(upper|top)\b", en) or _contains_any(nat, REGION_WORDS["upper"]):
            loc["region"] = "upper"
        if re.search(r"\b(lower|bottom|below)\b", en) or _contains_any(nat, REGION_WORDS["lower"]):
            loc["region"] = "lower"
        if re.search(r"\b(middle|center|centre|navel|belly button|around)\b", en) or _contains_any(nat, REGION_WORDS["middle"]):
            loc.setdefault("region", "middle")
        if re.search(r"\bright\b", en) or _contains_any(nat, SIDE_WORDS["right"]):
            loc["side"] = "right"
        elif re.search(r"\bleft\b", en) or _contains_any(nat, SIDE_WORDS["left"]):
            loc["side"] = "left"
        loc["said"] = (native_text or en_text or "").strip()[:200]
        details["location"] = loc
    elif slot == "severity":
        for level, words in (("severe", ["severe", "unbearable", "very bad", "terrible", "worst", "intense", "extreme"]),
                             ("moderate", ["moderate", "medium"]), ("mild", ["mild", "slight", "little"])):
            if any(re.search(rf"\b{re.escape(w)}\b", en) for w in words) or _contains_any(nat, SEVERITY_NATIVE[level]):
                details["severity"] = level
                break
        details["severity_said"] = (native_text or en_text or "").strip()[:200]
    elif slot == "duration":
        details["duration_said"] = (native_text or en_text or "").strip()[:200]
    elif slot in ("associated", "medicines"):
        if is_no(native_text or en_text or "", lang):
            details[f"{slot}_none"] = True
    return details


# ---------------------------------------------------------------- the turn

@dataclass
class Turn:
    text: str
    meta: dict


def _name(term: str, lang: str) -> str:
    return term if lang == "en" else SYMPTOM_NAMES[lang].get(term, term)


def _dept_name(code: str | None, name: str | None, lang: str) -> str | None:
    if not name:
        return None
    return name if lang == "en" else DEPARTMENT_NAMES[lang].get(code or "", name)


def match_strength(suggestion: dict) -> str:
    """How clear the routing match is. NOT a probability (rule weights are not probabilities)."""
    if suggestion["status"] != "matched":
        return "unclear"
    cands = suggestion["candidates"]
    top = cands[0]
    margin = suggestion.get("score_margin") or 0
    if len(cands) == 1 and top["score"] >= 5 or margin >= 3:
        return "clear"
    return "likely" if margin >= 1 else "unclear"


def _has_detail(ex: text_processing.Extraction, details: dict, key: str, lead: str | None) -> bool:
    if key == "duration":
        return bool(ex.durations or details.get("duration_said")) or any(
            "duration" in m.attributes for m in ex.reported)
    if key == "severity":
        return bool(ex.severity or details.get("severity")) or any(
            "severity" in m.attributes for m in ex.reported)
    return False


def next_slot(ex: text_processing.Extraction, details: dict, asked: list[str], max_questions: int) -> str | None:
    if len(asked) >= max_questions:
        return None
    terms = [m.term for m in ex.reported]
    if not terms:
        if "describe" not in asked:
            return "describe"
        return "describe_retry" if "describe_retry" not in asked else None
    lead = next((t for t in terms if t in PAIN_LIKE), terms[0])
    wanted: list[str] = []
    if "stomach pain" in terms and "location" not in details:
        wanted.append("abdomen")
    elif "pain (location not stated)" in terms and not any(t in PAIN_LIKE and t != "pain (location not stated)" for t in terms) \
            and "location" not in details:
        wanted.append("pain_location")
    if not _has_detail(ex, details, "duration", lead):
        wanted.append("duration")
    if lead in PAIN_LIKE and not _has_detail(ex, details, "severity", lead):
        wanted.append("severity")
    if len(terms) < 3 and not details.get("associated_none"):
        wanted.append("associated")
    if not (ex.medication_mentions and ex.allergy_mentions) and not details.get("medicines_none"):
        wanted.append("medicines")
    return next((s for s in wanted if s not in asked), None)


def plan_turn(*, lang: str, combined_en: str, details: dict, asked: list[str], suggestion: dict,
              patient_turns: int, emergency_number: str, max_questions: int) -> Turn:
    """Decide the assistant's next message from the whole conversation so far."""
    t = TEMPLATES[lang]
    ex = text_processing.extract(combined_en)
    terms = [m.term for m in ex.reported]
    uncertain = {m.term for m in ex.reported if m.status == "uncertain"}
    attention = [a for a in suggestion.get("attention", []) if a.get("context") in ("current", "uncertain")]
    urgent = bool(set(terms) & RED_FLAG_TERMS) or bool(attention)
    loc = details.get("location", {})
    caution = ("stomach pain" in terms and "fever" in terms and loc.get("side") == "right"
               and loc.get("region") == "lower")

    strength = match_strength(suggestion)
    dept_meta = None
    if suggestion["status"] in ("matched", "default", "ambiguous"):
        cands = suggestion["candidates"]
        why_terms: list[str] = []
        for m in (cands[0]["matches"] if cands else []):
            term = term_for_phrase(m["phrase"]) or m["phrase"]
            if term not in why_terms:
                why_terms.append(term)
        dept_meta = {
            "status": suggestion["status"], "strength": strength, "code": suggestion["department_code"],
            "name": suggestion["department_name"], "why": why_terms,
            "alternatives": [{"name": c["name"], "score": c["score"]} for c in cands[:3]],
            "note": "Preliminary. Not a probability. Staff confirm the department.",
        }

    def listing(names: list[str]) -> str:
        return t["and"].join(names) if len(names) <= 2 else ", ".join(names[:-1]) + t["and"] + names[-1]

    understood = [f"{_name(x, lang)} {t['unsure']}" if x in uncertain else _name(x, lang) for x in terms]

    def dept_sentence() -> str:
        if not dept_meta or dept_meta["status"] == "ambiguous":
            return t["dept_unclear"]
        if dept_meta["status"] == "default":
            return t["dept_default"]
        dname = _dept_name(dept_meta["code"], dept_meta["name"], lang)
        why = listing([_name(x, lang) for x in dept_meta["why"]]) or dname
        return (t["dept_clear"] if strength == "clear" else t["dept_likely"]).format(dept=dname, why=why)

    meta_common = {
        "engine": DIALOGUE_ENGINE, "asked_so_far": asked,
        "symptoms": [{"term": m.term, "status": m.status,
                      "severity": (m.attributes.get("severity") or {}).get("text"),
                      "duration": (m.attributes.get("duration") or {}).get("text")} for m in ex.reported],
        "denied": [m.term for m in ex.denied], "urgent": urgent, "caution": caution,
        "department": dept_meta, "details": details,
    }

    if urgent:  # emergency guidance first, no questions in the way
        parts = [t["urgent"].format(number=emergency_number)]
        if understood:
            parts.append(t["understood"].format(list=listing(understood)))
        parts += [dept_sentence(), t["prelim"], t["next"]]
        return Turn(" ".join(parts), {**meta_common, "stage": "urgent", "asked": None})

    slot = next_slot(ex, details, asked, max_questions)
    if slot is not None:
        lead = next((x for x in terms if x in PAIN_LIKE), terms[0] if terms else None)
        key = {"abdomen": "q_abdomen", "pain_location": "q_pain_location", "duration": "q_duration",
               "severity": "q_severity", "associated": "q_associated", "medicines": "q_medicines",
               "describe": "q_describe", "describe_retry": "q_describe_retry"}[slot]
        question = t[key].format(symptom=_name(lead, lang) if lead else "")
        opener = t["empathy"] if patient_turns <= 1 else t["thanks"]
        parts = [opener]
        if caution:
            parts.append(t["caution"])
        parts.append(question)
        return Turn(" ".join(parts), {**meta_common, "stage": "asking", "asked": slot})

    parts = [t["thanks"]]
    if understood:
        parts.append(t["understood"].format(list=listing(understood)))
    if ex.denied:
        parts.append(t["not_have"].format(list=listing([_name(m.term, lang) for m in ex.denied])))
    if caution:
        parts.append(t["caution"])
    parts += [dept_sentence(), t["prelim"], t["worse"].format(number=emergency_number), t["next"]]
    return Turn(" ".join(parts), {**meta_common, "stage": "ready", "asked": None})
