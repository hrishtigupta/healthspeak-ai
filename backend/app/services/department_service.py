"""Departments and routing rules: configuration, defaults and rule loading."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai.department_classification import Rule
from app.core import default_routing
from app.database.models import Department, RoutingRule, User
from app.schemas.department import DepartmentCreate, DepartmentUpdate, RuleCreate, RuleOut, RuleUpdate
from app.services import audit_service


class DuplicateCode(Exception):
    pass


class UnknownDepartment(Exception):
    pass


def list_departments(db: Session, *, include_inactive: bool = False) -> list[Department]:
    q = select(Department).order_by(Department.name)
    if not include_inactive:
        q = q.where(Department.is_active.is_(True))
    return list(db.scalars(q))


def get_active(db: Session, department_id: uuid.UUID) -> Department | None:
    d = db.get(Department, department_id)
    return d if d is not None and d.is_active else None


def default_department(db: Session) -> Department | None:
    return db.scalar(select(Department).where(Department.is_default.is_(True),
                                              Department.is_active.is_(True)))


def _set_only_default(db: Session, dept: Department) -> None:
    db.execute(update(Department).where(Department.id != dept.id).values(is_default=False))


def create_department(db: Session, data: DepartmentCreate, actor: User | None) -> Department:
    if db.scalar(select(Department).where(Department.code == data.code)):
        raise DuplicateCode
    dept = Department(code=data.code, name=data.name.strip(), description=data.description,
                      is_default=data.is_default)
    db.add(dept)
    db.flush()
    if dept.is_default:
        _set_only_default(db, dept)
    audit_service.record(db, "department.created", actor_user_id=actor.id if actor else None,
                         target_type="department", target_id=dept.id, details={"code": dept.code})
    db.commit()
    db.refresh(dept)
    return dept


def update_department(db: Session, dept: Department, data: DepartmentUpdate, actor: User) -> Department:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in changes.items():
        setattr(dept, k, v.strip() if isinstance(v, str) else v)
    if changes.get("is_default"):
        _set_only_default(db, dept)
    audit_service.record(db, "department.updated", actor_user_id=actor.id, target_type="department",
                         target_id=dept.id, details={"fields": sorted(changes)})
    db.commit()
    db.refresh(dept)
    return dept


def rule_out(r: RoutingRule) -> RuleOut:
    return RuleOut(id=r.id, kind=r.kind, phrase=r.phrase, weight=r.weight, department_id=r.department_id,
                   department_name=r.department.name if r.department else None, is_active=r.is_active)


def list_rules(db: Session, *, department_id: uuid.UUID | None = None, kind: str | None = None,
               include_inactive: bool = True) -> list[RoutingRule]:
    q = select(RoutingRule).order_by(RoutingRule.kind, RoutingRule.phrase)
    if department_id:
        q = q.where(RoutingRule.department_id == department_id)
    if kind:
        q = q.where(RoutingRule.kind == kind)
    if not include_inactive:
        q = q.where(RoutingRule.is_active.is_(True))
    return list(db.scalars(q))


def create_rule(db: Session, data: RuleCreate, actor: User | None) -> RoutingRule:
    if data.department_id is not None and get_active(db, data.department_id) is None:
        raise UnknownDepartment
    rule = RoutingRule(kind=data.kind, phrase=data.phrase, weight=data.weight,
                       department_id=data.department_id,
                       created_by_user_id=actor.id if actor else None)
    db.add(rule)
    db.flush()
    audit_service.record(db, "routing_rule.created", actor_user_id=actor.id if actor else None,
                         target_type="routing_rule", target_id=rule.id,
                         details={"kind": rule.kind, "phrase": rule.phrase, "weight": rule.weight})
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule: RoutingRule, data: RuleUpdate, actor: User) -> RoutingRule:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in changes.items():
        setattr(rule, k, v)
    audit_service.record(db, "routing_rule.updated", actor_user_id=actor.id, target_type="routing_rule",
                         target_id=rule.id, details=changes)
    db.commit()
    db.refresh(rule)
    return rule


def active_rules(db: Session) -> list[Rule]:
    """Rules usable for classification: active rule + (for route rules) active department."""
    out = []
    for r in list_rules(db, include_inactive=False):
        if r.kind == "route" and (r.department is None or not r.department.is_active):
            continue
        out.append(Rule(id=str(r.id), kind=r.kind, phrase=r.phrase, weight=r.weight,
                        department_id=str(r.department_id) if r.department_id else None,
                        department_code=r.department.code if r.department else None,
                        department_name=r.department.name if r.department else None))
    return out


def load_defaults(db: Session) -> int:
    """Create the default (draft) departments and rules if no department exists yet."""
    if db.scalar(select(Department.id).limit(1)):
        return 0
    by_code = {}
    for code, name, is_default in default_routing.DEPARTMENTS:
        d = Department(code=code, name=name, is_default=is_default)
        db.add(d)
        by_code[code] = d
    db.flush()
    n = 0
    for code, rules in default_routing.ROUTE_RULES.items():
        for phrase, weight in rules:
            db.add(RoutingRule(kind="route", phrase=phrase, weight=weight, department_id=by_code[code].id))
            n += 1
    for phrase in default_routing.ATTENTION_PHRASES:
        db.add(RoutingRule(kind="attention", phrase=phrase, weight=1))
        n += 1
    audit_service.record(db, "routing.defaults_loaded", details={"departments": len(by_code), "rules": n})
    db.commit()
    return n
