from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Employee


def seed():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for number in range(1, 11):
            email = f"employee{number}@example.com"

            existing = db.scalar(
                select(Employee).where(Employee.email == email)
            )

            if existing is not None:
                continue

            db.add(
                Employee(
                    name=f"테스트직원{number:02d}",
                    email=email,
                    phone=f"TEST-PHONE-{number:03d}",
                    department=["개발팀", "운영팀", "보안팀"][
                        (number - 1) % 3
                    ],
                    role="user",
                )
            )

        db.commit()

    print("직원 테이블과 가상 데이터 준비 완료")


if __name__ == "__main__":
    seed()