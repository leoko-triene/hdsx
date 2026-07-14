"""验证批量上传/内容去重/角色权限/文件清单/作业读取接口。"""
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
from app.modules.models import Course  # noqa: E402


def ensure(response, statuses=(200, 201, 207)):
    if response.status_code not in statuses:
        raise AssertionError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text}")
    return response.json()


def token(client, username):
    data = ensure(client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123!"}))
    return {"Authorization": f"Bearer {data['access_token']}"}


def main():
    client = TestClient(app)
    teacher, student = token(client, "teacher"), token(client, "student")
    with SessionLocal() as db:
        course = db.scalar(select(Course).where(Course.name == "AI 教育演示课程"))

    content = f"产品功能验证 {time.time_ns()}：同一内容即使文件名不同也必须阻止重复上传。".encode()
    batch = ensure(client.post(
        f"/api/v1/courses/{course.id}/documents/batch", headers=teacher,
        data={"category": "courseware"},
        files=[
            ("files", ("内容文件A.txt", io.BytesIO(content), "text/plain")),
            ("files", ("改名后的文件B.txt", io.BytesIO(content), "text/plain")),
        ],
    ))
    assert batch["uploaded"] == 1 and batch["duplicates"] == 1, batch

    documents = ensure(client.get(f"/api/v1/courses/{course.id}/documents", headers=student))
    assert any(item["filename"] == "内容文件A.txt" for item in documents)

    forbidden = client.post("/api/v1/courses", headers=student, json={"name": "学生非法课程", "subject": "test"})
    assert forbidden.status_code == 403, forbidden.text

    teacher_assignments = ensure(client.get("/api/v1/assignments", headers=teacher))
    student_assignments = ensure(client.get("/api/v1/assignments", headers=student))
    assert all(item["status"] == "published" for item in student_assignments)
    if student_assignments:
        assignment_id = student_assignments[0]["id"]
        student_detail = ensure(client.get(f"/api/v1/assignments/{assignment_id}", headers=student))
        assert all("standard_answer" not in question for question in student_detail["questions"])
        teacher_detail = ensure(client.get(f"/api/v1/assignments/{assignment_id}", headers=teacher))
        assert all("standard_answer" in question for question in teacher_detail["questions"])

    print(json.dumps({
        "batch": batch, "knowledge_documents": len(documents),
        "student_create_course_status": forbidden.status_code,
        "teacher_assignments": len(teacher_assignments),
        "student_assignments": len(student_assignments),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
