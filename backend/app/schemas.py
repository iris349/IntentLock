from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime

class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str
    department: str
    role: Literal["user", "admin"]

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Literal["user", "admin"]

class RoleChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "admin"]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int
    action: str
    target_id: int | None
    details: dict
    created_at: datetime

class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_ids: list[int] = Field(min_length=1, max_length=100)

    fields: list[
        Literal["name", "email", "phone", "department"]
    ] = Field(min_length=1, max_length=4)

    @field_validator("employee_ids")
    @classmethod
    def validate_employee_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("직원 번호는 양수여야 합니다.")

        if len(values) != len(set(values)):
            raise ValueError("직원 번호를 중복 선택할 수 없습니다.")

        return values

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("내보낼 항목을 중복 선택할 수 없습니다.")

        return values