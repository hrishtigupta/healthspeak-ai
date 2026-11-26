"""The ONE definition of "urgent", shared by the chat assistant and the saved intake priority.

These are the existing emergency rules, moved here unchanged so both places always agree:
- a patient-reported (current or uncertain) red-flag symptom, or
- a hospital "attention" routing rule that fired on a current/uncertain mention.

Nothing here is new medical criteria, and none of it diagnoses: it only decides whether to show
emergency guidance and to flag the intake for staff first.
"""

# Reported terms that always get emergency guidance instead of more questions.
RED_FLAG_TERMS = frozenset({"chest pain", "breathing difficulty", "fainting"})


def attention_fired(attention: list[dict] | None) -> bool:
    """True if a hospital attention rule matched a current/uncertain (not denied/past) mention."""
    return any(a.get("context") in ("current", "uncertain") for a in (attention or []))


def is_urgent(reported_terms, attention: list[dict] | None = None) -> bool:
    return bool(set(reported_terms) & RED_FLAG_TERMS) or attention_fired(attention)
