import csv
import io
from pathlib import Path

from playwright.sync_api import expect

BASELINE = (
    Path(__file__).resolve().parents[3] / "baseline" / "v1"
)


def login(page, username, password):
    page.goto("http://localhost:5173")

    page.get_by_label("아이디", exact=True).fill(username)
    page.get_by_label("비밀번호", exact=True).fill(password)

    page.get_by_role(
        "button", name="로그인", exact=True
    ).click()


def test_admin_normal_flow(page):
    BASELINE.mkdir(parents=True, exist_ok=True)
    screenshots = BASELINE / "screenshots"
    screenshots.mkdir(exist_ok=True)

    # 복원용 관리자 인증
    auth = page.request.post(
        "http://127.0.0.1:8000/auth/login",
        form={
            "username": "admin",
            "password": "AdminTest123!",
        },
    )
    assert auth.ok

    headers = {
        "Authorization":
            f"Bearer {auth.json()['access_token']}"
    }

    response = page.request.get(
        "http://127.0.0.1:8000/employees",
        headers=headers,
    )
    assert response.ok

    employee = response.json()[0]
    original_role = employee["role"]

    try:
        login(page, "admin", "AdminTest123!")

        expect(
            page.get_by_role("heading", name="직원 목록 · 권한 변경")
        ).to_be_visible()

        page.screenshot(
            path=str(screenshots / "01-admin-screen.png"),
            full_page=True,
        )

        row = page.get_by_role("row").filter(
            has=page.get_by_role(
                "cell", name=employee["email"], exact=True
            )
        )

        row.get_by_role("button").click()

        dialog = page.get_by_role("dialog")
        expect(dialog).to_contain_text(employee["name"])

        page.screenshot(
            path=str(screenshots / "02-role-confirm.png"),
            full_page=True,
        )

        # 취소 후 권한이 유지되는지 확인
        dialog.get_by_role("button", name="취소").click()

        current = page.request.get(
            "http://127.0.0.1:8000/employees",
            headers=headers,
        ).json()

        assert next(
            item["role"]
            for item in current
            if item["id"] == employee["id"]
        ) == original_role

        row.get_by_role("button").click()

        with page.expect_response(
            lambda response:
                response.request.method == "PATCH"
                and response.url.endswith(
                    f"/employees/{employee['id']}/role"
                )
        ) as change:
            page.get_by_role("dialog").get_by_role(
                "button", name="확인 후 권한 변경"
            ).click()

        assert change.value.status == 200

        new_role = (
            "admin" if original_role == "user" else "user"
        )
        new_label = (
            "관리자" if new_role == "admin" else "일반 사용자"
        )
        expect(
            row.get_by_role("cell", name=new_label, exact=True)
        ).to_be_visible()

        page.get_by_role(
            "checkbox",
            name=f"{employee['name']} 내보내기 선택",
            exact=True,
        ).check()

        page.get_by_role(
            "button", name="내보내기 내용 확인"
        ).click()

        expect(page.get_by_role("dialog")).to_contain_text(
            "대상 인원: 1명"
        )

        page.screenshot(
            path=str(screenshots / "03-export-confirm.png"),
            full_page=True,
        )

        with page.expect_download() as download_info:
            page.get_by_role("dialog").get_by_role(
                "button", name="확인 후 CSV 다운로드"
            ).click()

        download = download_info.value
        csv_path = BASELINE / "export-example.csv"
        download.save_as(str(csv_path))

        rows = list(csv.reader(io.StringIO(
            csv_path.read_text(encoding="utf-8-sig")
        )))

        assert rows == [
            ["이름", "이메일"],
            [employee["name"], employee["email"]],
        ]

    finally:
        # UI 테스트가 중간에 실패해도 원래 권한으로 복원
        restore = page.request.patch(
            f"http://127.0.0.1:8000/employees/{employee['id']}/role",
            headers=headers,
            data={"role": original_role},
        )

        assert restore.status in (200, 409), (
            "원래 권한 복원 실패: " + restore.text()
        )


def test_ordinary_user_screen(page):
    login(page, "user1", "UserTest123!")

    expect(page.get_by_text(
        "직원 관리와 개인정보 내보내기는 관리자만 사용할 수 있습니다.",
        exact=True,
    )).to_be_visible()

    expect(
        page.get_by_role("heading", name="직원 목록 · 권한 변경")
    ).to_have_count(0)