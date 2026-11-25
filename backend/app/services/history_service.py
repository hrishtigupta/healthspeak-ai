"""A verified patient's earlier encounters (intake records) and their symptoms.

Rules:
- Lookup is ONLY by patient_id (a verified record), never by name or phone.
- Read-only: earlier encounters are never modified; each submission is its own intake.
- The history is assembled at read time. It is not copied into new encounters.
- Staff-confirmed facts and AI-extracted (unconfirmed) facts are labelled differently.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import SymptomReviewStatus, SymptomStatus
from app.database.models import ExtractedSymptom, IntakeRecord
from app.schemas.history import (
    HistoryEncounter,
    HistoryOut,
    HistorySymptom,
    PatientEncounterView,
    PatientHistoryOut,
    RecurrenceRef,
    RecurringSymptom,
)
from app.services import symptom_service

STATEMENT_CHARS = 300
RECURRENCE_SCAN = 50  # how many earlier encounters are scanned for recurring symptoms
_ACTIVE_STATUSES = {SymptomStatus.CURRENT.value, SymptomStatus.UNCERTAIN.value}
_DETAIL_KEYS = ("severity", "duration", "frequency", "timing")


def _details(attributes: dict) -> dict[str, str]:
    out = {k: attributes[k]["text"] for k in _DETAIL_KEYS if isinstance(attributes.get(k), dict)
           and attributes[k].get("text")}
    triggers = attributes.get("triggers")
    if triggers:
        out["triggers"] = "; ".join(t["text"] for t in triggers if t.get("text"))
    return out


def _symptom_view(s: ExtractedSymptom) -> HistorySymptom:
    return HistorySymptom(
        term=s.effective_term, symptom_code=s.symptom_code if not s.confirmed_term else None,
        status=s.effective_status,
        source="staff_confirmed" if s.is_staff_confirmed else "ai_unconfirmed",
        evidence_text=s.evidence_text, details=_details(s.attributes or {}))


def _query(patient_id: uuid.UUID, before: datetime | None, exclude: uuid.UUID | None):
    cond = [IntakeRecord.patient_id == patient_id]
    if before is not None:
        cond.append(IntakeRecord.created_at < before)
    if exclude is not None:
        cond.append(IntakeRecord.id != exclude)
    return cond


def _page(db: Session, patient_id: uuid.UUID, *, before: datetime | None, exclude: uuid.UUID | None,
          limit: int, offset: int) -> tuple[list[IntakeRecord], int]:
    cond = _query(patient_id, before, exclude)
    total = db.scalar(select(func.count()).select_from(IntakeRecord).where(*cond)) or 0
    rows = list(db.scalars(select(IntakeRecord).where(*cond)
                           .order_by(IntakeRecord.created_at.desc(), IntakeRecord.id)
                           .limit(limit).offset(offset)))
    return rows, total


def _symptoms_by_intake(db: Session, intakes: list[IntakeRecord]) -> dict[uuid.UUID, list[ExtractedSymptom]]:
    """Symptoms from each intake's latest analysis, minus ones staff rejected or that
    were about someone else. One query for the whole page."""
    latest = {i.id: i.analyses[-1].id for i in intakes if i.analyses}
    out: dict[uuid.UUID, list[ExtractedSymptom]] = {i.id: [] for i in intakes}
    if not latest:
        return out
    rows = db.scalars(select(ExtractedSymptom).where(ExtractedSymptom.analysis_id.in_(latest.values()))
                      .order_by(ExtractedSymptom.evidence_start))
    for s in rows:
        if s.review_status == SymptomReviewStatus.REJECTED.value:
            continue
        if s.effective_status == SymptomStatus.THIRD_PARTY.value:
            continue
        out[s.intake_id].append(s)
    return out


def _statement(i: IntakeRecord) -> str:
    text = i.final_text or i.english_text or i.original_text
    return text if len(text) <= STATEMENT_CHARS else text[:STATEMENT_CHARS] + "…"


def _encounter(i: IntakeRecord, symptoms: list[ExtractedSymptom]) -> HistoryEncounter:
    a = i.analyses[-1] if i.analyses else None
    ex = a.extraction if a else {}
    return HistoryEncounter(
        intake_id=i.id, encounter_date=i.created_at, original_language=i.original_language,
        review_status=i.review_status, reviewed_at=i.reviewed_at,
        confirmed_department=i.confirmed_department_name,
        ai_suggested_department=(a.suggestion.get("department_name") if a else None),
        statement=_statement(i), symptoms=[_symptom_view(s) for s in symptoms],
        medication_mentions=list(ex.get("medication_mentions", [])),
        allergy_mentions=list(ex.get("allergy_mentions", [])))


def for_patient(db: Session, patient_id: uuid.UUID, *, before: datetime | None = None,
                exclude_intake_id: uuid.UUID | None = None, limit: int = 10, offset: int = 0
                ) -> HistoryOut:
    """Earlier encounters, newest first, for staff. `before`/`exclude` narrow it to what
    came before a given intake."""
    intakes, total = _page(db, patient_id, before=before, exclude=exclude_intake_id,
                           limit=limit, offset=offset)
    syms = _symptoms_by_intake(db, intakes)
    return HistoryOut(patient_id=patient_id, total=total, limit=limit, offset=offset,
                      encounters=[_encounter(i, syms[i.id]) for i in intakes])


def for_intake(db: Session, intake: IntakeRecord, *, limit: int = 5, offset: int = 0) -> HistoryOut:
    """Earlier encounters of the SAME verified patient as `intake`, plus recurring symptoms."""
    out = for_patient(db, intake.patient_id, before=intake.created_at, exclude_intake_id=intake.id,
                      limit=limit, offset=offset)
    out.recurring = recurring(db, intake)
    return out


def recurring(db: Session, intake: IntakeRecord) -> list[RecurringSymptom]:
    """Terms the patient reports now that also appeared in earlier encounters. Context for
    staff only: it does not change extraction or the department suggestion."""
    now = {s.effective_term: s for s in symptom_service.for_intake(db, intake.id)
           if s.effective_status in _ACTIVE_STATUSES and s.review_status != SymptomReviewStatus.REJECTED.value}
    if not now:
        return []
    prior, _ = _page(db, intake.patient_id, before=intake.created_at, exclude=intake.id,
                     limit=RECURRENCE_SCAN, offset=0)
    syms = _symptoms_by_intake(db, prior)
    refs: dict[str, list[RecurrenceRef]] = {}
    for i in prior:
        for s in syms[i.id]:
            if s.effective_term in now and s.effective_status != SymptomStatus.NEGATED.value:
                refs.setdefault(s.effective_term, []).append(RecurrenceRef(
                    intake_id=i.id, encounter_date=i.created_at, status=s.effective_status,
                    source="staff_confirmed" if s.is_staff_confirmed else "ai_unconfirmed"))
    return [RecurringSymptom(term=t, previous=r) for t, r in sorted(refs.items())]


def for_own_account(db: Session, patient_id: uuid.UUID, *, limit: int, offset: int) -> PatientHistoryOut:
    """Patient-facing: only what staff confirmed. No AI suggestions or unconfirmed readings."""
    intakes, total = _page(db, patient_id, before=None, exclude=None, limit=limit, offset=offset)
    syms = _symptoms_by_intake(db, intakes)
    views = []
    for i in intakes:
        confirmed = [_symptom_view(s) for s in syms[i.id]
                     if s.is_staff_confirmed and s.effective_status != SymptomStatus.NEGATED.value]
        views.append(PatientEncounterView(
            intake_id=i.id, encounter_date=i.created_at, review_status=i.review_status,
            confirmed_department=i.confirmed_department_name,
            # Only text a patient wrote or staff reviewed; never an unreviewed translation.
            statement=(i.final_text or i.original_text)[:STATEMENT_CHARS],
            confirmed_symptoms=confirmed))
    return PatientHistoryOut(total=total, limit=limit, offset=offset, encounters=views)
