"""Departments (read for staff/doctors/admins) and routing-rule configuration (admins)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.permissions import require_roles
from app.database.models import Department, RoutingRule, User
from app.database.session import get_db
from app.schemas.department import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    RuleCreate,
    RuleOut,
    RuleUpdate,
)
from app.services import department_service

router = APIRouter(tags=["departments"])

workforce = require_roles(Role.STAFF, Role.DOCTOR, Role.ADMIN)
admin_only = require_roles(Role.ADMIN)


@router.get("/departments", response_model=list[DepartmentOut], dependencies=[Depends(workforce)])
def active_departments(db: Session = Depends(get_db)):
    return department_service.list_departments(db)


# ---------- admin: departments ----------

def _dept_or_404(department_id: uuid.UUID, db: Session) -> Department:
    d = db.get(Department, department_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    return d


@router.get("/admin/departments", response_model=list[DepartmentOut], dependencies=[Depends(admin_only)])
def all_departments(db: Session = Depends(get_db)):
    return department_service.list_departments(db, include_inactive=True)


@router.post("/admin/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(body: DepartmentCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    try:
        return department_service.create_department(db, body, admin)
    except department_service.DuplicateCode:
        raise HTTPException(status.HTTP_409_CONFLICT, "A department with this code already exists") from None


@router.patch("/admin/departments/{department_id}", response_model=DepartmentOut)
def update_department(department_id: uuid.UUID, body: DepartmentUpdate, admin: User = Depends(admin_only),
                      db: Session = Depends(get_db)):
    return department_service.update_department(db, _dept_or_404(department_id, db), body, admin)


# ---------- admin: routing rules ----------

@router.get("/admin/routing-rules", response_model=list[RuleOut], dependencies=[Depends(admin_only)])
def list_rules(department_id: uuid.UUID | None = None, kind: Literal["route", "attention"] | None = None,
               db: Session = Depends(get_db)):
    return [department_service.rule_out(r)
            for r in department_service.list_rules(db, department_id=department_id, kind=kind)]


@router.post("/admin/routing-rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(body: RuleCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    try:
        return department_service.rule_out(department_service.create_rule(db, body, admin))
    except department_service.UnknownDepartment:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown or inactive department") from None


@router.patch("/admin/routing-rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: uuid.UUID, body: RuleUpdate, admin: User = Depends(admin_only),
                db: Session = Depends(get_db)):
    rule = db.get(RoutingRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    return department_service.rule_out(department_service.update_rule(db, rule, body, admin))
