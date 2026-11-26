"""Context-aware extraction (rules-v2) and context-aware department suggestions.

All text here is synthetic. These tests need no database.
"""

import pytest

from app.ai.department_classification import Rule, suggest
from app.ai.text_processing import extract, summarize

pytestmark = pytest.mark.no_db


def by_term(ex, term):
    return [m for m in ex.mentions if m.term == term]


def statuses(ex):
    return {(m.term, m.status) for m in ex.mentions}


# ---------- matching ----------

@pytest.mark.parametrize("text,term", [
    ("I have a fever", "fever"),
    ("I have a high temperature", "fever"),            # synonym
    ("There is pain in my chest", "chest pain"),
    ("It is hard, I feel short of breath", "breathing difficulty"),  # multiword
    ("I keep throwing up", "vomiting"),
    ("loose motions since morning", "diarrhoea"),
])
def test_phrases_and_synonyms(text, term):
    assert term in {m.term for m in extract(text).reported}


def test_specific_phrase_wins_over_generic_pain():
    ex = extract("I have chest pain")
    assert [m.term for m in ex.mentions] == ["chest pain"]


@pytest.mark.parametrize("text,term", [
    ("I have vomitting", "vomiting"),
    ("I have diarhea", "diarrhoea"),
    ("a bad hedache", "headache"),
    ("feeling dizzyness", "dizziness"),
])
def test_conservative_fuzzy_match_is_flagged_for_review(text, term):
    ex = extract(text)
    m = by_term(ex, term)[0]
    assert m.match_type == "fuzzy" and m.review_required
    assert m.evidence.text in text  # the patient's own spelling is kept as evidence
    assert any("spelling" in r for r in ex.review_reasons)


@pytest.mark.parametrize("text", [
    "He is breeding dogs",              # one edit from "bleeding"
    "She was healing well",             # one edit from "feeling"-like words
    "The weather is fewer than before",  # short words are never fuzzy-matched
    "I like reading",
    "feverish-looking painting",        # hyphenated compound must not match as a symptom word
])
def test_unrelated_words_are_not_symptoms(text):
    assert extract(text).mentions == []


def test_substring_inside_other_words_does_not_match():
    ex = extract("My cousin Hurston is coughlin and the painter came")
    assert ex.mentions == []


def test_two_symptoms_equally_close_are_not_guessed():
    # "vomitng" could only be vomiting; but a token equidistant from two terms must be skipped.
    from app.ai.text_processing import _fuzzy_target
    assert _fuzzy_target("headach") is None or _fuzzy_target("headach")[0] == "headache"


# ---------- context ----------

def test_negated_symptom_is_not_present():
    ex = extract("I do not have fever.")
    assert statuses(ex) == {("fever", "negated")}
    assert ex.reported == [] and [m.term for m in ex.denied] == ["fever"]


def test_historical_symptom_is_kept_but_not_current():
    ex = extract("I had fever last week.")
    assert statuses(ex) == {("fever", "historical")}
    assert ex.reported == [] and [m.term for m in ex.historical] == ["fever"]
    assert ex.mentions[0].cues[0].text == "last week"


def test_third_party_symptom():
    ex = extract("my mother has a headache")
    assert statuses(ex) == {("headache", "third_party")}
    assert ex.reported == [] and ex.mentions[0].subject == "third_party"


def test_uncertain_symptom_is_reported_but_marked():
    ex = extract("I think I might have a fever")
    assert statuses(ex) == {("fever", "uncertain")}
    assert [m.term for m in ex.reported] == ["fever"]
    assert ex.mentions[0].review_required


def test_mixed_clauses_keep_each_symptom_in_its_own_status():
    ex = extract("I had fever last week and now I have a cough. My mother has a headache and fever.")
    assert ("fever", "historical") in statuses(ex)
    assert ("cough", "current") in statuses(ex)
    assert ("headache", "third_party") in statuses(ex)
    assert ("fever", "third_party") in statuses(ex)


def test_still_having_it_overrides_a_past_marker():
    ex = extract("I have had fever since last week.")
    assert statuses(ex) == {("fever", "current")}


def test_own_symptom_after_mentioning_a_relative_is_the_patients():
    ex = extract("My mother has a headache, but I have a cough.")
    assert ("cough", "current") in statuses(ex) and ("headache", "third_party") in statuses(ex)


def test_relative_in_an_earlier_sentence_does_not_leak():
    ex = extract("I took my mother to the clinic. I have a cough.")
    assert statuses(ex) == {("cough", "current")}


# ---------- attributes ----------

def test_attributes_only_when_stated():
    ex = extract("I have a headache.")
    assert ex.mentions[0].attributes == {}


def test_attributes_stated_in_the_same_clause_are_linked_with_evidence():
    src = "Severe headache every morning when I climb stairs for three days."
    m = extract(src).mentions[0]
    a = m.attributes
    assert a["severity"]["text"] == "Severe"
    assert a["frequency"]["text"] == "every morning"
    assert a["duration"]["text"] == "for three days"
    assert a["triggers"][0]["text"] == "when I climb stairs"
    for key in ("severity", "frequency", "duration"):
        assert src[a[key]["start"]:a[key]["end"]] == a[key]["text"]


def test_attributes_in_other_sentences_are_not_attached():
    ex = extract("I have a headache. It started three days ago and is severe.")
    assert ex.mentions[0].attributes == {}
    assert ex.durations and ex.severity  # still captured globally for staff


def test_shared_clause_details_are_marked_shared():
    m = by_term(extract("I have a cough and fever for three days."), "cough")[0]
    assert m.attributes["duration"]["shared"] is True


def test_severity_goes_to_the_nearest_symptom_only():
    ex = extract("I have a mild fever and cough.")
    assert "severity" in by_term(ex, "fever")[0].attributes
    assert "severity" not in by_term(ex, "cough")[0].attributes


