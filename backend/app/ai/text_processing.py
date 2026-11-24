"""Transparent, rule-based extraction of what the patient EXPLICITLY said.

Rules of this module (from the project's clinical-safety requirements):
- Only literal matches are extracted; every item carries the exact source words.
- Nothing is inferred: duration, severity, medication and allergies are only
  reported when stated, otherwise they are listed as "not mentioned".
- Negated mentions ("no fever") are reported as denied, never as symptoms.
- No diagnosis, no interpretation, no advice.
"""

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from app.ai.lexicon import (
    ALLERGY_WORDS,
    LEXICON_VERSION,
    MEDICATION_WORDS,
    NEGATION_CUES,
    SEVERITY_WORDS,
    SYMPTOMS,
    UNCERTAINTY_WORDS,
)

ENGINE_VERSION = "rules-v1"
NEGATION_WINDOW_CHARS = 45  # how far back a negation cue may sit within the clause

_NUM = (r"(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"few|a few|several|couple of|a couple of)")
_UNIT = r"(?:minutes?|hours?|hrs?|days?|nights?|weeks?|months?|years?)"
_DURATION_PATTERNS = [
    rf"\bfor\s+(?:the\s+)?(?:last\s+|past\s+)?{_NUM}\s+{_UNIT}\b",
    rf"\b(?:last|past)\s+{_NUM}\s+{_UNIT}\b",
    rf"\b{_NUM}\s+{_UNIT}\s+ago\b",
    r"\bsince\s+(?:yesterday|today|this\s+morning|this\s+evening|last\s+night|morning|"
    r"last\s+week|last\s+month|last\s+year|childhood|birth|\w+day|\d+\s+\w+)\b",
    r"\bfrom\s+(?:yesterday|last\s+night|last\s+week|this\s+morning)\b",
    r"\b(?:yesterday|last\s+night|this\s+morning)\b",
]
_CLAUSE_BREAK = re.compile(r"[.;!?\n]|\bbut\b|\bhowever\b|\balthough\b", re.IGNORECASE)


def _phrase_regex(phrase: str) -> re.Pattern:
    body = r"\s+".join(re.escape(p) for p in phrase.split())
    return re.compile(rf"(?<![\w'-]){body}(?![\w-])", re.IGNORECASE)


def normalize(text: str) -> str:
    """Unicode-normalise and unify apostrophes/spaces WITHOUT changing the words."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("’", "'").replace("‘", "'").replace(" ", " ")
    return text


def _clause_prefix(text: str, start: int) -> str:
    """Text from the start of the clause containing `start` up to `start`."""
    prefix = text[max(0, start - 200):start]
    breaks = list(_CLAUSE_BREAK.finditer(prefix))
    if breaks:
        prefix = prefix[breaks[-1].end():]
    return prefix[-NEGATION_WINDOW_CHARS:]


_NEGATION_RES = [_phrase_regex(c) for c in NEGATION_CUES]
# "not sure" / "not certain" express uncertainty, not denial.
_NOT_NEGATION = re.compile(r"\bnot\s+(?:sure|certain)\b", re.IGNORECASE)


def is_negated(text: str, start: int) -> bool:
    prefix = _NOT_NEGATION.sub(" ", _clause_prefix(text, start))
    return any(r.search(prefix) for r in _NEGATION_RES)


def find_phrase(text: str, phrase: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _phrase_regex(phrase).finditer(text)]


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(c, 0, start) for c in ".!?\n")
    right_candidates = [i for i in (text.find(c, end) for c in ".!?\n") if i != -1]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    return text[left + 1:right].strip()


@dataclass
class Evidence:
    text: str  # exact words from the source
    start: int
    end: int


@dataclass
class SymptomMention:
    term: str
    evidence: Evidence
    negated: bool


@dataclass
class Extraction:
    reported: list[SymptomMention] = field(default_factory=list)
    denied: list[SymptomMention] = field(default_factory=list)
    durations: list[Evidence] = field(default_factory=list)
    severity: list[Evidence] = field(default_factory=list)
    uncertainty: list[Evidence] = field(default_factory=list)
    medication_mentions: list[str] = field(default_factory=list)
    allergy_mentions: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    lexicon_version: str = LEXICON_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def _non_overlapping(matches: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Prefer longer, more specific phrases ("chest pain" over "pain")."""
    chosen: list[tuple[int, int, str]] = []
    for s, e, term in sorted(matches, key=lambda m: (-(m[1] - m[0]), m[0])):
        if all(e <= cs or s >= ce for cs, ce, _ in chosen):
            chosen.append((s, e, term))
    return sorted(chosen)


