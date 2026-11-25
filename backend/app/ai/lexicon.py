"""Approved symptom vocabulary (English) used to recognise what a patient REPORTED.

Each canonical term lists the plain-language phrases patients commonly use.
Matching is literal (whole words, case-insensitive): nothing is inferred, and a
term is only extracted when one of its phrases actually appears in the text.

*** DRAFT vocabulary — to be reviewed and extended by the clinical team. ***
Bump LEXICON_VERSION whenever this list changes (it is stored with each analysis).
"""

LEXICON_VERSION = "lex-2026-11-25"

SYMPTOMS: dict[str, list[str]] = {
    "fever": ["fever", "feverish", "high temperature"],
    "cough": ["cough", "coughing", "dry cough", "wet cough"],
    "sore throat": ["sore throat", "throat pain", "pain in my throat", "throat hurts"],
    "runny or blocked nose": ["runny nose", "blocked nose", "stuffy nose", "sneezing"],
    "headache": ["headache", "head ache", "head pain", "head hurts", "migraine"],
    "dizziness": ["dizzy", "dizziness", "lightheaded", "light-headed", "giddiness", "vertigo"],
    "fainting": ["fainted", "fainting", "passed out", "blacked out", "unconscious"],
    "chest pain": ["chest pain", "pain in my chest", "chest hurts", "chest tightness", "tight chest"],
    "palpitations": ["palpitations", "heart racing", "racing heart", "heart pounding", "fast heartbeat"],
    "breathing difficulty": ["shortness of breath", "short of breath", "breathless", "breathlessness",
                             "difficulty breathing", "trouble breathing", "can't breathe",
                             "cannot breathe", "breathing problem", "wheezing"],
    "stomach pain": ["stomach pain", "stomach ache", "stomachache", "abdominal pain", "belly pain",
                     "tummy pain", "pain in my stomach", "stomach hurts"],
    "nausea": ["nausea", "nauseous", "feel sick", "feeling sick"],
    "vomiting": ["vomiting", "vomited", "throwing up", "threw up", "vomit"],
    "diarrhoea": ["diarrhoea", "diarrhea", "loose motions", "loose stools", "watery stools"],
    "constipation": ["constipation", "constipated"],
    "burning urination": ["burning urination", "burning when urinating", "pain when urinating",
                          "painful urination", "burning while passing urine"],
    "back pain": ["back pain", "backache", "back ache", "lower back pain", "pain in my back"],
    "knee pain": ["knee pain", "pain in my knee", "knee hurts", "knees hurt"],
    "joint pain": ["joint pain", "joints hurt", "pain in my joints"],
    "neck pain": ["neck pain", "stiff neck", "pain in my neck"],
    "injury": ["injury", "injured", "fell down", "fracture", "sprain", "sprained", "twisted my ankle"],
    "swelling": ["swelling", "swollen"],
    "rash": ["rash", "rashes", "skin rash", "red spots", "hives"],
    "itching": ["itching", "itchy", "itch"],
    "ear pain": ["ear pain", "earache", "ear ache", "pain in my ear", "ear hurts"],
    "hearing problem": ["hearing loss", "can't hear", "cannot hear", "ringing in my ears", "ringing in ears"],
    "eye problem": ["blurred vision", "blurry vision", "eye pain", "red eyes", "itchy eyes", "watery eyes"],
    "toothache": ["toothache", "tooth ache", "tooth pain"],
    "weakness": ["weakness", "weak"],
    "tiredness": ["tired", "tiredness", "fatigue", "exhausted", "no energy"],
    "numbness": ["numbness", "numb", "tingling", "pins and needles"],
    "bleeding": ["bleeding", "blood in", "bled"],
    "weight change": ["weight loss", "lost weight", "weight gain", "gained weight"],
    "sleep problem": ["can't sleep", "cannot sleep", "trouble sleeping", "insomnia"],
    "low mood or anxiety": ["anxious", "anxiety", "depressed", "low mood", "panic attack", "panic attacks"],
    "body pain": ["body ache", "body aches", "body pain", "aching all over", "pain all over"],
    "chills": ["chills", "shivering", "shivers"],
    "loss of appetite": ["loss of appetite", "poor appetite", "no appetite", "lost my appetite"],
    "pain (location not stated)": ["pain", "aching", "ache", "hurts"],
}

# Stable internal identifiers ("hs.<term>"). These are NOT SNOMED CT / ICD codes. Mapping to an
# external terminology must be done and validated by a clinical terminologist; until then
# `external_codes` stays empty so we never present guessed codes as standard.
EXTERNAL_CODES: dict[str, dict[str, str]] = {}


def symptom_id(term: str) -> str:
    return "hs." + "_".join(term.replace("(", "").replace(")", "").split())


# Words (>= 6 letters, one edit away from a vocabulary word) that are ordinary English and must
# never be "corrected" into a symptom by the conservative fuzzy matcher.
FUZZY_STOPWORDS = {
    "breeding", "feeding", "leading", "weeding", "seeding", "reading", "heading", "healing",
    "wheeling", "hearing",
}

# Words that suggest the patient is describing a health problem even if we did not recognise it.
HEALTH_CUES = ["pain", "hurt", "hurts", "ache", "sick", "ill", "unwell", "problem", "trouble", "feel",
               "feeling", "bleed", "swell", "swollen", "symptom", "symptoms", "burning", "itch",
               "injury", "wound", "cut", "burn", "weak", "dizzy", "breath", "pregnant", "doctor",
               "medicine", "tablet", "allergy", "infection", "lump", "rash", "fever", "cough"]

# Words that switch a symptom mention into "denied" when they appear shortly before it
# in the same clause ("no fever", "I don't have a cough", "without vomiting").
NEGATION_CUES = [
    "no", "not", "never", "without", "denies", "deny", "don't have", "do not have",
    "didn't have", "did not have", "haven't had", "have not had", "hasn't", "has not", "none",
    "no longer", "free of",
]

SEVERITY_WORDS = ["mild", "slight", "moderate", "severe", "very bad", "bad", "terrible", "unbearable",
                  "intense", "extreme", "worst", "sharp", "dull"]

UNCERTAINTY_WORDS = ["maybe", "might", "not sure", "i think", "perhaps", "possibly", "sometimes",
                     "on and off", "comes and goes", "i don't know", "not certain"]

MEDICATION_WORDS = ["tablet", "tablets", "medicine", "medicines", "medication", "medications", "syrup",
                    "capsule", "capsules", "injection", "inhaler", "paracetamol", "ibuprofen",
                    "antibiotic", "antibiotics", "painkiller", "painkillers", "taking", "took"]

ALLERGY_WORDS = ["allergy", "allergies", "allergic"]