def test_after_three_days_is_not_a_trigger():
    m = extract("Headache after three days of travel").mentions[0]
    assert "triggers" not in m.attributes


# ---------- unknown text, identifiers, review ----------

def test_unmatched_text_is_preserved_verbatim():
    src = "I have a cough. There is a strange pressure behind my eye. Also the parking is bad."
    ex = extract(src)
    kept = {u.text for u in ex.unmatched}
    assert "There is a strange pressure behind my eye" in kept
    assert "Also the parking is bad" in kept
    for u in ex.unmatched:
        assert src[u.start:u.end] == u.text
    assert any("not recognised" in r for r in ex.review_reasons)


def test_symptom_ids_are_internal_and_external_codes_are_not_invented():
    m = extract("I have chest pain").mentions[0]
    assert m.symptom_id == "hs.chest_pain" and m.external_codes == {}


def test_everything_starts_unreviewed():
    ex = extract("fever and cough")
    assert ex.review_required and all(m.review_status == "unreviewed" for m in ex.mentions)


def test_summary_mentions_past_and_other_person_separately():
    s = summarize(extract("I had fever last week. My mother has a headache. I have a cough."))
    assert "PAST" in s and "ANOTHER PERSON" in s and "Reported: cough" in s


# ---------- department suggestion ----------

RULES = [
    Rule("1", "route", "knee pain", 6, "d-ortho", "orthopaedics", "Orthopaedics"),
    Rule("2", "route", "cough", 4, "d-pulm", "pulmonology", "Pulmonology"),
    Rule("3", "route", "sore throat", 4, "d-ent", "ent", "ENT"),
    Rule("4", "route", "fever", 3, "d-gm", "general_medicine", "General Medicine"),
    Rule("5", "attention", "chest pain", 1, None, None, None),
]
DEFAULT = ("d-gm", "general_medicine", "General Medicine")


def test_historical_symptom_does_not_route():
    s = suggest("I had a cough last year.", RULES, DEFAULT)
    assert s.status == "default" and s.candidates == []
    assert [x.reason for x in s.excluded] == ["historical"]


def test_third_party_symptom_does_not_route():
    s = suggest("My father has knee pain.", RULES, DEFAULT)
    assert s.status == "default" and [x.reason for x in s.excluded] == ["third_party"]


def test_negated_symptom_is_listed_as_excluded():
    s = suggest("No cough, but I have knee pain.", RULES, DEFAULT)
    assert s.department_code == "orthopaedics"
    assert {x.reason for x in s.excluded} == {"negated"}


def test_current_symptom_wins_over_past_one():
    s = suggest("I had knee pain last year. Now I have a cough.", RULES, DEFAULT)
    assert s.status == "matched" and s.department_code == "pulmonology"


def test_uncertain_symptom_still_routes_but_asks_for_review():
    s = suggest("Maybe I have a cough.", RULES, DEFAULT)
    assert s.department_code == "pulmonology"
    assert any("uncertainty" in r for r in s.review_reasons) and s.review_required


def test_text_without_health_content_is_out_of_scope():
    s = suggest("Where is the parking lot? I want to book a taxi.", RULES, DEFAULT)
    assert s.status == "out_of_scope" and s.department_id is None and s.candidates == []


def test_vague_health_text_defaults_but_is_labelled():
    s = suggest("I feel a bit off today.", RULES, DEFAULT)
    assert s.status == "default" and s.review_required


def test_ambiguous_tie_has_no_department():
    s = suggest("Cough and sore throat.", RULES, DEFAULT)
    assert s.status == "ambiguous" and s.department_id is None and s.score_margin == 0


def test_close_scores_are_flagged():
    rules = [Rule("1", "route", "knee pain", 6, "d-ortho", "orthopaedics", "Orthopaedics"),
             Rule("2", "route", "cough", 5, "d-pulm", "pulmonology", "Pulmonology")]
    s = suggest("Knee pain and a cough.", rules, DEFAULT)
    assert s.status == "matched" and s.score_margin == 1
    assert any("Close scores" in r for r in s.review_reasons)


def test_never_final_and_no_made_up_confidence():
    s = suggest("Knee pain.", RULES, DEFAULT).to_dict()
    assert s["review_required"] is True and s["review_status"] == "pending_staff_review"
    assert s["confidence"] is None and "calibrated" in s["confidence_note"]


def test_attention_hit_carries_its_context():
    s = suggest("My brother has chest pain.", RULES, DEFAULT)
    assert [(a.evidence, a.context) for a in s.attention] == [("chest pain", "third_party")]
    assert suggest("I do not have chest pain.", RULES, DEFAULT).attention == []


def test_pluggable_classifier_interface():
    from app.ai import department_classification as dc

    original = dc.get_classifier()

    class Fixed:
        name = "fixed-test"

        def suggest(self, source_text, rules, default):
            return dc.Suggestion("default", None, None, None, [], [], "x", classifier=self.name)

    dc.register_classifier(Fixed())
    try:
        assert suggest("anything", RULES, DEFAULT).classifier == "fixed-test"
    finally:
        dc.register_classifier(original)


# ---------- "high" as a severity word ----------

def test_high_fever_records_high_as_severity():
    ex = extract("I have a high fever for three days.")
    fever = by_term(ex, "fever")[0]
    assert fever.attributes["severity"]["text"].lower() == "high"
    assert [e.text.lower() for e in ex.severity] == ["high"]


def test_high_inside_a_symptom_name_is_not_a_severity():
    ex = extract("I have a high temperature.")
    assert by_term(ex, "fever") and "severity" not in by_term(ex, "fever")[0].attributes
    assert ex.severity == []
