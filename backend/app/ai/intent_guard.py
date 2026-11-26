"""Deterministic input-intent guard for the intake chat (no model, no external service).

HealthSpeak AI is a healthcare intake assistant, not a general chatbot. For each patient message this
decides, in order:

  unsafe     requests for instructions to make weapons/explosives or to harm someone
  health     symptoms or health words (or anything we cannot clearly place: the safe default)
  service    appointments, departments, status, how to use the app
  unrelated  clearly off-topic general questions (weather, jokes, sport, trivia, ...)
  greeting   a bare hello

Rules that keep it safe:
- The caller checks emergency symptoms BEFORE using the result: an emergency always wins.
- "health" is the default. A message is only called unrelated/unsafe when a specific pattern matches
  AND no symptom or health word is present, so a sick patient is never turned away.
- It runs on the patient's text in its own script plus the English analysis text (translation or the
  glossary), so Hindi, Urdu and Dogri work through the existing language pipeline. Native lists are a
  safety net for when the translation model is not installed.
- It only classifies. It never produces instructions of any kind.
"""

import re
import unicodedata
from dataclasses import dataclass

GUARD_VERSION = "guard-2026-11-27"

_TOKEN = re.compile(r"[\wऀ-ॿ؀-ۿ]+")  # \w alone would split Devanagari words at vowel signs


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "").lower()
    t = re.sub("[​‌‍‎‏]", "", t)
    return t.replace("ي", "ی").replace("ك", "ک")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(_norm(text))


def _has_phrase(tokens: list[str], phrase: str) -> bool:
    """Whole-word match of a (possibly multi-word) native phrase, so Dogri 'बमारी' never hits 'बम'."""
    p = _TOKEN.findall(_norm(phrase))
    return any(tokens[i:i + len(p)] == p for i in range(len(tokens) - len(p) + 1))


# ------------------------------------------------------------------ English patterns (analysis text)

_HEALTH_CUE = re.compile(
    r"\b(pain|painful|ache|aching|hurt|hurts|hurting|sick|ill|illness|unwell|fever|cough|cold|vomit\w*|nausea|"
    r"dizz\w*|bleed\w*|injur\w*|rash|itch\w*|swell\w*|swollen|breath\w*|chest|stomach|head|headache|symptom\w*|"
    r"medicine\w*|tablet\w*|allerg\w*|diabet\w*|blood pressure|infection|pregnan\w*|burn\w*|fracture\w*|"
    r"emergency|ambulance|faint\w*|weak\w*|tired|diarrh\w*|constipat\w*|throat|ear|eye|tooth|teeth|back|knee|"
    r"joint|skin|urine|urinat\w*|sleep|anxi\w*|depress\w*)\b", re.I)

_UNSAFE_OBJECT = (r"(bombs?|explosives?|grenades?|detonators?|ieds?|pipe bomb|molotov|landmines?|"
                  r"guns?|firearms?|rifles?|ammunition|weapons?|bioweapons?|chemical weapons?|nerve gas)")
_UNSAFE_VERB = (r"(make|making|build|building|create|creating|assemble|assembling|construct\w*|manufactur\w*|"
                r"prepar\w*|synthes\w*|produc\w*|how to|how can i|how do i|how would i|steps? to|instructions?|"
                r"recipe|teach me|show me how)")
_UNSAFE = [
    re.compile(rf"\b{_UNSAFE_VERB}\b[^.?!]{{0,40}}\b{_UNSAFE_OBJECT}\b", re.I),
    re.compile(rf"\b{_UNSAFE_OBJECT}\b[^.?!]{{0,40}}\b(recipe|instructions?|steps)\b", re.I),
    re.compile(r"\b(how|ways?) to (kill|murder|poison|hurt|harm|attack) (someone|somebody|a person|people|"
               r"my (neighbou?r|boss|teacher|wife|husband|friend))\b", re.I),
]

_SERVICE = re.compile(
    r"\b(appointments?|book(ing)?|schedul\w*|reschedul\w*|department\w*|which doctor|doctors? available|"
    r"timings?|opening hours|visiting hours|working hours|where is|location|address|directions?|queue|token|"
    r"my status|status of|check status|how (do|can|to) i? ?(use|login|log in|register|sign up|sign in|reset)|"
    r"forgot (my )?password|help with (the )?(app|application)|how does this (work|app work)|what can you do|"
    r"fees?|charges?|insurance)\b", re.I)
# NOT service words (they are legitimate clinical statements and must stay in the intake):
# "follow-up", "visit", "OPD", "report". The service list stays narrow on purpose.

_UNRELATED = re.compile(
    r"\b(weather|forecast|will it rain|is it raining|jokes?|riddles?|funny story|cricket|football|soccer|ipl|"
    r"world cup|match score|who (will win|won|is winning)|capital of|president of|prime minister|population of|"
    r"movies?|films?|songs?|lyrics|music|actor|actress|celebrity|netflix|recipe|how to (cook|bake)|"
    r"stock market|share price|bitcoin|crypto\w*|elections?|politic\w*|"
    r"write (me )?(a |an )?(poem|code|essay|story|program)|translate this|"
    r"what is \d+ ?[-+*/x×] ?\d+)\b", re.I)

