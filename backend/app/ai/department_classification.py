"""Suggest a department from configurable routing rules (D7). Not a diagnosis.

Each active rule is a phrase + weight for one department ("route" rules) or a
phrase that hospital policy marks for prompt staff attention ("attention" rules).
A rule counts once if its phrase appears in the text and is not negated
("no chest pain" does not count). The department with the highest total wins;
a tie means "ambiguous" (staff must choose); no match falls back to the default
department, clearly labelled as such.
"""

import hashlib
from dataclasses import asdict, dataclass, field

from app.ai.text_processing import find_phrase, is_negated, normalize


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


@dataclass
class Candidate:
    department_id: str
    code: str
    name: str
    score: int
    matches: list[Match] = field(default_factory=list)


@dataclass
class Suggestion:
    status: str  # matched | ambiguous | default | no_rules
    department_id: str | None
    department_code: str | None
    department_name: str | None
    candidates: list[Candidate]
    attention: list[Match]
    ruleset_version: str

    def to_dict(self) -> dict:
        return asdict(self)


def ruleset_version(rules: list[Rule]) -> str:
    key = "|".join(sorted(f"{r.kind}:{r.department_code}:{r.phrase.lower()}:{r.weight}" for r in rules))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _first_unnegated(text: str, phrase: str) -> str | None:
    for s, e in find_phrase(text, phrase):
        if not is_negated(text, s):
            return text[s:e]
    return None


def suggest(source_text: str, rules: list[Rule], default: tuple[str, str, str] | None) -> Suggestion:
    """default = (department_id, code, name) of the fallback department, if any."""
    text = normalize(source_text)
    version = ruleset_version(rules)
    candidates: dict[str, Candidate] = {}
    attention: list[Match] = []
    for r in rules:
        evidence = _first_unnegated(text, r.phrase)
        if evidence is None:
            continue
        m = Match(rule_id=r.id, phrase=r.phrase, weight=r.weight, evidence=evidence)
        if r.kind == "attention":
            attention.append(m)
            continue
        c = candidates.setdefault(r.department_id, Candidate(r.department_id, r.department_code,
                                                             r.department_name, 0))
        c.score += r.weight
        c.matches.append(m)

    ranked = sorted(candidates.values(), key=lambda c: (-c.score, c.name))
    if ranked and (len(ranked) == 1 or ranked[0].score > ranked[1].score):
        top = ranked[0]
        return Suggestion("matched", top.department_id, top.code, top.name, ranked, attention, version)
    if ranked:
        return Suggestion("ambiguous", None, None, None, ranked, attention, version)
    if default:
        return Suggestion("default", *default, [], attention, version)
    return Suggestion("no_rules", None, None, None, [], attention, version)
