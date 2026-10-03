from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="IntentLock 실습 서비스")


class Employee(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    department: str
    role: Literal["user", "admin"]


# 첫 실행 확인용 가상 데이터
employees = [
    Employee(
        id=1,
        name="admin1",
        email="employee1@example.com",
        phone="TEST-PHONE-001",
        department="개발팀",
        role="user",
    ),
    Employee(
        id=2,
        name="admin2",
        email="employee2@example.com",
        phone="TEST-PHONE-002",
        department="운영팀",
        role="user",
    ),
    Employee(
        id=3,
        name="admin3",
        email="employee3@example.com",
        phone="TEST-PHONE-003",
        department="보안팀",
        role="admin",
    ),
]


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/employees", response_model=list[Employee])
def get_employees():
    return employees