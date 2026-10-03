import csv
import io

from fastapi.responses import Response
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import AuditLog, Employee, User
from app.database import get_db
from app.schemas import (
    AuditLogResponse,
    EmployeeResponse,
    ExportRequest,
    RoleChangeRequest,
    TokenResponse,
    UserResponse,

)
from app.security import (
    DUMMY_HASH,
    create_access_token,
    get_current_user,
    require_admin,
    verify_password,
)

app = FastAPI(title="IntentLock 실습 서비스")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.username == form.username)
    )

    stored_hash = user.password_hash if user else DUMMY_HASH
    password_valid = verify_password(form.password, stored_hash)

    if user is None or not password_valid:
        raise HTTPException(
            status_code=401,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(user.id)
    )


@app.get("/auth/me", response_model=UserResponse)
def read_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@app.get("/employees", response_model=list[EmployeeResponse])
def get_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = select(Employee).order_by(Employee.id)
    return db.scalars(statement).all()

@app.patch(
    "/employees/{employee_id}/role",
    response_model=EmployeeResponse,
)
def change_employee_role(
    employee_id: int,
    body: RoleChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    employee = db.get(Employee, employee_id)

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="직원을 찾을 수 없습니다.",
        )

    previous_role = employee.role

    if previous_role == body.role:
        raise HTTPException(
            status_code=409,
            detail="이미 해당 권한입니다.",
        )

    employee.role = body.role

    log = AuditLog(
        actor_user_id=current_user.id,
        action="employee_role_change",
        target_id=employee.id,
        details={
            "previous_role": previous_role,
            "new_role": body.role,
        },
    )

    db.add(log)

    # 권한 변경과 기록 저장을 함께 확정
    db.commit()
    db.refresh(employee)

    return employee


@app.get(
    "/audit-logs",
    response_model=list[AuditLogResponse],
)
def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = select(AuditLog).order_by(
        AuditLog.created_at.desc(),
        AuditLog.id.desc(),
    )

    return db.scalars(statement).all()

@app.post(
    "/exports",
    response_class=Response,
    responses={
        200: {
            "description": "선택한 직원 개인정보 CSV",
            "content": {"text/csv": {}},
        }
    },
)
def export_employees(
    body: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = select(Employee).where(
        Employee.id.in_(body.employee_ids)
    )

    employees = db.scalars(statement).all()
    employees_by_id = {
        employee.id: employee for employee in employees
    }

    missing_ids = [
        employee_id
        for employee_id in body.employee_ids
        if employee_id not in employees_by_id
    ]

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "존재하지 않는 직원이 포함되어 있습니다.",
                "missing_employee_ids": missing_ids,
            },
        )

    # 사용자에게 익숙한 CSV 열 이름
    field_labels = {
        "name": "이름",
        "email": "이메일",
        "phone": "전화번호",
        "department": "부서",
    }

    output = io.StringIO(newline="")
    writer = csv.writer(output)

    writer.writerow([
        field_labels[field] for field in body.fields
    ])

    for employee_id in body.employee_ids:
        employee = employees_by_id[employee_id]

        row = []

        for field in body.fields:
            value = str(getattr(employee, field))

            # 스프레드시트에서 수식으로 해석될 수 있는 값 처리
            if value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value

            row.append(value)

        writer.writerow(row)

    # BOM을 포함해 한글 CSV를 생성
    csv_bytes = output.getvalue().encode("utf-8-sig")

    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="employee_export",
            target_id=None,
            details={
                "employee_ids": body.employee_ids,
                "fields": body.fields,
                "employee_count": len(employees),
            },
        )
    )

    db.commit()

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                'attachment; filename="employees.csv"',
            "Cache-Control": "no-store",
        },
    )