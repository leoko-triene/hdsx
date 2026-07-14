from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.models import Course, CourseManager, CourseMember, User


def current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError("AUTH_REQUIRED", "请先登录", 401)
    try:
        payload = decode_access_token(authorization.removeprefix("Bearer "))
        user = db.scalar(select(User).where(User.id == int(payload["sub"]), User.is_active.is_(True)))
    except (ValueError, KeyError):
        raise AppError("INVALID_TOKEN", "登录凭证无效或已过期", 401)
    if not user:
        raise AppError("INVALID_TOKEN", "用户不存在或已禁用", 401)
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError()
        return user
    return dependency


def owned_course(db: Session, course_id: int, user: User) -> Course:
    """校验课程存在且当前教师为其负责人（管理员豁免）。"""
    course = db.get(Course, course_id)
    if not course:
        raise NotFoundError("课程")
    if user.role == "teacher" and not db.scalar(
        select(CourseManager.id).where(CourseManager.course_id == course_id, CourseManager.user_id == user.id)
    ):
        raise PermissionDeniedError("只有课程负责人可以执行此操作")
    return course


def visible_course(db: Session, course_id: int, user: User) -> Course:
    """校验课程对当前用户可见。"""
    course = db.get(Course, course_id)
    if not course:
        raise NotFoundError("课程")
    if user.role == "student" and not db.scalar(
        select(CourseMember.id).where(
            CourseMember.course_id == course_id,
            CourseMember.student_id == user.id,
            CourseMember.status == "active",
        )
    ):
        raise PermissionDeniedError("你尚未加入该课程")
    if user.role == "parent":
        raise PermissionDeniedError()
    return course


Teacher = Depends(require_roles("teacher", "admin"))

