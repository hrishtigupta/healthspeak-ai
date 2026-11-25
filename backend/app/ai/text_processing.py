"""Transparent, rule-based extraction of what the patient EXPLICITLY said.

Rules of this module (from the project's clinical-safety requirements):
- Only literal (or, conservatively, one-typo) matches are extracted; every item carries the
  exact source words and their position.
- Nothing is inferred: duration, severity, frequency, timing and triggers are only reported
  when stated in the same clause, otherwise they are listed as "not mentioned".
- Every symptom mention gets a context status: current, uncertain, negated, historical or
  third_party ("my mother has a headache"). Only current/uncertain mentions land in
  `reported`; the rest stay visible in their own lists and are never dropped.
- Text that matched nothing is preserved in `unmatched` so staff can see it.
- No diagnosis, no interpretation, no advice. Everything starts as "unreviewed".
"""

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from app.ai.lexicon import (
    ALLERGY_WORDS,
    EXTERNAL_CODES,
    FUZZY_STOPWORDS,
    HEALTH_CUES,
    LEXICON_VERSION,
    MEDICATION_WORDS,
    NEGATION_CUES,
    SEVERITY_WORDS,
    SYMPTOMS,
    UNCERTAINTY_WORDS,
    symptom_id,
)

ENGINE_VERSION = "rules-v2"
NEGATION_WINDOW_CHARS = 45  # how far back a negation cue may sit within the clause
HEDGE_WINDOW_BEFORE = 45
HEDGE_WINDOW_AFTER = 30
SEVERITY_WINDOW = 25
FUZZY_MIN_LEN = 6
MAX_MENTIONS = 100

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
_FREQUENCY_PATTERN = (
    r"\b(?:every\s+(?:day|night|morning|evening|week|month|hour|few\s+\w+)|daily|nightly|weekly|"
    r"(?:once|twice|thrice|\d+\s+times|two\s+times|three\s+times)\s+(?:a|an|per|each|every)\s+"
    r"(?:day|night|week|month|hour)|often|frequently|occasionally|constantly|all\s+the\s+time|"
    r"on\s+and\s+off|comes\s+and\s+goes|again\s+and\s+again|at\s+times|now\s+and\s+then|sometimes)\b"
)
_TIMING_PATTERN = (
    r"\b(?:at\s+night|in\s+the\s+(?:morning|evening|afternoon|night)|at\s+(?:bedtime|midnight|noon)|"
    r"early\s+morning|during\s+the\s+(?:day|night)|when\s+i\s+wake\s+up|before\s+(?:meals|bed|eating))\b"
)
_TRIGGER_HEAD = (
    r"(?:when|while|whenever|after|during|on|upon)\s+(?:i\s+)?(?:am\s+)?"
    r"(?:walking|climbing|running|exercising|exercise|eating|drinking|coughing|lying|bending|standing|"
    r"sitting|sleeping|swallowing|urinating|breathing|lifting|exertion|meals|food|stress|stairs|"
    r"walk|climb|run|eat|drink|cough|lie|bend|stand|sit|swallow|urinate|lift|exert\w*)"
)
_TRIGGER_TAIL = r"(?:\s+(?!and\b|but\b|or\b|for\b|since\b|i\b|it\b|so\b)[a-z]+){0,2}"
_TRIGGER_PATTERN = rf"\b{_TRIGGER_HEAD}\b{_TRIGGER_TAIL}"

_CLAUSE_BREAK = re.compile(r"[.;!?\n]|\bbut\b|\bhowever\b|\balthough\b", re.IGNORECASE)
# Context uses a slightly finer split so "I had fever last week and now I have a cough" separates.
_CTX_BREAK = re.compile(
    r"[.;!?\n]|\bbut\b|\bhowever\b|\balthough\b|\bnow\b|,\s*(?=i\b)|\band\s+(?=(?:i|he|she|my)\b)",
    re.IGNORECASE)
_SENTENCE_BREAK = re.compile(r"[.;!?\n]+")

