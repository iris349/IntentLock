from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

TEST_ACCOUNTS = [
    ("admin", "AdminTest123!", "admin"),
    ("user1", "UserTest123!", "user"),
    ("user2", "UserTest123!", "user"),
]


def seed_users():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for username, password, role in TEST_ACCOUNTS:
            existing = db.scalar(
                select(User).where(User.username == username)
            )

            if existing is not None:
                continue

            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                )
            )

        db.commit()

    print("테스트 계정 준비 완료")


if __name__ == "__main__":
    seed_users()