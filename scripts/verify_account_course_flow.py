"""真实验证注册、资料/改密、加入申请审批、多负责人和批量导入。"""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.models import Course, User  # noqa: E402


def ok(response, statuses=(200, 201, 207)):
    if response.status_code not in statuses:
        raise AssertionError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text}")
    return response.json()


def login(client, username, password="Demo123!"):
    data = ok(client.post("/api/v1/auth/login", json={"username": username, "password": password}))
    return {"Authorization": f"Bearer {data['access_token']}"}


def main():
    client = TestClient(app)
    suffix = str(time.time_ns())[-10:]
    username = f"join_{suffix}"
    password = "Register123!"
    new_password = "Changed123!"
    registered = ok(client.post("/api/v1/auth/register", json={
        "username": username, "display_name": "申请入课学生", "email": None, "password": password,
    }))
    student = login(client, username, password)
    profile = ok(client.patch("/api/v1/auth/profile", headers=student, json={"display_name": "已修改姓名", "email": f"{username}@example.com"}))
    ok(client.post("/api/v1/auth/change-password", headers=student, json={"current_password": password, "new_password": new_password}))
    student = login(client, username, new_password)
    teacher = login(client, "teacher")

    with SessionLocal() as db:
        course = db.scalar(select(Course).where(Course.name == "AI 教育演示课程"))
        admin_id = db.scalar(select(User.id).where(User.username == "admin"))

    before = client.get(f"/api/v1/courses/{course.id}/documents", headers=student)
    assert before.status_code == 403
    join = ok(client.post(f"/api/v1/courses/{course.id}/join-requests", headers=student, json={"reason": "希望学习机器学习课程"}))
    pending = ok(client.get(f"/api/v1/courses/{course.id}/join-requests", headers=teacher))
    assert any(item["id"] == join["id"] for item in pending)
    ok(client.patch(f"/api/v1/course-join-requests/{join['id']}", headers=teacher, json={"action": "approve", "comment": "同意加入"}))
    after = client.get(f"/api/v1/courses/{course.id}/documents", headers=student)
    assert after.status_code == 200

    manager = ok(client.post(f"/api/v1/courses/{course.id}/managers", headers=teacher, json={"user_id": admin_id}))
    managers = ok(client.get(f"/api/v1/courses/{course.id}/managers", headers=teacher))
    assert any(item["user_id"] == admin_id for item in managers)

    csv_data = f"username,display_name,email\nimport_{suffix},批量导入学生,import_{suffix}@example.com\n".encode()
    imported = ok(client.post(
        f"/api/v1/courses/{course.id}/students/import", headers=teacher,
        data={"default_password": "Imported123!"},
        files={"file": ("students.csv", io.BytesIO(csv_data), "text/csv")},
    ))
    assert imported["success"] == 1
    courses = ok(client.get("/api/v1/courses", headers=student))
    assert any(item["id"] == course.id for item in courses)

    print(json.dumps({
        "registered_user": registered["id"], "profile_name": profile["display_name"],
        "access_before_approval": before.status_code, "access_after_approval": after.status_code,
        "managers": len(managers), "import_success": imported["success"],
        "student_visible_courses": len(courses),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
