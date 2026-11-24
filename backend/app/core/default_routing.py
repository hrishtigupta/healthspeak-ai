"""Default departments and routing rules loaded by `python -m app.seed`.

*** DRAFT — must be reviewed and adapted by the hospital's clinical team. ***
Administrators can change everything here at runtime through /api/admin/departments
and /api/admin/routing-rules; this file is only the starting point.

Route rules: phrase -> department, weight 1-10 (higher = stronger signal).
Attention rules: phrases hospital policy marks for PROMPT STAFF ATTENTION. They
raise a visible flag for staff; they are not a triage decision or a diagnosis.
"""

DEPARTMENTS = [
    # code, name, is_default
    ("general_medicine", "General Medicine", True),
    ("cardiology", "Cardiology", False),
    ("pulmonology", "Pulmonology", False),
    ("gastroenterology", "Gastroenterology", False),
    ("orthopaedics", "Orthopaedics", False),
    ("neurology", "Neurology", False),
    ("ent", "ENT (Ear, Nose and Throat)", False),
    ("dermatology", "Dermatology", False),
    ("ophthalmology", "Ophthalmology", False),
    ("urology", "Urology", False),
    ("dental", "Dental", False),
    ("psychiatry", "Psychiatry", False),
]

ROUTE_RULES = {
    "general_medicine": [("fever", 3), ("tired", 1), ("weakness", 1), ("weight loss", 2), ("vomiting", 1)],
    "cardiology": [("chest pain", 6), ("palpitations", 6), ("heart racing", 5), ("chest tightness", 5),
                   ("fast heartbeat", 5)],
    "pulmonology": [("cough", 4), ("shortness of breath", 6), ("breathless", 6), ("difficulty breathing", 6),
                    ("wheezing", 5), ("short of breath", 6)],
    "gastroenterology": [("stomach pain", 6), ("abdominal pain", 6), ("stomach ache", 6), ("nausea", 3),
                         ("diarrhoea", 5), ("diarrhea", 5), ("loose motions", 5), ("constipation", 5),
                         ("vomiting", 3)],
    "orthopaedics": [("knee pain", 6), ("back pain", 5), ("joint pain", 5), ("fracture", 7), ("sprain", 6),
                     ("neck pain", 4), ("fell down", 4), ("swollen", 2)],
    "neurology": [("headache", 4), ("migraine", 6), ("dizzy", 3), ("dizziness", 3), ("numbness", 5),
                  ("tingling", 4), ("fainted", 5), ("seizure", 7)],
    "ent": [("sore throat", 5), ("ear pain", 6), ("earache", 6), ("hearing loss", 6), ("runny nose", 3),
            ("blocked nose", 4), ("ringing in my ears", 5)],
    "dermatology": [("rash", 6), ("itching", 5), ("itchy", 4), ("hives", 6), ("skin", 3)],
    "ophthalmology": [("blurred vision", 6), ("blurry vision", 6), ("eye pain", 6), ("red eyes", 5)],
    "urology": [("burning urination", 6), ("painful urination", 6), ("pain when urinating", 6),
                ("blood in urine", 7)],
    "dental": [("toothache", 7), ("tooth pain", 7), ("gum", 4)],
    "psychiatry": [("anxiety", 5), ("anxious", 4), ("depressed", 5), ("panic attack", 5),
                   ("can't sleep", 2)],
}

ATTENTION_PHRASES = [
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing", "unconscious", "fainted",
    "passed out", "seizure", "severe bleeding", "bleeding heavily", "vomiting blood", "suicidal",
    "kill myself", "pregnant and bleeding", "stroke", "face drooping", "slurred speech",
]
