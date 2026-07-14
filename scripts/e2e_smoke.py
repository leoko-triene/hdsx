"""连接真实 MySQL、Milvus 和 Ollama 的教学闭环冒烟测试。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.models import Course, KnowledgePoint, User  # noqa: E402


def check(response, expected=(200, 201)):
    if response.status_code not in expected:
        raise RuntimeError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text}")
    return response.json()


def login(client, username):
    data = check(client.post("/api/v1/auth/login", json={"username": username, "password": "Demo123!"}))
    return {"Authorization": f"Bearer {data['access_token']}"}


def main():
    client = TestClient(app)
    teacher = login(client, "teacher")
    student = login(client, "student")
    admin = login(client, "admin")
    parent = login(client, "parent")
    with SessionLocal() as db:
        course = db.scalar(select(Course).where(Course.name == "AI 教育演示课程"))
        student_id = db.scalar(select(User.id).where(User.username == "student"))
        parent_id = db.scalar(select(User.id).where(User.username == "parent"))
        point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.course_id == course.id, KnowledgePoint.code == "ML-OVERFIT"))
        if not point:
            point = KnowledgePoint(course_id=course.id, code="ML-OVERFIT", name="过拟合", description="过拟合的成因与缓解方法")
            db.add(point); db.commit(); db.refresh(point)
        point_id = point.id
    course_id = course.id

    source = Path(__file__).parents[1] / "evals" / "demo_course.md"
    with source.open("rb") as handle:
        upload = check(client.post(
            f"/api/v1/courses/{course_id}/documents", headers=teacher,
            data={"category": "textbook"}, files={"file": (source.name, handle, "text/markdown")},
        ))

    search = check(client.post("/api/v1/knowledge/search", headers=teacher, json={"course_id": course_id, "query": "过拟合如何缓解", "top_k": 5}))
    if not search or not search[0].get("rerank_score"):
        raise RuntimeError("混合检索或重排序没有返回有效结果")

    lesson = check(client.post("/api/v1/lesson-resources/generate", headers=teacher, json={
        "course_id": course_id, "chapter_title": "机器学习", "resource_type": "lesson_plan",
        "audience": "本科生", "duration_minutes": 45, "requirements": "包含课堂讨论",
    }))

    session = check(client.post("/api/v1/qa/sessions", headers=student, json={"course_id": course_id, "title": "机器学习答疑"}))
    answer = check(client.post(f"/api/v1/qa/sessions/{session['id']}/messages", headers=student, json={"content": "什么是过拟合，如何缓解？"}))

    assignment = check(client.post("/api/v1/assignments", headers=teacher, json={"course_id": course_id, "title": "机器学习基础作业", "description": "冒烟测试"}))
    objective = check(client.post(f"/api/v1/assignments/{assignment['id']}/questions", headers=teacher, json={
        "question_type": "single_choice", "stem": "测试集的主要用途是什么？",
        "standard_answer": "B", "options": [{"key": "A", "content": "训练参数"}, {"key": "B", "content": "最终评估泛化能力"}], "max_score": 5,
    }))
    subjective = check(client.post(f"/api/v1/assignments/{assignment['id']}/questions", headers=teacher, json={
        "question_type": "short_answer", "stem": "列举两种缓解过拟合的方法。",
        "standard_answer": "增加训练数据、正则化、降低模型复杂度、早停等。",
        "rubric": [{"criterion": "任意一种有效方法", "points": 3}, {"criterion": "第二种有效方法", "points": 2}],
        "knowledge_point_ids": [point_id], "max_score": 5,
    }))
    check(client.post(f"/api/v1/assignments/{assignment['id']}/publish", headers=teacher))
    submission = check(client.post(f"/api/v1/assignments/{assignment['id']}/submissions", headers=student, json={"answers": [
        {"question_id": objective["id"], "answer": "B"},
        {"question_id": subjective["id"], "answer": "可以增加训练数据，并使用正则化。"},
    ]}))
    grading = check(client.post(f"/api/v1/submissions/{submission['id']}/grade", headers=teacher))
    for result in grading["results"]:
        check(client.patch(f"/api/v1/grading-results/{result['grading_result_id']}/review", headers=teacher, json={"final_score": result["score"], "feedback": result["feedback"]}))
    learning_path = check(client.post(f"/api/v1/students/{student_id}/learning-paths/generate?course_id={course_id}", headers=teacher))

    report = check(client.post("/api/v1/reports/generate", headers=teacher, json={
        "student_id": student_id, "course_id": course_id, "period_type": "week",
        "period_start": "2026-07-04T00:00:00", "period_end": "2026-07-11T23:59:59",
    }))
    check(client.patch(f"/api/v1/reports/{report['id']}/review", headers=teacher, json={"action": "publish", "comment": "冒烟测试审核通过"}))
    check(client.post("/api/v1/users/parent-student-links", headers=admin, json={"parent_id": parent_id, "student_id": student_id}))
    parent_reports = check(client.get("/api/v1/parent/reports", headers=parent))
    summary = {
        "document": upload, "top_search_chunk": search[0]["chunk_id"],
        "lesson_id": lesson["id"], "qa_citations": len(answer["citations"]),
        "assignment_id": assignment["id"], "suggested_total": grading["suggested_total"],
        "learning_path_id": learning_path["id"], "report_id": report["id"],
        "parent_visible_reports": len(parent_reports),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
