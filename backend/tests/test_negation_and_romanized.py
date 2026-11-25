"""Regression tests: a negated MEDICINE must not negate a symptom, and Latin-script
Hindi/Urdu must raise a translation warning. Synthetic text only; no database."""

import pytest

from app.ai import translation_checks
from app.ai.text_processing import extract

pytestmark = pytest.mark.no_db


def statuses(text):
    return {(m.term, m.status) for m in extract(text).mentions}


@pytest.mark.parametrize("text", [
    "I have not taken azithromycin, the cough has been for three days.",
    "I haven't taken ibuprofen, my back hurts.",
    "I did not take the tablet and I have a headache.",
    "I never started the syrup, cough is bad.",
])
def test_negated_medicine_does_not_negate_the_symptom(text):
    assert all(s == "current" for _, s in statuses(text)), statuses(text)
    assert statuses(text)


@pytest.mark.parametrize("text,expected", [
    ("I do not have fever.", {("fever", "negated")}),
    ("No fever, no cough.", {("fever", "negated"), ("cough", "negated")}),
    ("I don't have a fever, but I have a headache.", {("fever", "negated"), ("headache", "current")}),
])
def test_real_negation_still_works(text, expected):
    assert statuses(text) == expected


def test_romanized_hindi_is_flagged():
    warnings = translation_checks.check("Main Dolo 650 le raha hoon, bukhar nahi hai.", "The main is Dolo 650.")
    assert translation_checks.ROMANIZED_WARNING in warnings


@pytest.mark.parametrize("original", ["मुझे बुखार है", "مجھے بخار ہے", "मुझे fever है", "ok"])
def test_native_script_is_not_flagged(original):
    assert not translation_checks.is_romanized(original)
