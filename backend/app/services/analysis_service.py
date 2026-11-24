"""Run the rule-based extraction + department suggestion for an intake.

Output is stored as an append-only IntakeAnalysis and is always UNCONFIRMED
machine output until a staff member confirms the intake.
"""

import hashlib

from sqlalchemy.orm import Session

from app.ai import department_classification, text_processing
from app.database.models import IntakeAnalysis, IntakeRecord, User
from app.services import audit_service, department_service


class NoTextToAnalyse(Exception):
    pass


def analyse(db: Session, intake: IntakeRecord, *, source: str = "english_text",
            actor: User | None = None) -> IntakeAnalysis:
    text = intake.final_text if source == "final_text" else intake.english_text
    if not text:
        raise NoTextToAnalyse
    extraction = text_processing.extract(text)
    summary = text_processing.summarize(extraction)
    default = department_service.default_department(db)
    suggestion = department_classification.suggest(
        text, department_service.active_rules(db),
        (str(default.id), default.code, default.name) if default else None,
    )
    rec = IntakeAnalysis(
        intake=intake, source=source,
        source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        extraction=extraction.to_dict(), summary=summary, suggestion=suggestion.to_dict(),
        suggested_department_id=suggestion.department_id, needs_attention=bool(suggestion.attention),
        engine_version=f"{extraction.engine_version}/{extraction.lexicon_version}",
        ruleset_version=suggestion.ruleset_version,
        created_by_user_id=actor.id if actor else None,
    )
    db.add(rec)
    db.flush()
    audit_service.record(db, "intake.analysed", actor_user_id=actor.id if actor else None,
                         target_type="intake", target_id=intake.id,
                         details={"source": source, "status": suggestion.status,
                                  "attention": rec.needs_attention})
    db.commit()
    db.refresh(rec)
    return rec


def analyse_if_possible(db: Session, intake: IntakeRecord, actor: User | None = None) -> None:
    """Called automatically once English text exists. Never blocks the submission."""
    if intake.english_text:
        try:
            analyse(db, intake, source="english_text", actor=actor)
        except Exception:  # noqa: BLE001 - analysis is advisory; never lose the intake
            db.rollback()
            import logging

            logging.getLogger(__name__).exception("Automatic intake analysis failed")


def latest(intake: IntakeRecord) -> IntakeAnalysis | None:
    return intake.analyses[-1] if intake.analyses else None
