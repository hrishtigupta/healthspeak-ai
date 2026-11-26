"""Conservative Hindi -> Dogri SPELLING suggestion for speech transcripts (display aid only).

Why this exists: Whisper has no Dogri. For Dogri audio the app asks it to write Hindi, so the transcript
comes out with Hindi function words ("में", "है", "नहीं") where Dogri has "च", "ऐ", "नेईं". This module
rewrites a small, well-understood set of those words so the SUGGESTED transcript reads more like Dogri.

What it is NOT:
- It is NOT speech recognition and does not make the transcript accurate. Words the speech model got
  wrong stay wrong. The app labels the result "suggested spelling, not verified".
- It never replaces the raw transcript, which is stored and kept unchanged. The patient can edit or
  restore the original; their approved text is what the intake uses.
- It is NOT a translation dictionary. Anything not covered by a rule below is left exactly as it was
  rather than guessed. Rules that could change the meaning only fire in a safe context.

Every rewrite is reported in `changes`, so it can be shown, audited and tested. The function is
deterministic and idempotent (running it twice gives the same text). DRAFT: a fluent Dogri speaker
should review and extend these rules.
"""

import re
import unicodedata
from dataclasses import dataclass, field

NORMALIZER_VERSION = "doi-norm-2026-11-27"

# Split into words and separators so spacing and punctuation are preserved exactly.
_SPLIT = re.compile(r"(\s+|[।,.?!;:\"'()\-])")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Words that are the same job in both languages and never ambiguous: safe to rewrite anywhere.
_ALWAYS = {
    "मुझे": "मिगी", "मुझको": "मिगी",            # to me
    "आपको": "तुसेंगी",                          # to you
    "आपका": "तुंदा", "आपकी": "तुंदी", "आपके": "तुंदे",  # your
    "बहुत": "बौहत",                              # very
    "नहीं": "नेईं", "नही": "नेईं",              # no / not
    "है": "ऐ",                                   # is
    "हूँ": "आं", "हूं": "आं",                    # I am
}

# Multi-word patterns (Hindi progressive tense and "to take"): matched on whole words only.
_PHRASES = [
    (("हो", "रहा", "है"), ("होआ", "करदा", "ऐ")),
    (("हो", "रही", "है"), ("होआ", "करदी", "ऐ")),
    (("आ", "रहा", "है"), ("आवा", "करदा", "ऐ")),
    (("आ", "रही", "है"), ("आवा", "करदी", "ऐ")),
    (("लेने", "में"), ("लैने", "च")),
]

_NUMBERS = {"एक": "इक्क", "तीन": "त्रै", "पांच": "पंज", "पाँच": "पंज", "छह": "छे", "सात": "सत्त",
            "आठ": "अट्ठ", "नौ": "नौं"}  # दो, चार, दस are spelled the same in Dogri
_UNITS = {"दिन": "दिनें", "हफ्ते": "हफ्तें", "महीने": "म्हीनें", "घंटे": "घैंटे"}
# "से" (from/since) becomes "थमां" only after a time word; elsewhere it can mean "with"/"by" and is kept.
_TIME_BEFORE_SE = {"कल", "आज", "सुबह", "रात", "शाम", "कब", "दिन", "दिनों", "हफ्ते", "हफ्तों", "महीने",
                   "महीनों", "घंटे", "घंटों", "साल", "सालों", "कल्ल", "कदूं"}
_SIDES = {"दाएं": "सज्जे", "दाईं": "सज्जे", "दायीं": "सज्जे", "दाहिने": "सज्जे", "दाहिनी": "सज्जे",
          "बाएं": "खब्बे", "बाईं": "खब्बे", "बायीं": "खब्बे", "बायें": "खब्बे"}
_SIDE_NOUN = {"तरफ", "तरफ़", "ओर", "तरफा"}
# "और" (and) -> "ते" only BETWEEN two health words ("बुखार और खांसी"); "और" can also mean "more/other".
_HEALTH_WORDS = {"बुखार", "खांसी", "खाँसी", "दर्द", "सिरदर्द", "उल्टी", "उलटी", "दस्त", "चक्कर", "कमजोरी",
                 "कमज़ोरी", "थकान", "खुजली", "सूजन", "जुकाम", "कब्ज", "घबराहट", "चोट", "बेहोशी", "दाने", "ठंड"}


@dataclass
class Suggestion:
    text: str
    changes: list[dict] = field(default_factory=list)  # [{"from": "में", "to": "च", "rule": "..."}]

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def _norm(token: str) -> str:
    return unicodedata.normalize("NFC", token)


def suggest(text: str | None) -> Suggestion:
    """Return the suggested Dogri-spelled transcript and the list of rewrites. Raw text is never changed."""
    if not text or not _DEVANAGARI.search(text):
        return Suggestion(text or "")
    parts = _SPLIT.split(text)  # words and separators interleaved
    word_idx = [i for i, p in enumerate(parts) if p and not _SPLIT.fullmatch(p)]
    words = [_norm(parts[i]) for i in word_idx]
    out = list(words)
    changes: list[dict] = []

    def record(old: str, new: str, rule: str) -> None:
        changes.append({"from": old, "to": new, "rule": rule})

    n = len(words)
    done = [False] * n  # a word rewritten by a multi-word rule is not rewritten again

    # 1) multi-word phrases
    i = 0
    while i < n:
        for src, dst in _PHRASES:
            if tuple(words[i:i + len(src)]) == src:
                for k, w in enumerate(dst):
                    out[i + k], done[i + k] = w, True
                record(" ".join(src), " ".join(dst), "phrase")
                i += len(src) - 1
                break
        i += 1

    # 2) number + time unit + "से"  ("तीन दिन से" -> "त्रै दिनें थमां")
    for i in range(n - 2):
        if (not any(done[i:i + 3]) and words[i] in _NUMBERS and words[i + 1] in _UNITS
                and words[i + 2] == "से"):
            out[i], out[i + 1], out[i + 2] = _NUMBERS[words[i]], _UNITS[words[i + 1]], "थमां"
            done[i] = done[i + 1] = done[i + 2] = True
            record(" ".join(words[i:i + 3]), " ".join(out[i:i + 3]), "duration")

    # 3) single words, each with its own safety check
    for i, w in enumerate(words):
        if done[i]:
            continue
        prev = words[i - 1] if i > 0 else ""
        nxt = words[i + 1] if i + 1 < n else ""
        new = None
        rule = ""
        if w in _ALWAYS:
            new, rule = _ALWAYS[w], "function word"
        elif w == "में" and i > 0 and prev != "मैं":
            new, rule = "च", "postposition"  # not sentence-initial: that could be the spelling "मैं" (I)
        elif w == "से" and prev in _TIME_BEFORE_SE:
            new, rule = "थमां", "since/from after a time word"
        elif w == "कल" and nxt == "से":
            new, rule = "कल्ल", "yesterday"
        elif w == "कब" and nxt == "से":
            new, rule = "कदूं", "since when"
        elif w in _SIDES and nxt in _SIDE_NOUN:
            new, rule = _SIDES[w], "side"
        elif w in _SIDE_NOUN and prev in _SIDES:
            new, rule = "पासे", "side"
        elif w == "और" and prev in _HEALTH_WORDS and nxt in _HEALTH_WORDS:
            new, rule = "ते", "and between health words"
        if new is not None and new != w:
            out[i] = new
            record(w, new, rule)

    if not changes:
        return Suggestion(text)
    for k, i in enumerate(word_idx):
        parts[i] = out[k]
    return Suggestion("".join(parts), changes)
