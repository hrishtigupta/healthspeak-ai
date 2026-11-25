"""Normalised symptom rows for an intake, and the staff review of them.

AI output (rows created from an analysis) is never edited. Staff decisions are
stored beside it and every change is also appended to intake_revisions, so the
original machine reading and each correction stay auditable.
"""

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.lexicon import SYMPTOMS, symptom_id
from app.core.enums import ReviewStatus, SymptomMatchType, SymptomReviewStatus, SymptomStatus
from app.database.models import ExtractedSymptom, IntakeAnalysis, IntakeRecord, IntakeRevision, User
from app.services import audit_service

MAX_TERM_CHARS = 60


class SymptomNotFound(Exception):
    pass


class SymptomSuperseded(Exception):
    """The symptom belongs to an older analysis; review the latest one instead."""


class IntakeLocked(Exception):
    """The intake is already confirmed; its symptom facts are final."""


class InvalidSymptom(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def latest_analysis(db: Session, intake_id: uuid.UUID) -> IntakeAnalysis | None:
    return db.scalar(select(IntakeAnalysis).where(IntakeAnalysis.intake_id == intake_id)
                     .order_by(IntakeAnalysis.created_at.desc()).limit(1))


def for_analysis(db: Session, analysis_id: uuid.UUID) -> list[ExtractedSymptom]:
    return list(db.scalars(select(ExtractedSymptom).where(ExtractedSymptom.analysis_id == analysis_id)
                           .order_by(ExtractedSymptom.evidence_start, ExtractedSymptom.created_at)))


def for_intake(db: Session, intake_id: uuid.UUID) -> list[ExtractedSymptom]:
    """Symptoms of the intake's LATEST analysis (older analyses stay stored but are superseded)."""
    a = latest_analysis(db, intake_id)
    return for_analysis(db, a.id) if a else []


def _key(term: str, evidence: str | None) -> tuple[str, str]:
    return term.lower(), (evidence or "").strip().lower()


def store_from_analysis(db: Session, intake: IntakeRecord, analysis: IntakeAnalysis,
                        extraction: dict) -> list[ExtractedSymptom]:
    """Create one row per mention. Staff decisions on the previous analysis are carried over
    when the same words were read the same way; staff-added symptoms are carried over always."""
    prev_analysis = db.scalar(select(IntakeAnalysis).where(
        IntakeAnalysis.intake_id == intake.id, IntakeAnalysis.id != analysis.id)
        .order_by(IntakeAnalysis.created_at.desc()).limit(1))
    previous = for_analysis(db, prev_analysis.id) if prev_analysis else []
    carried = {_key(p.term, p.evidence_text): p for p in previous
               if p.review_status != SymptomReviewStatus.UNREVIEWED.value
               and p.match_type != SymptomMatchType.STAFF.value}
    rows: list[ExtractedSymptom] = []
    for m in extraction.get("mentions", []):
        ev = m.get("evidence") or {}
        row = ExtractedSymptom(
            analysis_id=analysis.id, intake_id=intake.id, patient_id=intake.patient_id,
            term=m["term"][:MAX_TERM_CHARS], symptom_code=m.get("symptom_id") or None,
            status=m["status"], subject=m.get("subject", "self"),
            match_type=m.get("match_type", "exact"), evidence_text=ev.get("text"),
            evidence_start=ev.get("start"), evidence_end=ev.get("end"),
            attributes=m.get("attributes") or {},
        )
        old = carried.get(_key(row.term, row.evidence_text))
        if old is not None and old.status == row.status:
            row.review_status, row.confirmed_term = old.review_status, old.confirmed_term
            row.confirmed_status, row.review_note = old.confirmed_status, old.review_note
            row.reviewed_by_user_id, row.reviewed_at = old.reviewed_by_user_id, old.reviewed_at
        rows.append(row)
    for p in previous:
        if p.match_type == SymptomMatchType.STAFF.value:
            rows.append(ExtractedSymptom(
                analysis_id=analysis.id, intake_id=intake.id, patient_id=intake.patient_id,
                term=p.term, symptom_code=p.symptom_code, status=p.status, subject=p.subject,
                match_type=p.match_type, evidence_text=p.evidence_text, attributes=p.attributes or {},
                review_status=p.review_status, confirmed_term=p.confirmed_term,
                confirmed_status=p.confirmed_status, review_note=p.review_note,
                reviewed_by_user_id=p.reviewed_by_user_id, reviewed_at=p.reviewed_at))
    db.add_all(rows)
    return rows


# ---------- staff review ----------

def _snapshot(s: ExtractedSymptom) -> str:
    return json.dumps({"term": s.effective_term, "status": s.effective_status,
                       "review": s.review_status}, sort_keys=True)


def _check_editable(db: Session, intake: IntakeRecord) -> IntakeAnalysis:
    if intake.review_status == ReviewStatus.CONFIRMED.value:
        raise IntakeLocked
    analysis = latest_analysis(db, intake.id)
    if analysis is None:
        raise SymptomNotFound
    return analysis


def _audit(db: Session, intake: IntakeRecord, staff: User, action: str, symptom: ExtractedSymptom,
           old: str | None, note: str | None) -> None:
    db.add(IntakeRevision(intake=intake, field="symptom", old_value=old, new_value=_snapshot(symptom),
                          reason=note, edited_by_user_id=staff.id))
    audit_service.record(db, f"symptom.{action}", actor_user_id=staff.id, target_type="intake",
                         target_id=intake.id, details={"symptom_id": str(symptom.id)})


def review(db: Session, intake: IntakeRecord, symptom_id_: uuid.UUID, staff: User, *, action: str,
           term: str | None = None, status: str | None = None, note: str | None = None
           ) -> ExtractedSymptom:
    """action: confirm | reject | correct. Staff decisions never touch the AI columns."""
    analysis = _check_editable(db, intake)
    s = db.get(ExtractedSymptom, symptom_id_)
    if s is None or s.intake_id != intake.id:
        raise SymptomNotFound
    if s.analysis_id != analysis.id:
        raise SymptomSuperseded
    old = _snapshot(s)
    if action == "confirm":
        s.review_status, s.confirmed_term, s.confirmed_status = SymptomReviewStatus.CONFIRMED.value, None, None
    elif action == "reject":
        s.review_status, s.confirmed_term, s.confirmed_status = SymptomReviewStatus.REJECTED.value, None, None
    elif action == "correct":
        new_term = _clean_term(term) if term else None
        if status is not None and status not in {x.value for x in SymptomStatus}:
            raise InvalidSymptom
        if new_term is None and status is None:
            raise InvalidSymptom
        s.review_status = SymptomReviewStatus.CORRECTED.value
        s.confirmed_term = new_term if new_term and new_term != s.term else s.confirmed_term
        s.confirmed_status = status if status and status != s.status else s.confirmed_status
    else:
        raise InvalidSymptom
    s.review_note = note
    s.reviewed_by_user_id, s.reviewed_at = staff.id, _now()
    _audit(db, intake, staff, action, s, old, note)
    db.commit()
    db.refresh(s)
    return s


def _clean_term(term: str) -> str:
    t = " ".join(term.split()).lower()
    if not t or len(t) > MAX_TERM_CHARS:
        raise InvalidSymptom
    return t


def add_staff_symptom(db: Session, intake: IntakeRecord, staff: User, *, term: str, status: str,
                      evidence_text: str | None, note: str | None) -> ExtractedSymptom:
    """Staff record a symptom the system missed (e.g. from unmatched text)."""
    analysis = _check_editable(db, intake)
    if status not in {x.value for x in SymptomStatus}:
        raise InvalidSymptom
    t = _clean_term(term)
    s = ExtractedSymptom(
        analysis_id=analysis.id, intake_id=intake.id, patient_id=intake.patient_id, term=t,
        symptom_code=symptom_id(t) if t in SYMPTOMS else None, status=status,
        subject="third_party" if status == SymptomStatus.THIRD_PARTY.value else "self",
        match_type=SymptomMatchType.STAFF.value, evidence_text=(evidence_text or None),
        attributes={}, review_status=SymptomReviewStatus.CONFIRMED.value,
        reviewed_by_user_id=staff.id, reviewed_at=_now(), review_note=note)
    db.add(s)
    db.flush()
    _audit(db, intake, staff, "added", s, None, note)
    db.commit()
    db.refresh(s)
    return s
