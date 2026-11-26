"""Transparent evidence labels for extracted fields (what the intake review screen shows as "confidence").

No percentages: the extractor is rule-based, so a number would be made up. Instead each field says HOW it
was found, using the metadata we already store:

  exact     the patient's own words matched a known term exactly
  possible  matched with spelling tolerance (a one-typo variant), so staff should check it
  staff     added or corrected by a staff member (never shown as an original AI extraction)
  missing   nothing found for this field

A symptom the patient was unsure about, or one read from a machine translation, carries an extra note.
These labels help staff see what needs attention. They do not say anything about clinical certainty.
"""

from app.core.enums import SymptomMatchType, SymptomReviewStatus, TranslationStatus

LABELS = {
    "exact": "Exact match",
    "possible": "Possible match",
    "staff": "Added or corrected by staff",
    "missing": "Not found",
    "rejected": "Rejected by staff",
}


def symptom_evidence(*, match_type: str, review_status: str, status: str, term: str,
                     effective_term: str) -> dict:
    """Evidence for ONE extracted symptom, from existing columns only."""
    notes: list[str] = []
    confirmed = review_status == SymptomReviewStatus.CONFIRMED.value
    if review_status == SymptomReviewStatus.REJECTED.value:
        level = "rejected"
    elif match_type == SymptomMatchType.STAFF.value:
        level = "staff"
        notes.append("Added by a staff member; not an AI extraction.")
    elif review_status == SymptomReviewStatus.CORRECTED.value:
        level = "staff"
        notes.append(f"The AI read this as '{term}'; staff corrected it to '{effective_term}'.")
    elif match_type == SymptomMatchType.FUZZY.value:
        level = "possible"
        notes.append("Matched a spelling variant of the patient's words: check it against the original.")
    else:
        level = "exact"
    if status == "uncertain":
        notes.append("The patient sounded unsure about this.")
    if confirmed:
        notes.append("Confirmed by staff.")
    return {"level": level, "label": LABELS[level], "confirmed_by_staff": confirmed, "notes": notes}


def _worst(levels: list[str]) -> str:
    for level in ("possible", "staff", "exact"):  # the field most in need of a look wins
        if level in levels:
            return level
    return "missing"


def field_evidence(*, symptoms, analysis, translation_status: str, confirmed_department) -> list[dict]:
    """One row per extracted field for the staff review screen (symptoms, duration, severity, ...)."""
    live = [s for s in symptoms if s.review_status != SymptomReviewStatus.REJECTED.value]
    machine = translation_status == TranslationStatus.COMPLETED.value
    mt_note = ["Read from a machine translation of the patient's words."] if machine else []
    rows: list[dict] = []

    def row(field: str, level: str, detail: str, notes: list[str] | None = None) -> None:
        rows.append({"field": field, "level": level, "label": LABELS[level], "detail": detail,
                     "notes": notes or []})

    # symptoms
    if live:
        counts = {}
        for s in live:
            lv = symptom_evidence(match_type=s.match_type, review_status=s.review_status, status=s.status,
                                  term=s.term, effective_term=s.effective_term)["level"]
            counts[lv] = counts.get(lv, 0) + 1
        detail = ", ".join(f"{n} {LABELS[k].lower()}" for k, n in counts.items())
        row("symptoms", _worst(list(counts)), detail, mt_note if any(k != "staff" for k in counts) else [])
    else:
        row("symptoms", "missing", "No symptom was found. Read the patient's original words.")

    # duration / severity come from the patient's own words (quoted), so a hit is an exact match
    for key in ("duration", "severity"):
        hits = [s for s in live if (s.attributes or {}).get(key, {}).get("text")]
        if hits:
            quoted = '", "'.join(dict.fromkeys(s.attributes[key]["text"] for s in hits))
            row(key, "exact", f'Patient said: "{quoted}"', mt_note)
        else:
            row(key, "missing", "Not stated by the patient.")

    # medicines / allergies mentioned in the patient's words
    ext = (analysis.extraction if analysis else {}) or {}
    for key, name in (("medication_mentions", "medicines"), ("allergy_mentions", "allergies")):
        found = ext.get(key) or []
        if found:
            row(name, "exact", "Patient mentioned: " + ", ".join(f'"{x}"' for x in found[:5]), mt_note)
        else:
            row(name, "missing", "Not mentioned.")

    # department: advice from the routing rules until staff confirm one
    if confirmed_department is not None:
        row("department", "staff", f"Confirmed by staff: {confirmed_department.name}")
    elif analysis is None:
        row("department", "missing", "No suggestion yet.")
    else:
        sug = analysis.suggestion or {}
        status = sug.get("status")
        if status == "matched":
            row("department", "possible", f"Suggested by the routing rules: {sug.get('department_name')}. "
                "Advice only until staff confirm.")
        elif status == "ambiguous":
            row("department", "missing", "Several departments matched equally: staff must choose.")
        else:
            row("department", "missing", "No symptom pointed to a specific department (default shown).")
    return rows