_HISTORICAL = re.compile(
    r"\blast\s+(?:week|month|year|weekend|winter|summer|monsoon)\b|"
    r"\blast\s+(?:mon|tues|wednes|thurs|fri|satur|sun)day\b|"
    rf"\b{_NUM}\s+(?:days?|weeks?|months?|years?)\s+ago\b|"
    r"\b(?:previously|in the past|used to|history of|years back|as a child|childhood|"
    r"when i was (?:a )?(?:child|kid|young|little)|recovered|went away|got better|cleared up|"
    r"was cured|has gone|have gone)\b", re.IGNORECASE)
# Words that show the problem is still going on, overriding a historical cue in the same clause.
_ONGOING = re.compile(r"\b(?:still|currently|today|right now|at the moment|ongoing|since|again)\b",
                      re.IGNORECASE)
_THIRD_PARTY = re.compile(
    r"\b(?:my|his|her|their)\s+(?:mother|mom|mum|father|dad|wife|husband|son|daughter|child|children|"
    r"kid|kids|baby|brother|sister|grandmother|grandfather|grandma|grandpa|friend|colleague|"
    r"neighbou?r|uncle|aunt|cousin|partner|boyfriend|girlfriend|mother-in-law|father-in-law)\b|"
    r"\b(?:he|she)\b", re.IGNORECASE)
_FIRST_PERSON = re.compile(r"\b(?:i|i'm|i've|i'd|i'll|me|myself)\b", re.IGNORECASE)
_FIRST_PERSON_OWN = re.compile(r"\b(?:my|me)\b", re.IGNORECASE)
_HEDGES = re.compile(
    r"\b(?:i think|i guess|i suppose|i suspect|maybe|might|may be|perhaps|possibly|probably|"
    r"not sure|not certain|unsure|could be|seems? like|don't know if|do not know if)\b", re.IGNORECASE)


def _phrase_regex(phrase: str) -> re.Pattern:
    body = r"\s+".join(re.escape(p) for p in phrase.split())
    return re.compile(rf"(?<![\w'-]){body}(?![\w-])", re.IGNORECASE)


