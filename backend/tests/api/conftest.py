import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Employee, User
from app.security import hash_password

ADMIN_HASH = hash_password("AdminTest123!")
USER_HASH = hash_password("UserTest123!")


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, connection_record):
        connection.execute("PRAGMA foreign_keys=ON")

    TestSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    with TestSession() as db:
        db.add_all([
            User(
                id=1,
                username="admin",
                password_hash=ADMIN_HASH,
                role="admin",
            ),
            User(
                id=2,
                username="user1",
                password_hash=USER_HASH,
                role="user",
            ),
        ])

        db.add_all([
            Employee(
                id=1,
                name="테스트직원01",
                email="employee1@example.com",
                phone="TEST-PHONE-001",
                department="개발팀",
                role="user",
            ),
            Employee(
                id=2,
                name="테스트직원02",
                email="employee2@example.com",
                phone="TEST-PHONE-002",
                department="운영팀",
                role="user",
            ),
        ])

        db.commit()

    def override_get_db():
        with TestSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.fixture
def admin_headers(client):
    response = client.post(
        "/auth/login",
        data={
            "username": "admin",
            "password": "AdminTest123!",
        },
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(client):
    response = client.post(
        "/auth/login",
        data={
            "username": "user1",
            "password": "UserTest123!",
        },
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}