"""Suggest a department from configurable routing rules (D7). Not a diagnosis.

Each active rule is a phrase + weight for one department ("route" rules) or a
phrase that hospital policy marks for prompt staff attention ("attention" rules).

A route rule counts once, and only when the phrase describes the PATIENT'S OWN
CURRENT symptom (or one they are unsure about). Phrases that are negated ("no
chest pain"), historical ("fever last week") or about someone else ("my mother
has a cough") never add weight; they are listed under `excluded` so staff can see
why. The department with the highest total wins; a tie is "ambiguous" (staff must
choose); no match falls back to the default department, clearly labelled; text
with no health content at all is "out_of_scope".

Attention rules only surface hospital-defined phrases for prompt staff attention.
This module does not define or run any emergency protocol and is not an emergency
detector: urgent escalation stays with the hospital's own workflow.

Nothing here is ever final. Every suggestion has review_required = True; staff
confirm or change the department. Rule weights are not probabilities, so no
confidence percentage is reported (`confidence` is None).

A future trained classifier can be plugged in by implementing `DepartmentClassifier`
and calling `register_classifier`. None is provided because no reviewed, labelled
dataset exists in this project; synthetic labels would only teach it our own guesses.
"""

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Protocol

from app.ai import text_processing
from app.ai.lexicon import term_for_phrase
from app.ai.text_processing import classify_context, find_phrase, normalize

CONFIDENCE_NOTE = ("Not a calibrated probability: rule weights only rank the rules that matched. "
                   "Staff must confirm the department.")
CLOSE_CALL_RATIO = 0.8


@dataclass
class Rule:
    id: str
    kind: str  # "route" | "attention"
    phrase: str
    weight: int
    department_id: str | None
    department_code: str | None
    department_name: str | None


@dataclass
class Match:
    rule_id: str
    phrase: str
    weight: int
    evidence: str
    context: str = "current"  # current | uncertain | historical | third_party
    start: int = 0
    end: int = 0


@dataclass
class Excluded:
    rule_id: str
    phrase: str
    evidence: str
    reason: str  # negated | historical | third_party
    department_code: str | None = None


@dataclass
class Candidate:
    department_id: str
    code: str
    name: str
    score: int
    matches: list[Match] = field(default_factory=list)


@dataclass
class Suggestion:
    status: str  # matched | ambiguous | default | no_rules | out_of_scope
    department_id: str | None
    department_code: str | None
    department_name: str | None
    candidates: list[Candidate]
    attention: list[Match]
    ruleset_version: str
    excluded: list[Excluded] = field(default_factory=list)
    review_required: bool = True
    review_status: str = "pending_staff_review"
    review_reasons: list[str] = field(default_factory=list)
    confidence: float | None = None  # always None: no calibrated model exists
    confidence_note: str = CONFIDENCE_NOTE
    score_margin: int | None = None
    classifier: str = "rules"

    def to_dict(self) -> dict:
        return asdict(self)


class DepartmentClassifier(Protocol):
    name: str

    def suggest(self, source_text: str, rules: list[Rule],
                default: tuple[str, str, str] | None) -> Suggestion: ...


def ruleset_version(rules: list[Rule]) -> str:
    key = "|".join(sorted(f"{r.kind}:{r.department_code}:{r.phrase.lower()}:{r.weight}" for r in rules))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


