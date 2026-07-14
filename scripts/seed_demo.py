"""创建演示账号与课程。运行：从 Code1 执行 python scripts/seed_demo.py。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.models import Course, Status, User  # noqa: E402


def main():
    with SessionLocal() as db:
        accounts = [
            ("admin", "系统管理员", "admin"),
            ("teacher", "演示教师", "teacher"),
            ("student", "演示学生", "student"),
            ("parent", "演示家长", "parent"),
        ]
        users = {}
        for username, name, role in accounts:
            user = db.scalar(select(User).where(User.username == username))
            if not user:
                user = User(username=username, display_name=name, role=role, password_hash=hash_password("Demo123!"))
                db.add(user); db.flush()
            users[role] = user
        if not db.scalar(select(Course).where(Course.name == "AI 教育演示课程")):
            db.add(Course(name="AI 教育演示课程", subject="计算机", grade_level="本科", owner_id=users["teacher"].id, status=Status.ready, description="用于验证知识库、备课、批改与报告闭环。"))
        db.commit()
    print("演示数据已创建。账号：admin/teacher/student/parent，密码均为 Demo123!")


if __name__ == "__main__": main()