def normalize(text: str) -> str:
    """Unicode-normalise and unify apostrophes/spaces WITHOUT changing the words."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("’", "'").replace("‘", "'").replace(" ", " ")
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
    shared: bool = False  # attribute found in a clause that names several symptoms


@dataclass
class SymptomMention:
    term: str
    evidence: Evidence
    negated: bool
    symptom_id: str = ""
    external_codes: dict = field(default_factory=dict)
    # current | uncertain | negated | historical | third_party
    status: str = "current"
    subject: str = "self"  # self | third_party
    match_type: str = "exact"  # exact | fuzzy
    matched_phrase: str = ""  # the vocabulary phrase that matched
    cues: list[Evidence] = field(default_factory=list)  # words that decided the status
    attributes: dict = field(default_factory=dict)  # severity/duration/frequency/timing/triggers
    review_required: bool = False
    review_status: str = "unreviewed"


@dataclass
class Context:
    status: str
    subject: str
    negated: bool
    uncertain: bool
    historical: bool
    cues: list[Evidence]


@dataclass
class Extraction:
    reported: list[SymptomMention] = field(default_factory=list)  # current or uncertain, about the patient
    denied: list[SymptomMention] = field(default_factory=list)
    historical: list[SymptomMention] = field(default_factory=list)
    third_party: list[SymptomMention] = field(default_factory=list)
    mentions: list[SymptomMention] = field(default_factory=list)  # every occurrence, in text order
    durations: list[Evidence] = field(default_factory=list)
    severity: list[Evidence] = field(default_factory=list)
    uncertainty: list[Evidence] = field(default_factory=list)
    medication_mentions: list[str] = field(default_factory=list)
    allergy_mentions: list[str] = field(default_factory=list)
    unmatched: list[Evidence] = field(default_factory=list)  # patient text with no recognised symptom
    missing: list[str] = field(default_factory=list)
    health_related: bool = False
    review_required: bool = True
    review_reasons: list[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    lexicon_version: str = LEXICON_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- context ----------

def _clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    lo = max(0, start - 300)
    left = lo
    for m in _CTX_BREAK.finditer(text, lo, start):
        left = m.end()
    right = min(len(text), end + 300)
    m = _CTX_BREAK.search(text, end, right)
    if m:
        right = m.start()
    return left, right


def _ev(text: str, base: int, m: re.Match) -> Evidence:
    return Evidence(text[base + m.start():base + m.end()], base + m.start(), base + m.end())


def classify_context(text: str, start: int, end: int) -> Context:
    """Decide whether the words at text[start:end] describe a present symptom of the patient."""
    cl_start, cl_end = _clause_bounds(text, start, end)
    whole = text[cl_start:cl_end]
    cues: list[Evidence] = []

    negated = is_negated(text, start)

    subject = "self"
    prefix = text[cl_start:start]
    third = list(_THIRD_PARTY.finditer(prefix))
    if third:
        first_person = list(_FIRST_PERSON.finditer(prefix))
        if not first_person or third[-1].start() > first_person[-1].start():
            subject = "third_party"
            cues.append(_ev(text, cl_start, third[-1]))

    historical = False
    hist = _HISTORICAL.search(whole)
    if hist and not _ONGOING.search(whole):
        historical = True
        cues.append(_ev(text, cl_start, hist))

    uncertain = False
    h_lo = max(cl_start, start - HEDGE_WINDOW_BEFORE)
    h_hi = min(cl_end, end + HEDGE_WINDOW_AFTER)
    hedge = _HEDGES.search(text, h_lo, h_hi)
    if hedge:
        uncertain = True
        cues.append(Evidence(hedge.group(0), hedge.start(), hedge.end()))

    if negated:
        status = "negated"
    elif subject == "third_party":
        status = "third_party"
    elif historical:
        status = "historical"
    elif uncertain:
        status = "uncertain"
    else:
        status = "current"
    return Context(status, subject, negated, uncertain, historical, cues)


def has_health_cue(text: str) -> bool:
    low = normalize(text).lower()
    return any(find_phrase(low, w) for w in HEALTH_CUES)


# ---------- matching ----------

def _osa_distance(a: str, b: str) -> int:
    """Edit distance counting insert/delete/substitute/adjacent-swap as one edit each."""
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


_ALL_VOCAB_WORDS = {w.lower() for phrases in SYMPTOMS.values() for p in phrases for w in p.split()}
# Single-word vocabulary entries long enough that one typo cannot turn another real word into them.
_FUZZY_TARGETS: dict[str, tuple[str, str]] = {
    p.lower(): (term, p) for term, phrases in SYMPTOMS.items() for p in phrases
    if " " not in p and "-" not in p and "'" not in p and len(p) >= FUZZY_MIN_LEN
}
_TOKEN = re.compile(r"(?<![\w'-])[A-Za-z]{%d,}(?![\w'-])" % FUZZY_MIN_LEN)


def _fuzzy_target(token: str) -> tuple[str, str] | None:
    low = token.lower()
    if low in _ALL_VOCAB_WORDS or low in FUZZY_STOPWORDS:
        return None
    hits: dict[str, tuple[str, str]] = {}
    for cand, (term, phrase) in _FUZZY_TARGETS.items():
        if cand[0] != low[0] or abs(len(cand) - len(low)) > 1:
            continue
        if _osa_distance(low, cand) == 1:
            hits[term] = (term, phrase)
    # Two different symptoms equally close = ambiguous: do not guess.
    return next(iter(hits.values())) if len(hits) == 1 else None


def _non_overlapping(matches: list[tuple[int, int, str, str, str]]) -> list[tuple[int, int, str, str, str]]:
    """Prefer longer, more specific phrases ("chest pain" over "pain"); exact beats fuzzy."""
    chosen: list[tuple[int, int, str, str, str]] = []
    for m in sorted(matches, key=lambda m: (m[4] == "fuzzy", -(m[1] - m[0]), m[0])):
        if all(m[1] <= c[0] or m[0] >= c[1] for c in chosen):
            chosen.append(m)
    return sorted(chosen)


def _simple(text: str, words: list[str]) -> list[Evidence]:
    found = [(s, e) for w in words for s, e in find_phrase(text, w)]
    out, last_end = [], -1
    for s, e in sorted(found, key=lambda x: (x[0], -(x[1] - x[0]))):
        if s >= last_end:
            out.append(Evidence(text[s:e], s, e))
            last_end = e
    return out


def _regex_evidence(text: str, patterns: list[str], lo: int = 0, hi: int | None = None) -> list[Evidence]:
    hi = len(text) if hi is None else hi
    found = [(m.start(), m.end()) for p in patterns for m in re.finditer(p, text[lo:hi], re.IGNORECASE)]
    out, last_end = [], -1
    for s, e in sorted(found, key=lambda x: (x[0], -(x[1] - x[0]))):
        if s >= last_end:
            out.append(Evidence(text[lo + s:lo + e], lo + s, lo + e))
            last_end = e
    return out


def _attach_attributes(text: str, mentions: list[SymptomMention]) -> None:
    """Link severity/duration/frequency/timing/triggers that sit in the SAME clause.

    Nothing outside the clause is attached, and when a clause names several symptoms the
    clause-level details are marked `shared` so staff know they may not apply to each one.
    """
    spans = [(m.evidence.start, m.evidence.end) for m in mentions]
    for m in mentions:
        cl_start, cl_end = _clause_bounds(text, m.evidence.start, m.evidence.end)
        in_clause = [s for s in spans if cl_start <= s[0] < cl_end]
        shared = len(in_clause) > 1
        attrs: dict = {}

        best = None
        for ev in _simple(text[cl_start:cl_end], SEVERITY_WORDS):
            s, e = cl_start + ev.start, cl_start + ev.end
            gap = s - m.evidence.end if s >= m.evidence.end else m.evidence.start - e
            if gap > SEVERITY_WINDOW:
                continue
            lo, hi = sorted((s, m.evidence.start))
            if any(lo < o[0] < hi or lo < o[1] < hi for o in in_clause if o != (m.evidence.start, m.evidence.end)):
                continue  # another symptom sits between them: it belongs to that one
            if best is None or gap < best[0]:
                best = (gap, Evidence(ev.text, s, e))
        if best:
            attrs["severity"] = asdict(best[1])

        for key, patterns in (("duration", _DURATION_PATTERNS), ("frequency", [_FREQUENCY_PATTERN]),
                              ("timing", [_TIMING_PATTERN])):
            evs = _regex_evidence(text, patterns, cl_start, cl_end)
            if evs:
                attrs[key] = asdict(Evidence(evs[0].text, evs[0].start, evs[0].end, shared))
        trig = _regex_evidence(text, [_TRIGGER_PATTERN], cl_start, cl_end)
        if trig:
            attrs["triggers"] = [asdict(Evidence(t.text, t.start, t.end, shared)) for t in trig]
        m.attributes = attrs


def extract(source_text: str) -> Extraction:
    text = normalize(source_text)
    result = Extraction()

    raw: list[tuple[int, int, str, str, str]] = [
        (s, e, term, p, "exact") for term, phrases in SYMPTOMS.items() for p in phrases
        for s, e in find_phrase(text, p)]
    for m in _TOKEN.finditer(text):
        target = _fuzzy_target(m.group(0))
        if target:
            raw.append((m.start(), m.end(), target[0], target[1], "fuzzy"))

    for s, e, term, phrase, match_type in _non_overlapping(raw)[:MAX_MENTIONS]:
        ctx = classify_context(text, s, e)
        mention = SymptomMention(
            term=term, evidence=Evidence(text[s:e], s, e), negated=ctx.negated,
            symptom_id=symptom_id(term), external_codes=dict(EXTERNAL_CODES.get(term, {})),
            status=ctx.status, subject=ctx.subject, match_type=match_type, matched_phrase=phrase,
            cues=ctx.cues,
            review_required=(match_type == "fuzzy" or ctx.status != "current"),
        )
        result.mentions.append(mention)
    _attach_attributes(text, result.mentions)

    buckets = {"current": result.reported, "uncertain": result.reported, "negated": result.denied,
               "historical": result.historical, "third_party": result.third_party}
    seen: set[tuple[str, str]] = set()
    for mention in result.mentions:
        bucket = buckets[mention.status]
        key = (id(bucket), mention.term)
        # "current" and "uncertain" share one list; first mention of a term wins its slot.
        if key not in seen:
            seen.add(key)
            bucket.append(mention)
    # A term both reported and denied stays "reported" (and visible as both) - staff decide.

    result.durations = _regex_evidence(text, _DURATION_PATTERNS)
    result.severity = _simple(text, SEVERITY_WORDS)
    result.uncertainty = _simple(text, UNCERTAINTY_WORDS)
    result.medication_mentions = list(dict.fromkeys(
        _sentence_around(text, ev.start, ev.end) for ev in _simple(text, MEDICATION_WORDS)))
    result.allergy_mentions = list(dict.fromkeys(
        _sentence_around(text, ev.start, ev.end) for ev in _simple(text, ALLERGY_WORDS)))

    # Preserve patient text that produced no recognised symptom, verbatim, with positions.
    covered = [(mm.evidence.start, mm.evidence.end) for mm in result.mentions]
    pos = 0
    for brk in list(_SENTENCE_BREAK.finditer(text)) + [None]:
        seg_end = brk.start() if brk else len(text)
        seg = text[pos:seg_end]
        stripped = seg.strip()
        if stripped and not any(pos <= c[0] < seg_end for c in covered):
            lead = len(seg) - len(seg.lstrip())
            result.unmatched.append(Evidence(stripped, pos + lead, pos + lead + len(stripped)))
        pos = brk.end() if brk else len(text)

    result.health_related = bool(result.mentions) or has_health_cue(text)
    unrecognised = [u for u in result.unmatched
                    if has_health_cue(u.text) or _FIRST_PERSON_OWN.search(u.text)]

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

    reasons = result.review_reasons
    if any(m.match_type == "fuzzy" for m in result.mentions):
        reasons.append("A symptom was matched despite a spelling difference - check the wording.")
    if any(m.status == "uncertain" for m in result.mentions):
        reasons.append("The patient sounded unsure about a symptom.")
    if result.third_party:
        reasons.append("A symptom was described for another person, not the patient.")
    if result.historical:
        reasons.append("A symptom was described as past, not current.")
    if unrecognised:
        reasons.append("Some health-related words were not recognised - read the original text.")
    if not result.mentions:
        reasons.append("No symptom from the approved vocabulary was found - read the original text.")
    return result


def summarize(ex: Extraction) -> str:
    """A plain summary in which every item is quoted from the patient's words."""
    q = lambda ev: f'"{ev.text}"'  # noqa: E731
    parts = []
    if ex.reported:
        parts.append("Reported: " + "; ".join(
            f"{m.term}{' (unsure)' if m.status == 'uncertain' else ''} ({q(m.evidence)})"
            for m in ex.reported) + ".")
    else:
        parts.append("No symptoms from the approved vocabulary were identified.")
    if ex.denied:
        parts.append("Said they do NOT have: " + "; ".join(f"{m.term} ({q(m.evidence)})" for m in ex.denied) + ".")
    if ex.historical:
        parts.append("Described as in the PAST (not current): "
                     + "; ".join(f"{m.term} ({q(m.evidence)})" for m in ex.historical) + ".")
    if ex.third_party:
        parts.append("Described for ANOTHER PERSON: "
                     + "; ".join(f"{m.term} ({q(m.evidence)})" for m in ex.third_party) + ".")
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
