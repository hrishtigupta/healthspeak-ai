"""Cheap safety checks on a machine translation (Hindi/Urdu -> English).

These do NOT prove a translation is right. They only raise a flag for staff when
something that matters clinically looks like it may have been lost: a negation
("no fever") or a number ("3 days"). The original text is always kept and shown.
"""

import re
import unicodedata

# Whole-word negation markers. Bare particles such as "ना" / "न" are left out on purpose:
# they are also tag-question and emphasis words, so they would flag far too often.
_NEGATION_ORIGINAL = {
    "नहीं", "नही", "नहि", "बिना",  # Hindi
    "نہیں", "نہی", "بغیر",  # Urdu
}
_NEGATION_ENGLISH = re.compile(
    r"\b(?:no|not|never|without|none|neither|nor|denies|deny|cannot|can't|don't|doesn't|didn't|"
    r"haven't|hasn't|isn't|aren't|wasn't|won't|free of)\b|n't\b", re.IGNORECASE)
_WORD = re.compile(r"[\wऀ-ॿ؀-ۿ]+")

MACHINE_TRANSLATION_NOTE = ("The English text is a machine translation of the patient's original "
                            "words. Check it against the original before relying on it.")
NEGATION_WARNING = ("The original text contains a negation word (such as 'no' / 'not') but the English "
                    "translation does not. A 'no' may have been lost - read the original.")
NUMBER_WARNING = ("The numbers in the original text are missing from the English translation. A duration or "
                  "quantity may have been changed - read the original.")


ROMANIZED_WARNING = ("This text was submitted as Hindi/Urdu but is written in English (Latin) letters, e.g. "
                     "'bukhar nahi hai'. The translation model expects Devanagari or Urdu script, so the "
                     "English text may be wrong or meaningless - read the original.")
_INDIC_ARABIC_LETTER = re.compile(r"[ऀ-ॿ؀-ۿ]")


def is_romanized(text: str) -> bool:
    """True if the text has several words but no Devanagari/Urdu letters at all."""
    return (not _INDIC_ARABIC_LETTER.search(text)) and len(re.findall(r"[A-Za-z]{2,}", text)) >= 2


_NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
     "eleven", "twelve"])}


def _digits(text: str) -> list[str]:
    """All numbers in the text, with any script's digits mapped to ASCII."""
    out = []
    for run in re.findall(r"\d+", unicodedata.normalize("NFKC", text)):
        out.append("".join(str(unicodedata.digit(c)) for c in run).lstrip("0") or "0")
    return out


def check(original_text: str, english_text: str) -> list[str]:
    """Return human-readable warnings (empty if nothing looks lost)."""
    warnings: list[str] = []
    if is_romanized(original_text):
        warnings.append(ROMANIZED_WARNING)
    original_words = set(_WORD.findall(original_text))
    if original_words & _NEGATION_ORIGINAL and not _NEGATION_ENGLISH.search(english_text):
        warnings.append(NEGATION_WARNING)
    english_numbers = set(_digits(english_text)) | {
        _NUMBER_WORDS[w] for w in re.findall(r"[a-z]+", english_text.lower()) if w in _NUMBER_WORDS}
    if any(n not in english_numbers for n in _digits(original_text)):
        warnings.append(NUMBER_WARNING)
    return warnings