class RuleBasedClassifier:
    name = "rules"

    def suggest(self, source_text: str, rules: list[Rule],
                default: tuple[str, str, str] | None) -> Suggestion:
        text = normalize(source_text)
        version = ruleset_version(rules)
        candidates: dict[str, Candidate] = {}
        attention: list[Match] = []
        excluded: list[Excluded] = []

        for r in rules:
            counted: Match | None = None
            attention_hit: Match | None = None
            for s, e in find_phrase(text, r.phrase):
                ctx = classify_context(text, s, e)
                evidence = text[s:e]
                if ctx.status == "negated":
                    excluded.append(Excluded(r.id, r.phrase, evidence, "negated", r.department_code))
                    continue
                if r.kind == "attention":
                    # Hospital policy wants staff to see these even for past / other-person
                    # mentions; the context label tells them which it is.
                    if attention_hit is None:
                        attention_hit = Match(r.id, r.phrase, r.weight, evidence, ctx.status, s, e)
                    continue
                if ctx.status in ("historical", "third_party"):
                    excluded.append(Excluded(r.id, r.phrase, evidence, ctx.status, r.department_code))
                    continue
                if counted is None:
                    counted = Match(r.id, r.phrase, r.weight, evidence, ctx.status, s, e)
            if attention_hit:
                attention.append(attention_hit)
            if counted:
                c = candidates.setdefault(r.department_id, Candidate(
                    r.department_id, r.department_code, r.department_name, 0))
                c.score += r.weight
                c.matches.append(counted)

        # A rule phrase also fires when the extractor found the SAME vocabulary symptom in other
        # words ("my stomach has been hurting" for the rule "stomach pain"). One rule per
        # department and symptom, so several synonyms of one symptom never inflate the score.
        extraction = text_processing.extract(text)
        route_rules = [r for r in rules if r.kind == "route" and r.department_id]
        literal = {(m_dept, term_for_phrase(r.phrase)) for c in candidates.values() for m in c.matches
                   for r in route_rules if r.id == m.rule_id for m_dept in [r.department_id]}
        done: set[tuple[str, str]] = set(literal)
        excluded_already = {(x.department_code, term_for_phrase(x.phrase)) for x in excluded}
        for mention in extraction.mentions:
            by_dept: dict[str, Rule] = {}
            for r in route_rules:
                if term_for_phrase(r.phrase) == mention.term and (
                        r.department_id not in by_dept or r.weight > by_dept[r.department_id].weight):
                    by_dept[r.department_id] = r
            for dept_id, r in by_dept.items():
                key = (dept_id, mention.term)
                if key in done:
                    continue
                if mention.status in ("negated", "historical", "third_party"):
                    if (r.department_code, mention.term) not in excluded_already:
                        excluded.append(Excluded(r.id, r.phrase, mention.evidence.text, mention.status,
                                                 r.department_code))
                        excluded_already.add((r.department_code, mention.term))
                    done.add(key)
                    continue
                c = candidates.setdefault(dept_id, Candidate(
                    dept_id, r.department_code, r.department_name, 0))
                c.score += r.weight
                c.matches.append(Match(r.id, r.phrase, r.weight, mention.evidence.text, mention.status,
                                       mention.evidence.start, mention.evidence.end))
                done.add(key)

        ranked = sorted(candidates.values(), key=lambda c: (-c.score, c.name))
        reasons: list[str] = []
        margin = None

        if ranked and (len(ranked) == 1 or ranked[0].score > ranked[1].score):
            top = ranked[0]
            status = "matched"
            dept = (top.department_id, top.code, top.name)
            margin = top.score - (ranked[1].score if len(ranked) > 1 else 0)
            if len(ranked) > 1 and ranked[1].score >= CLOSE_CALL_RATIO * top.score:
                reasons.append(f"Close scores: {top.name} ({top.score}) and {ranked[1].name} "
                               f"({ranked[1].score}) - check which fits.")
            if any(m.context == "uncertain" for c in ranked for m in c.matches):
                reasons.append("Some matched symptoms were described with uncertainty.")
        elif ranked:
            status, dept = "ambiguous", (None, None, None)
            margin = 0
            reasons.append("Equal scores for: " + ", ".join(c.name for c in ranked) + ". Staff must choose.")
        elif not (excluded or attention or text_processing.extract(text).health_related):
            status, dept = "out_of_scope", (None, None, None)
            reasons.append("No health concern was found in the text, so no department is suggested.")
        elif default:
            status, dept = "default", default
            reasons.append("No routing rule matched a current symptom; the default department is shown "
                           "only as a starting point.")
        else:
            status, dept = "no_rules", (None, None, None)
            reasons.append("No routing rule matched and no default department is configured.")

        if excluded:
            kinds = sorted({x.reason for x in excluded})
            reasons.append("Ignored for routing because they were " + " / ".join(kinds)
                           + " - see 'excluded'.")
        if attention:
            reasons.append("Words that hospital policy marks for prompt staff attention were present.")

        return Suggestion(status, *dept, ranked, attention, version, excluded=excluded,
                          review_reasons=reasons, score_margin=margin, classifier=self.name)


_classifier: DepartmentClassifier = RuleBasedClassifier()


def get_classifier() -> DepartmentClassifier:
    return _classifier


def register_classifier(classifier: DepartmentClassifier) -> None:
    """Swap in another classifier (e.g. a future trained model). Must return a Suggestion."""
    global _classifier
    _classifier = classifier


def suggest(source_text: str, rules: list[Rule], default: tuple[str, str, str] | None) -> Suggestion:
    """default = (department_id, code, name) of the fallback department, if any."""
    return get_classifier().suggest(source_text, rules, default)