# ------------------------------------------------------------------ native-script safety nets
# Whole-word phrases. Hindi/Dogri (Devanagari) and Urdu. Used in addition to the English patterns.
# Harmful-instruction safety net for the native scripts: an "explosive/weapon" word AND a "make/build" word
# within a few words of each other (word order differs between languages, and "कैसे" etc. may sit between).
_NATIVE_UNSAFE_OBJECTS = {"बम", "विस्फोटक", "हथियार", "بم", "دھماکہ", "ہتھیار"}
_NATIVE_UNSAFE_VERBS = {"बना", "बनाना", "बनाएं", "बनाएँ", "बनाऊं", "बनाऊँ", "बनाने", "बनाओ", "तैयार",
                        "بنانا", "بنائیں", "بناؤں", "بنانے", "بنا", "تیار"}


def _native_unsafe(tokens: list[str]) -> str | None:
    for i, t in enumerate(tokens):
        if t in _NATIVE_UNSAFE_OBJECTS and any(
                v in _NATIVE_UNSAFE_VERBS for v in tokens[max(0, i - 4): i + 5]):
            return t
    return None


_NATIVE_UNRELATED = [
    "मौसम", "चुटकुला", "चुटकुले", "चुटकला", "क्रिकेट", "मैच", "राजधानी", "फिल्म", "फ़िल्म", "गाना", "गाने",
    "रेसिपी", "चुनाव", "शेयर", "کرکٹ", "موسم", "لطیفہ", "لطیفے", "میچ", "دارالحکومت", "فلم", "گانا", "گانے",
    "ریسیپی", "الیکشن",
]
# Deliberately narrow: words like "पता" (address / "I know") or "समय" (time) are also ordinary answers
# to a follow-up question ("पता नहीं"), so they must NOT divert the conversation.
_NATIVE_SERVICE = [
    "अपॉइंटमेंट", "अपाइंटमेंट", "एपॉइंटमेंट", "विभाग", "पासवर्ड", "اپائنٹمنٹ", "اپوائنٹمنٹ", "شعبہ", "پاسورڈ",
]
_NATIVE_HEALTH = [
    "दर्द", "बुखार", "खांसी", "उल्टी", "चक्कर", "बीमार", "बमारी", "तबीयत", "तकलीफ", "परेशानी", "दवा", "दवाई",
    "चोट", "खून", "सांस", "साह", "पीड़", "बेहोश", "कमजोरी", "کھانسی", "بخار", "درد", "الٹی", "چکر", "بیمار",
    "طبیعت", "تکلیف", "دوا", "چوٹ", "خون", "سانس", "کمزوری", "بے ہوش",
]
_GREETING_WORDS = {
    "hi", "hii", "hiii", "hello", "hey", "heya", "good", "morning", "afternoon", "evening", "namaste",
    "namaskar", "salaam", "salam", "assalamualaikum", "greetings", "there", "ji", "sir", "madam",
    "नमस्ते", "नमस्कार", "हेलो", "हैलो", "प्रणाम", "सलाम", "जी", "राम", "सुप्रभात", "शुभ", "प्रभात", "सुबह", "शाम",
    "السلام", "علیکم", "ہیلو", "آداب", "سلام", "جی",
}


@dataclass
class Intent:
    kind: str  # health | service | greeting | unrelated | unsafe
    reason: str = ""


def _native_hit(tokens: list[str], phrases) -> str | None:
    for p in phrases:
        if (_has_phrase(tokens, " ".join(p)) if isinstance(p, list) else _has_phrase(tokens, p)):
            return p if isinstance(p, str) else " ".join(p)
    return None


def classify(native_text: str, analysis_text: str, *, has_symptoms: bool = False) -> Intent:
    """Classify ONE patient message. `has_symptoms`: the extractor found a (reported or denied) symptom."""
    en = _norm(analysis_text if analysis_text else "")
    toks = _tokens(native_text)
    en_toks = _tokens(en)
    all_tokens = toks + [t for t in en_toks if t not in toks]

    health = has_symptoms or bool(_HEALTH_CUE.search(en)) or _native_hit(toks, _NATIVE_HEALTH)
    if health:
        return Intent("health", "symptom or health word present")

    for rx in _UNSAFE:
        if rx.search(en):
            return Intent("unsafe", "harmful-instructions pattern")
    if (hit := _native_unsafe(toks)):
        return Intent("unsafe", f"native pattern: {hit}")

    if _SERVICE.search(en) or _native_hit(toks, _NATIVE_SERVICE):
        return Intent("service", "appointment/department/status/app-help wording")

    if (m := _UNRELATED.search(en)) or (hit := _native_hit(toks, _NATIVE_UNRELATED)):
        return Intent("unrelated", m.group(0) if m else f"native pattern: {hit}")

    if all_tokens and len(all_tokens) <= 8 and all(t in _GREETING_WORDS for t in all_tokens):
        return Intent("greeting", "greeting words only")

    return Intent("health", "default: not clearly off-topic")
