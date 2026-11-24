"""Patient conversations/intake submission, and staff intake review.

Access (this phase):
- patient: their own conversations and intakes only (others' ids return 404)
- staff:   list, view (audited), correct and confirm intakes
- doctor/admin: not yet (doctors get assigned-patient access with the queue phase)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.enums import ReviewStatus, Role
from app.core.permissions import require_roles
from app.database.models import Conversation, IntakeRecord, Patient, User
from app.database.session import get_db
from app.schemas.intake import (
    ConversationOut,
    IntakeConfirm,
    IntakeCorrection,
    IntakeList,
    IntakePatientView,
    IntakeStaffView,
    MessageCreate,
    MessageExchange,
    MessageOut,
)
from app.services import intake_service, patient_service

router = APIRouter(tags=["intake"])

patient_only = require_roles(Role.PATIENT)
staff_only = require_roles(Role.STAFF)

_ERRORS = {
    intake_service.ConsentMissing: (status.HTTP_403_FORBIDDEN,
                                    "Please give consent before sharing your health concerns."),
    intake_service.ConversationClosed: (status.HTTP_409_CONFLICT, "This conversation has already been submitted."),
    intake_service.TooManyMessages: (status.HTTP_409_CONFLICT,
                                     "This conversation is too long. Please submit it and start a new one."),
    intake_service.NothingToSubmit: (status.HTTP_422_UNPROCESSABLE_CONTENT,
                                     "Please describe your concern before submitting."),
    intake_service.AlreadyConfirmed: (status.HTTP_409_CONFLICT, "This intake is already confirmed."),
    intake_service.EnglishTextNeeded: (status.HTTP_422_UNPROCESSABLE_CONTENT,
                                       "Enter the English version of the patient's words before confirming."),
}


def _fail(exc: Exception):
    code, msg = _ERRORS[type(exc)]
    raise HTTPException(status_code=code, detail=msg) from None


def _my_patient(user: User = Depends(patient_only), db: Session = Depends(get_db)) -> Patient:
    patient = patient_service.get_for_user(db, user)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No patient profile for this account")
    return patient


def _my_conversation(conversation_id: uuid.UUID, patient: Patient = Depends(_my_patient),
                     db: Session = Depends(get_db)) -> Conversation:
    conv = intake_service.get_own_conversation(db, conversation_id, patient)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv


# ---------- patient ----------

@router.post("/conversations", response_model=ConversationOut)
def open_conversation(response: Response, patient: Patient = Depends(_my_patient),
                      user: User = Depends(patient_only), db: Session = Depends(get_db)):
    """Resume the patient's open conversation, or start one (201)."""
    try:
        conv, created = intake_service.open_conversation(db, patient, user)
    except intake_service.ConsentMissing as e:
        _fail(e)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return conv


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def read_conversation(conv: Conversation = Depends(_my_conversation)):
    return conv


@router.post("/conversations/{conversation_id}/messages", response_model=MessageExchange,
             status_code=status.HTTP_201_CREATED)
def send_message(body: MessageCreate, conv: Conversation = Depends(_my_conversation),
                 db: Session = Depends(get_db)) -> MessageExchange:
    try:
        mine, ack = intake_service.add_message(db, conv, body)
    except (intake_service.ConversationClosed, intake_service.TooManyMessages,
            intake_service.ConsentMissing) as e:
        _fail(e)
    return MessageExchange(patient_message=MessageOut.model_validate(mine),
                           assistant_message=MessageOut.model_validate(ack))


@router.post("/conversations/{conversation_id}/submit", response_model=IntakePatientView,
             status_code=status.HTTP_201_CREATED)
def submit_conversation(conv: Conversation = Depends(_my_conversation),
                        user: User = Depends(patient_only), db: Session = Depends(get_db)):
    try:
        return intake_service.submit(db, conv, user)
    except (intake_service.ConversationClosed, intake_service.NothingToSubmit) as e:
        _fail(e)


@router.get("/patients/me/intakes", response_model=list[IntakePatientView])
def my_intakes(patient: Patient = Depends(_my_patient), db: Session = Depends(get_db)):
    return intake_service.list_for_patient(db, patient)


# ---------- staff ----------

def _intake_or_404(intake_id: uuid.UUID, db: Session) -> IntakeRecord:
    intake = intake_service.get(db, intake_id)
    if intake is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intake not found")
    return intake


@router.get("/intakes", response_model=IntakeList)
def list_intakes(review_status: ReviewStatus | None = None,
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                 _: User = Depends(staff_only), db: Session = Depends(get_db)) -> IntakeList:
    return intake_service.list_for_staff(db, review_status=review_status, limit=limit, offset=offset)


@router.get("/intakes/{intake_id}", response_model=IntakeStaffView)
def read_intake(intake_id: uuid.UUID, staff: User = Depends(staff_only),
                db: Session = Depends(get_db)) -> IntakeStaffView:
    return intake_service.staff_view(db, _intake_or_404(intake_id, db), staff)


@router.patch("/intakes/{intake_id}", response_model=IntakeStaffView)
def correct_intake(intake_id: uuid.UUID, body: IntakeCorrection, staff: User = Depends(staff_only),
                   db: Session = Depends(get_db)) -> IntakeStaffView:
    intake = intake_service.correct(db, _intake_or_404(intake_id, db), staff, body.final_text, body.reason)
    return intake_service.staff_view(db, intake, staff)


@router.post("/intakes/{intake_id}/confirm", response_model=IntakeStaffView)
def confirm_intake(intake_id: uuid.UUID, body: IntakeConfirm, staff: User = Depends(staff_only),
                   db: Session = Depends(get_db)) -> IntakeStaffView:
    try:
        intake = intake_service.confirm(db, _intake_or_404(intake_id, db), staff,
                                        body.final_text, body.reason)
    except (intake_service.AlreadyConfirmed, intake_service.EnglishTextNeeded) as e:
        _fail(e)
    return intake_service.staff_view(db, intake, staff)