def _simple(text: str, words: list[str]) -> list[Evidence]:
    found = [(s, e) for w in words for s, e in find_phrase(text, w)]
    out, last_end = [], -1
    for s, e in sorted(found, key=lambda x: (x[0], -(x[1] - x[0]))):
        if s >= last_end:
            out.append(Evidence(text[s:e], s, e))
            last_end = e
    return out


def extract(source_text: str) -> Extraction:
    text = normalize(source_text)
    result = Extraction()

    raw = [(s, e, term) for term, phrases in SYMPTOMS.items() for p in phrases
           for s, e in find_phrase(text, p)]
    seen_reported: set[str] = set()
    seen_denied: set[str] = set()
    for s, e, term in _non_overlapping(raw):
        mention = SymptomMention(term=term, evidence=Evidence(text[s:e], s, e), negated=is_negated(text, s))
        if mention.negated:
            if term not in seen_denied:
                result.denied.append(mention)
                seen_denied.add(term)
        elif term not in seen_reported:
            result.reported.append(mention)
            seen_reported.add(term)
    # A term both reported and denied stays "reported" (and visible as both) - staff decide.

    dur = [(m.start(), m.end()) for p in _DURATION_PATTERNS for m in re.finditer(p, text, re.IGNORECASE)]
    last_end = -1
    for s, e in sorted(dur, key=lambda x: (x[0], -(x[1] - x[0]))):
        if s >= last_end:
            result.durations.append(Evidence(text[s:e], s, e))
            last_end = e

    result.severity = _simple(text, SEVERITY_WORDS)
    result.uncertainty = _simple(text, UNCERTAINTY_WORDS)
    result.medication_mentions = list(dict.fromkeys(
        _sentence_around(text, ev.start, ev.end) for ev in _simple(text, MEDICATION_WORDS)))
    result.allergy_mentions = list(dict.fromkeys(
        _sentence_around(text, ev.start, ev.end) for ev in _simple(text, ALLERGY_WORDS)))

    if not result.reported:
        result.missing.append("No symptoms from the approved vocabulary were identified")
    if not result.durations:
        result.missing.append("How long it has been going on (duration)")
    if not result.severity:
        result.missing.append("How bad it is (severity)")
    if not result.medication_mentions:
        result.missing.append("Medicines being taken")
    if not result.allergy_mentions:
        result.missing.append("Allergies")
    return result


def summarize(ex: Extraction) -> str:
    """A plain summary in which every item is quoted from the patient's words."""
    q = lambda ev: f'"{ev.text}"'  # noqa: E731
    parts = []
    if ex.reported:
        parts.append("Reported: " + "; ".join(f"{m.term} ({q(m.evidence)})" for m in ex.reported) + ".")
    else:
        parts.append("No symptoms from the approved vocabulary were identified.")
    if ex.denied:
        parts.append("Said they do NOT have: " + "; ".join(f"{m.term} ({q(m.evidence)})" for m in ex.denied) + ".")
    if ex.durations:
        parts.append("Time mentioned: " + ", ".join(q(d) for d in ex.durations) + ".")
    if ex.severity:
        parts.append("Severity words used: " + ", ".join(q(s) for s in ex.severity) + ".")
    if ex.uncertainty:
        parts.append("Patient expressed uncertainty: " + ", ".join(q(u) for u in ex.uncertainty) + ".")
    if ex.medication_mentions:
        parts.append("Medicine mentioned: " + " / ".join(f'"{m}"' for m in ex.medication_mentions) + ".")
    if ex.allergy_mentions:
        parts.append("Allergy mentioned: " + " / ".join(f'"{m}"' for m in ex.allergy_mentions) + ".")
    missing = [m for m in ex.missing if not m.startswith("No symptoms")]
    if missing:
        parts.append("Not mentioned: " + "; ".join(missing) + ".")
    parts.append("(Automatically extracted from the patient's own words. Not a diagnosis. "
                 "Requires staff review.)")
    return " ".join(parts)
