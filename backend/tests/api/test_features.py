import csv
import io

import pytest


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrong"},
    )

    assert response.status_code == 401


def test_admin_can_read_employees(client, admin_headers):
    response = client.get(
        "/employees",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/employees", None),
        ("GET", "/audit-logs", None),
        ("PATCH", "/employees/1/role", {"role": "admin"}),
        (
            "POST",
            "/exports",
            {"employee_ids": [1], "fields": ["name"]},
        ),
    ],
)
def test_protected_routes(
    client, user_headers, admin_headers, method, path, body
):
    options = {"json": body} if body is not None else {}

    anonymous = client.request(method, path, **options)
    ordinary_user = client.request(
        method,
        path,
        headers=user_headers,
        **options,
    )

    assert anonymous.status_code == 401
    assert ordinary_user.status_code == 403

    # 拒否された要求で変更・記録が発生していないこと
    employees = client.get(
        "/employees", headers=admin_headers
    ).json()
    assert employees[0]["role"] == "user"

    logs = client.get(
        "/audit-logs", headers=admin_headers
    ).json()
    assert logs == []


def test_role_change_and_audit(client, admin_headers):
    response = client.patch(
        "/employees/1/role",
        headers=admin_headers,
        json={"role": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    employees = client.get(
        "/employees", headers=admin_headers
    ).json()
    assert employees[0]["role"] == "admin"

    logs = client.get(
        "/audit-logs", headers=admin_headers
    ).json()

    assert len(logs) == 1
    assert logs[0]["target_id"] == 1
    assert logs[0]["actor_user_id"] == 1
    assert logs[0]["details"] == {
        "previous_role": "user",
        "new_role": "admin",
    }


def test_export_only_selected_data(client, admin_headers):
    response = client.post(
        "/exports",
        headers=admin_headers,
        json={
            "employee_ids": [2],
            "fields": ["name", "email"],
        },
    )

    assert response.status_code == 200

    text = response.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))

    assert rows == [
        ["이름", "이메일"],
        ["테스트직원02", "employee2@example.com"],
    ]
    assert "TEST-PHONE" not in text

    logs = client.get(
        "/audit-logs", headers=admin_headers
    ).json()

    assert len(logs) == 1
    assert logs[0]["action"] == "employee_export"
    assert logs[0]["details"] == {
        "employee_ids": [2],
        "fields": ["name", "email"],
        "employee_count": 1,
    }


@pytest.mark.parametrize(
    "body,expected_status",
    [
        ({"employee_ids": [], "fields": ["name"]}, 422),
        ({"employee_ids": [1], "fields": ["password"]}, 422),
        ({"employee_ids": [1, 1], "fields": ["name"]}, 422),
        ({"employee_ids": [1, 99999], "fields": ["name"]}, 404),
    ],
)
def test_invalid_export_creates_no_log(
    client, admin_headers, body, expected_status
):
    response = client.post(
        "/exports",
        headers=admin_headers,
        json=body,
    )

    assert response.status_code == expected_status

    logs = client.get(
        "/audit-logs", headers=admin_headers
    ).json()
    assert logs == []