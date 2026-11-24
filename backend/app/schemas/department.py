"""Departments and routing-rule shapes (D7)."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_default: bool
    is_active: bool


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_default: bool = False


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None
    is_active: bool | None = None


class RuleOut(BaseModel):
    id: uuid.UUID
    kind: Literal["route", "attention"]
    phrase: str
    weight: int
    department_id: uuid.UUID | None
    department_name: str | None
    is_active: bool


def _clean_phrase(v: str) -> str:
    v = " ".join(v.split()).lower()
    if len(v) < 2:
        raise ValueError("Phrase is too short.")
    return v


class RuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["route", "attention"] = "route"
    phrase: str = Field(min_length=2, max_length=100)
    weight: int = Field(default=5, ge=1, le=10)
    department_id: uuid.UUID | None = None

    @field_validator("phrase")
    @classmethod
    def check_phrase(cls, v: str) -> str:
        return _clean_phrase(v)

    @model_validator(mode="after")
    def check_department(self):
        if self.kind == "route" and self.department_id is None:
            raise ValueError("A route rule needs a department.")
        if self.kind == "attention" and self.department_id is not None:
            raise ValueError("Attention rules are not tied to a department.")
        return self


class RuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phrase: str | None = Field(default=None, min_length=2, max_length=100)
    weight: int | None = Field(default=None, ge=1, le=10)
    is_active: bool | None = None

    @field_validator("phrase")
    @classmethod
    def check_phrase(cls, v):
        return _clean_phrase(v) if v is not None else v
