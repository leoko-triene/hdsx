import hashlib
import csv
import io
import json
import re
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, owned_course, require_roles, visible_course
from app.api.schemas import (
    AssignmentCreate, AssignmentMaterialGenerate, ChapterCreate, CourseCreate, CourseManagerAdd, CourseOut,
    JoinRequestCreate, JoinRequestReview,
    KnowledgePointCreate, LessonGenerateRequest, LoginRequest, ParentLinkCreate, PasswordChange,
    ProfileUpdate, QAAnswerCorrection, QAMessageCreate, QASessionCreate, QuestionCreate,
    RegisterRequest, ReportGenerateRequest, ReportReviewRequest, ReviewRequest, SearchRequest,
    SubmissionCreate, TokenResponse, UserCreate, UserOut,
)
from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.integrations.llm import get_llm_provider
from app.modules.models import (
    Assignment, Chapter, ClassGroup, ClassMember, Course, CourseJoinRequest,
    CourseManager, CourseMember, Document, DocumentChunk, GradingResult,
    KnowledgePoint, LearningPath, LessonResource, MasterySnapshot, Notification,
    ParentStudentLink, QAMessage, QASession, Question, Report, Status, Submission, User,
)
from app.rag.service import KnowledgeService
from app.services.agents import generate_assignment_materials, generate_lesson, generate_standard_answer, grade_subjective
from app.services.documents import extract_text, read_upload

router = APIRouter()


@router.post("/auth/bootstrap", response_model=UserOut, tags=["auth"])
def bootstrap_admin(data: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(func.count(User.id))) > 0:
        raise AppError("BOOTSTRAP_CLOSED", "系统已有用户，初始化入口已关闭", 409)
    if data.role != "admin":
        raise AppError("ADMIN_REQUIRED", "首个用户必须是管理员", 422)
    user = User(
        username=data.username, email=data.email, display_name=data.display_name,
        role=data.role, password_hash=hash_password(data.password),
    )
    db.add(user); db.commit(); db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "用户名或密码错误", 401)
    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role),
        user=UserOut.model_validate(user).model_dump(),
    )


@router.post("/auth/register", response_model=UserOut, status_code=201, tags=["auth"])
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.username == data.username)):
        raise AppError("USERNAME_EXISTS", "用户名已存在", 409)
    if data.email and db.scalar(select(User.id).where(User.email == data.email)):
        raise AppError("EMAIL_EXISTS", "邮箱已被使用", 409)
    linked_students = []
    if data.role == "parent":
        usernames = {value.strip() for value in data.student_usernames if value.strip()}
        if not usernames:
            raise AppError("PARENT_STUDENT_REQUIRED", "注册家长账号必须绑定至少一个学生用户名", 422)
        linked_students = list(db.scalars(select(User).where(User.username.in_(usernames), User.role == "student", User.is_active.is_(True))))
        if len(linked_students) != len(usernames):
            found = {item.username for item in linked_students}
            missing = sorted(usernames - found)
            raise AppError("STUDENT_NOT_FOUND", "部分学生账号不存在", 422, {"usernames": missing})
    user = User(
        username=data.username, email=data.email, display_name=data.display_name,
        role=data.role, password_hash=hash_password(data.password),
    )
    db.add(user); db.flush()
    for student in linked_students:
        db.add(ParentStudentLink(parent_id=user.id, student_id=student.id, status="active"))
    db.commit(); db.refresh(user)
    return user


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(user: User = Depends(current_user)):
    return user


@router.patch("/auth/profile", response_model=UserOut, tags=["auth"])
def update_profile(data: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if data.email:
        occupied = db.scalar(select(User.id).where(User.email == data.email, User.id != user.id))
        if occupied:
            raise AppError("EMAIL_EXISTS", "邮箱已被使用", 409)
    user.display_name = data.display_name
    user.email = data.email
    db.commit(); db.refresh(user)
    return user


@router.post("/auth/change-password", tags=["auth"])
def change_password(data: PasswordChange, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(data.current_password, user.password_hash):
        raise AppError("CURRENT_PASSWORD_INVALID", "当前密码不正确", 422)
    if data.current_password == data.new_password:
        raise AppError("PASSWORD_UNCHANGED", "新密码不能与当前密码相同", 422)
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "密码修改成功，请妥善保管新密码"}


@router.post("/users", response_model=UserOut, tags=["users"])
def create_user(data: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    if db.scalar(select(User.id).where(User.username == data.username)):
        raise AppError("USERNAME_EXISTS", "用户名已存在", 409)
    user = User(**data.model_dump(exclude={"password"}), password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut], tags=["users"])
def list_users(role: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_roles("teacher", "admin"))):
    stmt = select(User).where(User.is_active.is_(True)).order_by(User.display_name)
    if role:
        stmt = stmt.where(User.role == role)
    return list(db.scalars(stmt.limit(500)))


@router.post("/users/parent-student-links", tags=["users"])
def create_parent_link(data: ParentLinkCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    parent, student = db.get(User, data.parent_id), db.get(User, data.student_id)
    if not parent or parent.role != "parent" or not student or student.role != "student":
        raise AppError("INVALID_RELATION", "必须指定有效的家长和学生账号", 422)
    existing = db.scalar(select(ParentStudentLink).where(ParentStudentLink.parent_id == parent.id, ParentStudentLink.student_id == student.id))
    if existing: return {"id": existing.id, "status": existing.status}
    item = ParentStudentLink(parent_id=parent.id, student_id=student.id)
    db.add(item); db.flush()
    return {"id": item.id, "status": item.status}


@router.get("/courses", response_model=list[CourseOut], tags=["courses"])
def list_courses(db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Course).order_by(Course.id.desc())
    if user.role == "student":
        enrolled = select(CourseMember.course_id).where(
            CourseMember.student_id == user.id, CourseMember.status == "active"
        )
        stmt = stmt.where(Course.id.in_(enrolled))
    elif user.role == "parent":
        stmt = stmt.where(False)
    courses = list(db.scalars(stmt))
    managed_ids = set()
    if user.role == "teacher":
        managed_ids = set(db.scalars(select(CourseManager.course_id).where(CourseManager.user_id == user.id)))
    elif user.role == "admin":
        managed_ids = {course.id for course in courses}
    return [CourseOut.model_validate(course).model_copy(update={"is_manager": course.id in managed_ids}) for course in courses]


@router.get("/courses/managed", response_model=list[CourseOut], tags=["courses"])
def list_managed_courses(db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    stmt = select(Course).order_by(Course.name)
    if user.role == "teacher":
        stmt = stmt.where(Course.id.in_(select(CourseManager.course_id).where(CourseManager.user_id == user.id)))
    return [CourseOut.model_validate(course).model_copy(update={"is_manager": True}) for course in db.scalars(stmt)]


@router.post("/courses", response_model=CourseOut, tags=["courses"])
def create_course(data: CourseCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    course = Course(**data.model_dump(), owner_id=user.id, status=Status.ready)
    db.add(course); db.flush()
    db.add(CourseManager(course_id=course.id, user_id=user.id, added_by=user.id))
    db.commit(); db.refresh(course)
    return course


@router.get("/courses/discover", tags=["courses"])
def discover_courses(db: Session = Depends(get_db), user: User = Depends(require_roles("student"))):
    memberships = select(CourseMember.course_id).where(CourseMember.student_id == user.id, CourseMember.status == "active")
    requests = {item.course_id: item for item in db.scalars(select(CourseJoinRequest).where(CourseJoinRequest.student_id == user.id))}
    courses = list(db.scalars(select(Course).where(Course.status == Status.ready, Course.id.not_in(memberships)).order_by(Course.name)))
    return [{
        "id": course.id, "name": course.name, "subject": course.subject,
        "grade_level": course.grade_level, "description": course.description,
        "request_status": requests.get(course.id).status if requests.get(course.id) else None,
    } for course in courses]


@router.post("/courses/{course_id}/join-requests", tags=["courses"])
def request_course_join(course_id: int, data: JoinRequestCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("student"))):
    course = db.get(Course, course_id)
    if not course or course.status != Status.ready:
        raise NotFoundError("课程")
    if db.scalar(select(CourseMember.id).where(CourseMember.course_id == course_id, CourseMember.student_id == user.id, CourseMember.status == "active")):
        raise AppError("ALREADY_MEMBER", "你已经加入该课程", 409)
    item = db.scalar(select(CourseJoinRequest).where(CourseJoinRequest.course_id == course_id, CourseJoinRequest.student_id == user.id))
    if item and item.status == "pending":
        raise AppError("REQUEST_PENDING", "加入申请正在等待审批", 409)
    if item:
        item.status = "pending"; item.reason = data.reason; item.reviewer_id = None
        item.review_comment = None; item.reviewed_at = None
    else:
        item = CourseJoinRequest(course_id=course_id, student_id=user.id, reason=data.reason)
        db.add(item)
    db.commit(); db.refresh(item)
    return {"id": item.id, "status": item.status}


@router.get("/courses/{course_id}/join-requests", tags=["courses"])
def list_join_requests(course_id: int, status: str = "pending", db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, course_id, user)
    rows = db.execute(
        select(CourseJoinRequest, User).join(User, User.id == CourseJoinRequest.student_id)
        .where(CourseJoinRequest.course_id == course_id, CourseJoinRequest.status == status)
        .order_by(CourseJoinRequest.created_at)
    ).all()
    return [{
        "id": item.id, "student_id": student.id, "student_name": student.display_name,
        "username": student.username, "reason": item.reason, "status": item.status,
        "created_at": item.created_at,
    } for item, student in rows]


@router.patch("/course-join-requests/{request_id}", tags=["courses"])
def review_join_request(request_id: int, data: JoinRequestReview, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    item = db.get(CourseJoinRequest, request_id)
    if not item:
        raise NotFoundError("加入申请")
    owned_course(db, item.course_id, user)
    if item.status != "pending":
        raise AppError("REQUEST_ALREADY_REVIEWED", "该申请已经处理", 409)
    item.status = "approved" if data.action == "approve" else "rejected"
    item.reviewer_id = user.id; item.review_comment = data.comment; item.reviewed_at = datetime.utcnow()
    if data.action == "approve":
        member = db.scalar(select(CourseMember).where(CourseMember.course_id == item.course_id, CourseMember.student_id == item.student_id))
        if member:
            member.status = "active"; member.source = "application"
        else:
            db.add(CourseMember(course_id=item.course_id, student_id=item.student_id, source="application"))
    db.commit()
    return {"id": item.id, "status": item.status}


@router.post("/courses/{course_id}/managers", tags=["courses"])
def add_course_manager(course_id: int, data: CourseManagerAdd, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, course_id, user)
    manager = db.get(User, data.user_id)
    if not manager or manager.role not in {"teacher", "admin"}:
        raise AppError("INVALID_MANAGER", "课程负责人必须是教师或管理员", 422)
    existing = db.scalar(select(CourseManager).where(CourseManager.course_id == course_id, CourseManager.user_id == manager.id))
    if existing:
        return {"id": existing.id, "user_id": manager.id, "display_name": manager.display_name}
    item = CourseManager(course_id=course_id, user_id=manager.id, added_by=user.id)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "user_id": manager.id, "display_name": manager.display_name}


@router.get("/courses/{course_id}/managers", tags=["courses"])
def list_course_managers(course_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, course_id, user)
    rows = db.execute(
        select(CourseManager, User).join(User, User.id == CourseManager.user_id)
        .where(CourseManager.course_id == course_id).order_by(User.display_name)
    ).all()
    return [{"id": item.id, "user_id": manager.id, "display_name": manager.display_name, "username": manager.username} for item, manager in rows]


@router.post("/courses/{course_id}/chapters", tags=["courses"])
def create_chapter(course_id: int, data: ChapterCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, course_id, user)
    item = Chapter(course_id=course_id, **data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "title": item.title}


@router.post("/courses/{course_id}/knowledge-points", tags=["courses"])
def create_knowledge_point(course_id: int, data: KnowledgePointCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, course_id, user)
    item = KnowledgePoint(course_id=course_id, **data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "code": item.code, "name": item.name}


@router.get("/courses/{course_id}/students", tags=["courses"])
def list_course_students(course_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, course_id, user)
    rows = db.execute(
        select(CourseMember, User).join(User, User.id == CourseMember.student_id)
        .where(CourseMember.course_id == course_id, CourseMember.status == "active")
        .order_by(User.display_name)
    ).all()
    return [{
        "id": student.id, "display_name": student.display_name, "username": student.username,
        "email": student.email, "source": member.source, "joined_at": member.created_at,
    } for member, student in rows]


@router.post("/courses/{course_id}/students/import", status_code=207, tags=["courses"])
async def import_course_students(
    course_id: int, default_password: str = Form(...), file: UploadFile = File(...),
    db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin")),
):
    owned_course(db, course_id, user)
    if len(default_password) < 8:
        raise AppError("WEAK_DEFAULT_PASSWORD", "默认初始密码至少 8 位", 422)
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise AppError("IMPORT_FILE_TOO_LARGE", "学生名单不能超过 2MB", 413)
    text_value = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text_value = raw.decode(encoding); break
        except UnicodeDecodeError:
            continue
    if text_value is None:
        raise AppError("IMPORT_ENCODING_INVALID", "CSV 必须使用 UTF-8 或 GB18030 编码", 422)
    reader = csv.DictReader(io.StringIO(text_value))
    required = {"username", "display_name"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise AppError("IMPORT_COLUMNS_INVALID", "CSV 必须包含 username、display_name，可选 email、password", 422)
    results = []
    for line_no, row in enumerate(reader, start=2):
        username = (row.get("username") or "").strip()
        display_name = (row.get("display_name") or "").strip()
        email = (row.get("email") or "").strip() or None
        password = (row.get("password") or "").strip() or default_password
        if not username or not display_name or len(password) < 8:
            results.append({"line": line_no, "username": username, "status": "failed", "message": "用户名、姓名或密码格式无效"}); continue
        try:
            student = db.scalar(select(User).where(User.username == username))
            created = False
            if student and student.role != "student":
                results.append({"line": line_no, "username": username, "status": "failed", "message": "同名账号不是学生"}); continue
            if not student:
                if email and db.scalar(select(User.id).where(User.email == email)):
                    results.append({"line": line_no, "username": username, "status": "failed", "message": "邮箱已被占用"}); continue
                student = User(username=username, display_name=display_name, email=email, role="student", password_hash=hash_password(password))
                db.add(student); db.flush(); created = True
            member = db.scalar(select(CourseMember).where(CourseMember.course_id == course_id, CourseMember.student_id == student.id))
            if member and member.status == "active":
                results.append({"line": line_no, "username": username, "status": "existing", "message": "已是课程成员"}); continue
            if member:
                member.status = "active"; member.source = "import"
            else:
                db.add(CourseMember(course_id=course_id, student_id=student.id, source="import"))
            db.commit()
            results.append({"line": line_no, "username": username, "student_id": student.id, "status": "created" if created else "added"})
        except Exception as exc:
            db.rollback(); results.append({"line": line_no, "username": username, "status": "failed", "message": str(exc)})
    return {
        "total": len(results), "success": sum(x["status"] in {"created", "added"} for x in results),
        "existing": sum(x["status"] == "existing" for x in results),
        "failed": sum(x["status"] == "failed" for x in results), "results": results,
    }


@router.post("/courses/{course_id}/documents", status_code=201, tags=["knowledge"])
async def upload_document(
    course_id: int, category: str = Form("textbook"), file: UploadFile = File(...),
    db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin")),
):
    owned_course(db, course_id, user)
    result = await _process_document_upload(course_id, category, file, db, user)
    if result["status"] == "duplicate":
        raise AppError("DUPLICATE_DOCUMENT", "知识库中已存在内容相同的文件", 409, result)
    return result


async def _process_document_upload(
    course_id: int, category: str, file: UploadFile, db: Session, user: User
) -> dict:
    settings = get_settings()
    data, digest = await read_upload(file, settings.max_upload_mb)
    filename = Path(file.filename or "unnamed").name
    duplicate = db.scalar(
        select(Document).where(Document.course_id == course_id, Document.file_hash == digest)
    )
    if duplicate:
        return {
            "filename": filename, "status": "duplicate", "duplicate_of": duplicate.id,
            "message": f"内容与知识库文件《{duplicate.filename}》相同，已阻止重复上传",
        }
    target_dir = settings.storage_root / "uploads" / str(course_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex}_{filename}"
    document = None
    try:
        content = extract_text(filename, data)
        target.write_bytes(data)
        document = Document(
            course_id=course_id, uploader_id=user.id, filename=filename,
            source_path=str(target.resolve()), category=category,
            mime_type=file.content_type or "application/octet-stream", file_hash=digest,
            dedup_key=digest,
        )
        db.add(document); db.flush()
        service = KnowledgeService(db)
        count = service.ingest_text(document, content)
        db.flush()
        await service.index_document_vectors(document)
        document.status = Status.ready
        db.commit(); db.refresh(document)
        return {"id": document.id, "status": "ready", "chunks": count, "filename": filename}
    except IntegrityError:
        db.rollback()
        if target.exists():
            target.unlink(missing_ok=True)
        duplicate = db.scalar(select(Document).where(Document.course_id == course_id, Document.file_hash == digest))
        if duplicate:
            return {
                "filename": filename, "status": "duplicate", "duplicate_of": duplicate.id,
                "message": f"内容与知识库文件《{duplicate.filename}》相同，已阻止重复上传",
            }
        raise
    except Exception:
        db.rollback()
        if target.exists():
            target.unlink(missing_ok=True)
        raise


@router.post("/courses/{course_id}/documents/batch", status_code=207, tags=["knowledge"])
async def upload_documents_batch(
    course_id: int, category: str = Form("textbook"), files: list[UploadFile] = File(...),
    db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin")),
):
    owned_course(db, course_id, user)
    if not files:
        raise AppError("EMPTY_UPLOAD", "请至少选择一个文件", 422)
    if len(files) > 20:
        raise AppError("TOO_MANY_FILES", "单次最多上传 20 个文件", 422)
    results = []
    for file in files:
        try:
            results.append(await _process_document_upload(course_id, category, file, db, user))
        except AppError as exc:
            results.append({"filename": Path(file.filename or "unnamed").name, "status": "failed", "error": exc.message, "code": exc.code})
        except Exception as exc:
            results.append({"filename": Path(file.filename or "unnamed").name, "status": "failed", "error": str(exc), "code": "UPLOAD_FAILED"})
    return {
        "total": len(results),
        "uploaded": sum(item["status"] == "ready" for item in results),
        "duplicates": sum(item["status"] == "duplicate" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }


@router.get("/courses/{course_id}/documents", tags=["knowledge"])
def list_documents(
    course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    visible_course(db, course_id, user)
    rows = db.execute(
        select(Document, func.count(DocumentChunk.id))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.course_id == course_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    ).all()
    return [{
        "id": document.id, "filename": document.filename, "category": document.category,
        "mime_type": document.mime_type, "file_hash": document.file_hash,
        "status": document.status, "chunks": int(chunk_count),
        "created_at": document.created_at, "uploader_id": document.uploader_id,
    } for document, chunk_count in rows]


@router.post("/knowledge/search", tags=["knowledge"])
async def search_knowledge(data: SearchRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    visible_course(db, data.course_id, user)
    chunks = await KnowledgeService(db).hybrid_search(data.course_id, data.query, data.top_k)
    return [asdict(c) for c in chunks]


@router.post("/lesson-resources/generate", tags=["lesson"])
async def lesson_generate(data: LessonGenerateRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, data.course_id, user)
    content, citations = await generate_lesson(db, data)
    item = LessonResource(
        course_id=data.course_id, chapter_id=data.chapter_id, creator_id=user.id,
        resource_type=data.resource_type, title=content.get("title", data.chapter_title),
        content_json=content, citations_json=citations,
    )
    db.add(item); db.commit(); db.refresh(item)
    unsaved_ids = list(db.scalars(
        select(LessonResource.id).where(
            LessonResource.creator_id == user.id, LessonResource.is_saved.is_(False)
        ).order_by(LessonResource.created_at.desc(), LessonResource.id.desc()).offset(30)
    ))
    if unsaved_ids:
        for old in db.scalars(select(LessonResource).where(LessonResource.id.in_(unsaved_ids))):
            db.delete(old)
        db.commit()
    return {"id": item.id, "content": content, "citations": citations, "status": item.status, "is_saved": item.is_saved, "created_at": item.created_at}


@router.get("/lesson-resources", tags=["lesson"])
def list_lesson_resources(course_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    stmt = select(LessonResource, Course).join(Course, Course.id == LessonResource.course_id).where(LessonResource.creator_id == user.id)
    if course_id:
        owned_course(db, course_id, user); stmt = stmt.where(LessonResource.course_id == course_id)
    rows = db.execute(stmt.order_by(LessonResource.created_at.desc()).limit(200)).all()
    return [{
        "id": item.id, "course_id": course.id, "course_name": course.name,
        "title": item.title, "resource_type": item.resource_type,
        "content": item.content_json, "citations": item.citations_json,
        "is_saved": item.is_saved, "status": item.status, "created_at": item.created_at,
    } for item, course in rows]


@router.patch("/lesson-resources/{resource_id}/save", tags=["lesson"])
def save_lesson_resource(resource_id: int, saved: bool = True, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    item = db.get(LessonResource, resource_id)
    if not item or (item.creator_id != user.id and user.role != "admin"):
        raise NotFoundError("备课记录")
    item.is_saved = saved; db.commit()
    return {"id": item.id, "is_saved": item.is_saved}


@router.delete("/lesson-resources/{resource_id}", status_code=204, tags=["lesson"])
def delete_lesson_resource(resource_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    item = db.get(LessonResource, resource_id)
    if not item or (item.creator_id != user.id and user.role != "admin"):
        raise NotFoundError("备课记录")
    db.delete(item); db.commit()
    return Response(status_code=204)


@router.get("/lesson-resources/{resource_id}/download", tags=["lesson"])
def download_lesson_resource(resource_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    item = db.get(LessonResource, resource_id)
    if not item or (item.creator_id != user.id and user.role != "admin"):
        raise NotFoundError("备课记录")
    content = item.content_json or {}
    body = content.get("text") if isinstance(content, dict) else str(content)
    if not body:
        body = json.dumps(content, ensure_ascii=False, indent=2)
    document = f"# {item.title}\n\n{body}\n\n---\n生成时间：{item.created_at.isoformat()}\n"
    safe_name = "lesson-resource-" + str(item.id) + ".md"
    return Response(content=document, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})



@router.post("/assignments", tags=["assignment"])
def create_assignment(data: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, data.course_id, user)
    item = Assignment(**data.model_dump(), creator_id=user.id, total_score=0)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "title": item.title, "status": item.status}


def assignment_query_for_user(user: User):
    stmt = select(Assignment, Course).join(Course, Course.id == Assignment.course_id)
    if user.role == "teacher":
        managed = select(CourseManager.course_id).where(CourseManager.user_id == user.id)
        stmt = stmt.where(Course.id.in_(managed))
    elif user.role == "student":
        course_ids = select(CourseMember.course_id).where(
            CourseMember.student_id == user.id, CourseMember.status == "active"
        )
        stmt = stmt.where(
            Assignment.status == Status.published,
            Assignment.course_id.in_(course_ids),
        )
    elif user.role == "parent":
        stmt = stmt.where(False)
    return stmt


def assignment_summary(db: Session, assignment: Assignment, course: Course, user: User) -> dict:
    question_count = db.scalar(select(func.count(Question.id)).where(Question.assignment_id == assignment.id)) or 0
    submission_count = db.scalar(select(func.count(Submission.id)).where(Submission.assignment_id == assignment.id)) or 0
    my_submission = None
    if user.role == "student":
        submission = db.scalar(select(Submission).where(Submission.assignment_id == assignment.id, Submission.student_id == user.id))
        if submission:
            my_submission = {"id": submission.id, "status": submission.status, "total_score": submission.total_score, "submitted_at": submission.submitted_at}
    return {
        "id": assignment.id, "title": assignment.title, "description": assignment.description,
        "course_id": course.id, "course_name": course.name, "class_id": assignment.class_id,
        "due_at": assignment.due_at, "total_score": assignment.total_score,
        "status": assignment.status, "question_count": int(question_count),
        "submission_count": int(submission_count), "my_submission": my_submission,
        "created_at": assignment.created_at,
    }


@router.get("/assignments", tags=["assignment"])
def list_assignments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(assignment_query_for_user(user).order_by(Assignment.created_at.desc())).all()
    return [assignment_summary(db, assignment, course, user) for assignment, course in rows]


@router.get("/assignments/{assignment_id}", tags=["assignment"])
def get_assignment(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.execute(assignment_query_for_user(user).where(Assignment.id == assignment_id)).first()
    if not row:
        raise NotFoundError("作业")
    assignment, course = row
    questions = list(db.scalars(select(Question).where(Question.assignment_id == assignment.id).order_by(Question.sort_order, Question.id)))
    question_items = []
    for question in questions:
        item = {
            "id": question.id, "question_type": question.question_type, "stem": question.stem,
            "options": question.options_json, "max_score": question.max_score,
            "sort_order": question.sort_order, "material_type": question.material_type,
        }
        if user.role in {"teacher", "admin"}:
            item.update({"standard_answer": question.standard_answer, "rubric": question.rubric_json, "knowledge_point_ids": question.knowledge_point_ids_json})
        question_items.append(item)
    return {**assignment_summary(db, assignment, course, user), "questions": question_items}


@router.post("/assignments/{assignment_id}/generate-materials", tags=["assignment"])
async def generate_assignment_content(assignment_id: int, data: AssignmentMaterialGenerate, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise NotFoundError("作业")
    owned_course(db, assignment.course_id, user)
    if assignment.status != Status.draft:
        raise AppError("ASSIGNMENT_NOT_DRAFT", "只有草稿作业可以自动添加材料", 409)
    document = db.get(Document, data.document_id)
    if not document or document.course_id != assignment.course_id or document.status != Status.ready:
        raise AppError("DOCUMENT_NOT_AVAILABLE", "请选择该课程中已完成入库的文件", 422)
    chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index)))
    materials = await generate_assignment_materials(document, chunks, data)
    start_order = db.scalar(select(func.max(Question.sort_order)).where(Question.assignment_id == assignment.id)) or 0
    created = []
    for index, material in enumerate(materials, start=1):
        question = Question(
            assignment_id=assignment.id, question_type=material["question_type"],
            stem=material["stem"], standard_answer=material["standard_answer"],
            options_json=material.get("options"), rubric_json=None, knowledge_point_ids_json=[],
            material_type=material["material_type"], max_score=Decimal(str(material["max_score"])),
            sort_order=start_order + index,
        )
        assignment.total_score = Decimal(assignment.total_score) + question.max_score
        db.add(question); db.flush()
        created.append({"id": question.id, **material})
    db.commit()
    return {"assignment_id": assignment.id, "document_id": document.id, "document_name": document.filename, "created": len(created), "items": created}


@router.get("/assignments/{assignment_id}/submissions", tags=["grading"])
def list_assignment_submissions(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise NotFoundError("作业")
    owned_course(db, assignment.course_id, user)
    rows = db.execute(
        select(Submission, User).join(User, User.id == Submission.student_id)
        .where(Submission.assignment_id == assignment_id).order_by(Submission.submitted_at.desc())
    ).all()
    return [{
        "id": submission.id, "student_id": student.id, "student_name": student.display_name,
        "submitted_at": submission.submitted_at, "status": submission.status,
        "total_score": submission.total_score,
    } for submission, student in rows]


@router.get("/submissions/{submission_id}", tags=["grading"])
def get_submission(submission_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    submission = db.get(Submission, submission_id)
    if not submission:
        raise NotFoundError("提交")
    assignment = db.get(Assignment, submission.assignment_id)
    if user.role == "student" and submission.student_id != user.id:
        raise PermissionDeniedError()
    if user.role == "teacher":
        owned_course(db, assignment.course_id, user)
    if user.role == "parent":
        raise PermissionDeniedError()
    results = list(db.scalars(select(GradingResult).where(GradingResult.submission_id == submission.id)))
    questions = {item.id: item for item in db.scalars(select(Question).where(Question.assignment_id == assignment.id))}
    return {
        "id": submission.id, "assignment_id": assignment.id, "student_id": submission.student_id,
        "answers": submission.answers_json, "submitted_at": submission.submitted_at,
        "status": submission.status, "total_score": submission.total_score,
        "grading_results": [{
            "id": result.id, "question_id": result.question_id,
            "suggested_score": result.rule_score if result.rule_score is not None else result.ai_score,
            "final_score": result.final_score, "confidence": result.confidence,
            "feedback": result.feedback, "evidence": result.evidence_json, "status": result.status,
            "question": questions[result.question_id].stem, "question_type": questions[result.question_id].question_type,
            "standard_answer": questions[result.question_id].standard_answer,
        } for result in results],
    }


def normalized_question_options(question_type: str, options: list | None) -> list | None:
    if question_type == "true_false":
        return [{"key": "true", "content": "正确"}, {"key": "false", "content": "错误"}]
    return options


@router.post("/assignments/{assignment_id}/questions", tags=["assignment"])
async def add_question(assignment_id: int, data: QuestionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    assignment = db.get(Assignment, assignment_id)
    if not assignment: raise NotFoundError("作业")
    owned_course(db, assignment.course_id, user)
    options = normalized_question_options(data.question_type, data.options)
    standard_answer = data.standard_answer.strip() or await generate_standard_answer(db, assignment.course_id, data.question_type, data.stem, options)
    question = Question(
        assignment_id=assignment_id, question_type=data.question_type, stem=data.stem,
        standard_answer=standard_answer, options_json=options,
        rubric_json=data.rubric, knowledge_point_ids_json=data.knowledge_point_ids,
        max_score=data.max_score, sort_order=data.sort_order,
    )
    assignment.total_score = Decimal(assignment.total_score) + data.max_score
    db.add(question); db.commit(); db.refresh(question)
    return {"id": question.id, "max_score": question.max_score, "standard_answer": question.standard_answer}


@router.patch("/questions/{question_id}", tags=["assignment"])
async def update_question(question_id: int, data: QuestionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    question = db.get(Question, question_id)
    if not question:
        raise NotFoundError("题目")
    assignment = db.get(Assignment, question.assignment_id)
    owned_course(db, assignment.course_id, user)
    if db.scalar(select(Submission.id).where(Submission.assignment_id == assignment.id)):
        raise AppError("QUESTION_ALREADY_ANSWERED", "已有学生提交后不能修改题目，以免改变批改依据", 409)
    options = normalized_question_options(data.question_type, data.options)
    standard_answer = data.standard_answer.strip() or await generate_standard_answer(db, assignment.course_id, data.question_type, data.stem, options)
    old_score = Decimal(question.max_score)
    question.question_type = data.question_type; question.stem = data.stem
    question.standard_answer = standard_answer; question.options_json = options
    question.rubric_json = data.rubric; question.knowledge_point_ids_json = data.knowledge_point_ids
    question.max_score = data.max_score; question.sort_order = data.sort_order
    assignment.total_score = Decimal(assignment.total_score) - old_score + data.max_score
    db.commit(); db.refresh(question)
    return {"id": question.id, "max_score": question.max_score, "standard_answer": question.standard_answer}


@router.post("/assignments/{assignment_id}/publish", tags=["assignment"])
def publish_assignment(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    assignment = db.get(Assignment, assignment_id)
    if not assignment: raise NotFoundError("作业")
    owned_course(db, assignment.course_id, user)
    if not db.scalar(select(func.count(Question.id)).where(Question.assignment_id == assignment_id)):
        raise AppError("EMPTY_ASSIGNMENT", "作业至少需要一道题", 422)
    assignment.status = Status.published; db.commit()
    return {"id": assignment.id, "status": assignment.status}


def _answer_tokens(value) -> list[str]:
    values = value if isinstance(value, list) else re.split(r"[,，、;；\s]+", str(value))
    return sorted({str(item).strip().lower() for item in values if str(item).strip()})


async def _grade_submission(db: Session, submission: Submission, assignment: Assignment) -> dict:
    if db.scalar(select(GradingResult.id).where(GradingResult.submission_id == submission.id)):
        raise AppError("ALREADY_GRADED", "该提交已经生成批改结果，请直接查看", 409)
    questions = list(db.scalars(select(Question).where(Question.assignment_id == assignment.id)))
    answer_map = {int(x["question_id"]): x.get("answer", "") for x in submission.answers_json}
    chunks = KnowledgeService(db).course_context(assignment.course_id, 8)
    knowledge_context = "\n\n".join(chunk.content for chunk in chunks)
    output, total = [], Decimal("0")
    for question in questions:
        raw_answer = answer_map.get(question.id, "")
        answer = ",".join(str(value) for value in raw_answer) if isinstance(raw_answer, list) else str(raw_answer)
        if question.question_type in {"single_choice", "multiple_choice", "true_false"}:
            correct = _answer_tokens(raw_answer) == _answer_tokens(question.standard_answer)
            result = {"score": float(question.max_score if correct else 0), "confidence": 1.0, "feedback": "回答正确" if correct else "回答错误", "evidence": []}
            rule_score = Decimal(str(result["score"])); ai_score = None
        else:
            result = await grade_subjective(question, answer, knowledge_context)
            rule_score = None; ai_score = Decimal(str(result["score"]))
        score = rule_score if rule_score is not None else ai_score
        total += score or Decimal("0")
        grading = GradingResult(
            submission_id=submission.id, question_id=question.id, rule_score=rule_score,
            ai_score=ai_score, confidence=result["confidence"], feedback=result["feedback"],
            evidence_json=result.get("evidence", []), status=Status.pending_review,
        )
        db.add(grading); db.flush()
        output.append({"grading_result_id": grading.id, "question_id": question.id,
                       "standard_answer": question.standard_answer, **result})
    submission.total_score = total; submission.status = Status.pending_review
    db.commit()
    return {"submission_id": submission.id, "suggested_total": total, "results": output, "requires_review": True}


@router.post("/assignments/{assignment_id}/submissions", tags=["assignment"])
async def submit_assignment(assignment_id: int, data: SubmissionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("student"))):
    assignment = db.get(Assignment, assignment_id)
    if not assignment or assignment.status != Status.published: raise AppError("ASSIGNMENT_NOT_AVAILABLE", "作业未发布", 409)
    if db.scalar(select(Submission.id).where(Submission.assignment_id == assignment_id, Submission.student_id == user.id)):
        raise AppError("ALREADY_SUBMITTED", "该作业已经提交，不能重复提交", 409)
    question_ids = set(db.scalars(select(Question.id).where(Question.assignment_id == assignment_id)))
    answer_ids = {int(item.get("question_id", 0)) for item in data.answers}
    if not question_ids or not answer_ids.issubset(question_ids):
        raise AppError("INVALID_ANSWERS", "答案中包含不属于该作业的题目", 422)
    item = Submission(assignment_id=assignment_id, student_id=user.id, answers_json=data.answers)
    db.add(item); db.commit(); db.refresh(item)
    grading = await _grade_submission(db, item, assignment)
    return {"id": item.id, "status": item.status, "total_score": item.total_score, "grading": grading}


@router.post("/submissions/{submission_id}/grade", tags=["grading"])
async def grade_submission(submission_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    submission = db.get(Submission, submission_id)
    if not submission: raise NotFoundError("提交")
    assignment = db.get(Assignment, submission.assignment_id); owned_course(db, assignment.course_id, user)
    return await _grade_submission(db, submission, assignment)


@router.patch("/grading-results/{result_id}/review", tags=["grading"])
def review_grade(result_id: int, data: ReviewRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    result = db.get(GradingResult, result_id)
    if not result: raise NotFoundError("批改结果")
    question = db.get(Question, result.question_id)
    if data.final_score > question.max_score: raise AppError("SCORE_OUT_OF_RANGE", "最终分数不能超过题目满分", 422)
    result.final_score = data.final_score; result.feedback = data.feedback
    result.reviewer_id = user.id; result.status = Status.approved
    submission = db.get(Submission, result.submission_id)
    for point_id in question.knowledge_point_ids_json or []:
        ratio = float(data.final_score / question.max_score)
        level = "薄弱" if ratio < 0.6 else "待巩固" if ratio < 0.8 else "已掌握"
        db.add(MasterySnapshot(
            student_id=submission.student_id, knowledge_point_id=int(point_id),
            score=ratio, level=level, evidence_count=1, algorithm_version="v1",
        ))
    db.commit()
    pending = db.scalar(select(func.count(GradingResult.id)).where(GradingResult.submission_id == submission.id, GradingResult.status != Status.approved))
    if pending == 0:
        submission.status = Status.approved
        submission.total_score = db.scalar(select(func.sum(GradingResult.final_score)).where(GradingResult.submission_id == submission.id)) or 0
        db.commit()
    return {"id": result.id, "final_score": result.final_score, "status": result.status}


@router.post("/qa/sessions", tags=["qa"])
def create_qa_session(data: QASessionCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role in {"teacher", "admin"}:
        owned_course(db, data.course_id, user)
    else:
        visible_course(db, data.course_id, user)
    item = QASession(course_id=data.course_id, user_id=user.id, title=data.title)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "title": item.title}


@router.get("/qa/sessions", tags=["qa"])
def list_qa_sessions(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    visible_course(db, course_id, user)
    items = list(db.scalars(select(QASession).where(QASession.course_id == course_id, QASession.user_id == user.id).order_by(QASession.updated_at.desc()).limit(30)))
    return [{"id": item.id, "title": item.title, "updated_at": item.updated_at} for item in items]


@router.get("/qa/sessions/{session_id}/messages", tags=["qa"])
def list_qa_messages(session_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = db.get(QASession, session_id)
    if not session or session.user_id != user.id:
        raise NotFoundError("问答会话")
    items = list(db.scalars(select(QAMessage).where(QAMessage.session_id == session_id).order_by(QAMessage.id)))
    return [{"id": item.id, "role": item.role, "content": item.content, "citations": item.citations_json,
             "confidence": item.confidence, "insufficient": item.needs_teacher, "corrected_at": item.corrected_at,
             "correction_note": item.correction_note, "created_at": item.created_at} for item in items]


@router.post("/qa/sessions/{session_id}/messages", tags=["qa"])
async def ask(session_id: int, data: QAMessageCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = db.get(QASession, session_id)
    if not session or (session.user_id != user.id and user.role != "admin"): raise NotFoundError("问答会话")
    user_msg = QAMessage(session_id=session_id, role="user", content=data.content, trace_id=uuid.uuid4().hex)
    db.add(user_msg)
    answer = await KnowledgeService(db).answer(session.course_id, data.content)
    assistant_msg = QAMessage(
        session_id=session_id, role="assistant", content=answer.answer,
        citations_json=answer.citations, confidence=answer.confidence,
        needs_teacher=answer.insufficient_evidence, trace_id=answer.trace_id,
    )
    db.add(assistant_msg); db.commit(); db.refresh(assistant_msg)
    return {
        "id": assistant_msg.id, "answer": answer.answer, "citations": answer.citations,
        "confidence": answer.confidence, "insufficient_evidence": answer.insufficient_evidence,
        "trace_id": answer.trace_id,
    }


@router.get("/courses/{course_id}/qa-review", tags=["qa"])
def course_qa_review(course_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, course_id, user)
    sessions = list(db.scalars(select(QASession).where(QASession.course_id == course_id).order_by(QASession.updated_at.desc())))
    output = []
    for session in sessions:
        student = db.get(User, session.user_id)
        messages = list(db.scalars(select(QAMessage).where(QAMessage.session_id == session.id).order_by(QAMessage.id)))
        for index, message in enumerate(messages):
            if message.role != "user":
                continue
            answer = next((item for item in messages[index + 1:] if item.role == "assistant"), None)
            output.append({
                "session_id": session.id, "session_title": session.title,
                "student_id": student.id if student else None,
                "student_name": student.display_name if student else "未知用户",
                "question_id": message.id, "question": message.content, "asked_at": message.created_at,
                "answer_id": answer.id if answer else None, "answer": answer.content if answer else None,
                "confidence": answer.confidence if answer else None,
                "needs_teacher": answer.needs_teacher if answer else True,
                "corrected_at": answer.corrected_at if answer else None,
                "correction_note": answer.correction_note if answer else None,
            })
    return output


@router.patch("/qa/messages/{message_id}/correct", tags=["qa"])
def correct_qa_answer(message_id: int, data: QAAnswerCorrection, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    message = db.get(QAMessage, message_id)
    if not message or message.role != "assistant":
        raise NotFoundError("AI 回答")
    session = db.get(QASession, message.session_id)
    owned_course(db, session.course_id, user)
    if message.original_content is None:
        message.original_content = message.content
    message.content = data.content; message.correction_note = data.note
    message.corrected_by = user.id; message.corrected_at = datetime.utcnow(); message.needs_teacher = False
    db.add(Notification(
        user_id=session.user_id, notification_type="qa_correction",
        title="教师修正了课堂答疑回答",
        content=data.note or "你的一条课堂提问已由教师审核并修正，请重新查看。",
        link="/chat", notification_key=f"qa-correction-{message.id}-{uuid.uuid4().hex[:12]}",
    ))
    db.commit()
    return {"id": message.id, "content": message.content, "corrected_at": message.corrected_at}


def _topic_key(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())[:100]


@router.get("/courses/{course_id}/high-frequency", tags=["qa"])
def high_frequency_topics(course_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, course_id, user)
    questions = list(db.scalars(
        select(QAMessage.content).join(QASession, QASession.id == QAMessage.session_id)
        .where(QASession.course_id == course_id, QAMessage.role == "user")
    ))
    question_counts = Counter(_topic_key(value) for value in questions if value.strip())
    wrong_rows = db.execute(
        select(GradingResult, Question).join(Question, Question.id == GradingResult.question_id)
        .join(Assignment, Assignment.id == Question.assignment_id)
        .where(Assignment.course_id == course_id)
    ).all()
    wrong_counts = Counter()
    for result, question in wrong_rows:
        score = result.final_score if result.final_score is not None else result.ai_score if result.ai_score is not None else result.rule_score
        if score is not None and float(score) < float(question.max_score) * .6:
            wrong_counts[question.stem[:120]] += 1
    return {
        "course_id": course_id,
        "student_questions": [{"topic": key, "count": count} for key, count in question_counts.most_common(10)],
        "wrong_answer_topics": [{"topic": key, "count": count} for key, count in wrong_counts.most_common(10)],
        "focus": [key for key, _ in (question_counts + wrong_counts).most_common(8)],
    }


def create_due_notifications(db: Session, user: User) -> None:
    if user.role != "student":
        return
    now = datetime.utcnow(); deadline = now + timedelta(hours=48)
    course_ids = select(CourseMember.course_id).where(CourseMember.student_id == user.id, CourseMember.status == "active")
    submitted_ids = select(Submission.assignment_id).where(Submission.student_id == user.id)
    assignments = list(db.scalars(select(Assignment).where(
        Assignment.course_id.in_(course_ids), Assignment.status == Status.published,
        Assignment.due_at.is_not(None), Assignment.due_at >= now, Assignment.due_at <= deadline,
        Assignment.id.not_in(submitted_ids),
    )))
    changed = False
    for assignment in assignments:
        key = f"assignment-due-{assignment.id}-{user.id}"
        if not db.scalar(select(Notification.id).where(Notification.notification_key == key)):
            db.add(Notification(
                user_id=user.id, notification_type="assignment_due", title="作业即将截止",
                content=f"《{assignment.title}》将在 {assignment.due_at.strftime('%m月%d日 %H:%M')} 截止，请及时完成。",
                link=f"/assignments", notification_key=key,
            )); changed = True
    if changed:
        db.commit()


@router.get("/notifications", tags=["notifications"])
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    create_due_notifications(db, user)
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    items = list(db.scalars(stmt.order_by(Notification.created_at.desc()).limit(100)))
    return [{
        "id": item.id, "type": item.notification_type, "title": item.title,
        "content": item.content, "link": item.link, "read": item.read_at is not None,
        "created_at": item.created_at,
    } for item in items]


@router.patch("/notifications/{notification_id}/read", tags=["notifications"])
def read_notification(notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if not item:
        raise NotFoundError("通知")
    item.read_at = datetime.utcnow(); db.commit()
    return {"id": item.id, "read": True}


@router.get("/students/{student_id}/mastery", tags=["analytics"])
def mastery(student_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "student" and user.id != student_id: raise PermissionDeniedError()
    rows = list(db.scalars(select(MasterySnapshot).where(MasterySnapshot.student_id == student_id).order_by(MasterySnapshot.created_at.desc())))
    return [{"knowledge_point_id": x.knowledge_point_id, "score": x.score, "level": x.level, "evidence_count": x.evidence_count} for x in rows]


@router.get("/students/{student_id}/weak-profile", tags=["analytics"])
def weak_profile(student_id: int, course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "student" and user.id != student_id:
        raise PermissionDeniedError()
    if user.role in {"teacher", "admin"}:
        owned_course(db, course_id, user)
    elif user.role == "student":
        visible_course(db, course_id, user)
    else:
        raise PermissionDeniedError()
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise NotFoundError("学生")
    rows = db.execute(
        select(MasterySnapshot, KnowledgePoint)
        .join(KnowledgePoint, KnowledgePoint.id == MasterySnapshot.knowledge_point_id)
        .where(MasterySnapshot.student_id == student_id, KnowledgePoint.course_id == course_id)
        .order_by(MasterySnapshot.created_at.desc())
    ).all()
    latest = {}
    for snapshot, point in rows:
        latest.setdefault(point.id, (snapshot, point))
    weak = []
    service = KnowledgeService(db)
    for snapshot, point in latest.values():
        if snapshot.score >= .8:
            continue
        recommendations = service.keyword_search(course_id, point.name, 3)
        weak.append({
            "knowledge_point_id": point.id, "name": point.name, "description": point.description,
            "score": snapshot.score, "level": snapshot.level,
            "recommendations": [{"chunk_id": item.chunk_id, "filename": item.filename, "content_preview": item.content[:240]} for item in recommendations],
        })
    weak.sort(key=lambda item: item["score"])
    return {
        "student": {"id": student.id, "display_name": student.display_name},
        "course_id": course_id, "weak_count": len(weak), "weak_points": weak,
        "summary": "当前没有明显薄弱知识点" if not weak else f"发现 {len(weak)} 个需要优先巩固的知识点",
    }


@router.post("/students/{student_id}/learning-paths/generate", tags=["analytics"])
def generate_learning_path(student_id: int, course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "student" and user.id != student_id: raise PermissionDeniedError()
    points = list(db.scalars(select(MasterySnapshot).join(KnowledgePoint, KnowledgePoint.id == MasterySnapshot.knowledge_point_id).where(MasterySnapshot.student_id == student_id, KnowledgePoint.course_id == course_id).order_by(MasterySnapshot.score.asc())))
    seen, items = set(), []
    for snapshot in points:
        if snapshot.knowledge_point_id in seen: continue
        seen.add(snapshot.knowledge_point_id)
        if snapshot.score < .8:
            items.append({"knowledge_point_id": snapshot.knowledge_point_id, "priority": "high" if snapshot.score < .6 else "medium", "steps": ["知识点讲解", "例题学习", "针对性练习", "复测"]})
    version = (db.scalar(select(func.max(LearningPath.version)).where(LearningPath.student_id == student_id, LearningPath.course_id == course_id)) or 0) + 1
    path = LearningPath(student_id=student_id, course_id=course_id, version=version, items_json=items)
    db.add(path); db.commit(); db.refresh(path)
    return {"id": path.id, "version": path.version, "items": items}


@router.post("/reports/generate", tags=["reports"])
async def generate_report(data: ReportGenerateRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    owned_course(db, data.course_id, user)
    snapshots = list(db.scalars(select(MasterySnapshot).where(MasterySnapshot.student_id == data.student_id)))
    metrics = {"knowledge_points": len(snapshots), "average_mastery": round(sum(x.score for x in snapshots) / len(snapshots), 3) if snapshots else 0, "weak_points": [x.knowledge_point_id for x in snapshots if x.score < .6]}
    raw = await get_llm_provider().chat(
        "你是面向家长的学习沟通助手。只能解释给出的指标，不得编造数据；避免教育术语，语气客观、温和、可行动。",
        "请返回JSON对象，字段必须为：overview（本阶段一句话概况）、highlights（进步亮点数组）、needs_attention（需要关注的方面数组）、action_plan（家长可以在家配合的具体行动数组）、encouragement（给孩子的鼓励）、metrics_explanation（用通俗语言解释数据）。指标：" + json.dumps(metrics, ensure_ascii=False),
        True,
    )
    try: content = json.loads(raw)
    except json.JSONDecodeError: raise AppError("MODEL_OUTPUT_INVALID", "报告模型输出格式无效", 502)
    list_fields = ("highlights", "needs_attention", "action_plan")
    for field in list_fields:
        value = content.get(field, [])
        if isinstance(value, str):
            content[field] = [part.strip() for part in re.split(r"[\n；;]+", value) if part.strip()] or [value]
        elif not isinstance(value, list):
            content[field] = [str(value)] if value else []
    for field in ("overview", "encouragement", "metrics_explanation"):
        value = content.get(field, "")
        if isinstance(value, list):
            content[field] = "；".join(str(part) for part in value)
        elif not isinstance(value, str):
            content[field] = str(value or "")
    report = Report(**data.model_dump(), metrics_json=metrics, content_json=content, status=Status.pending_review)
    db.add(report); db.commit(); db.refresh(report)
    return {"id": report.id, "metrics": metrics, "content": content, "status": report.status}


@router.patch("/reports/{report_id}/review", tags=["reports"])
def review_report(report_id: int, data: ReportReviewRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    report = db.get(Report, report_id)
    if not report: raise NotFoundError("报告")
    owned_course(db, report.course_id, user)
    transitions = {
        "approve": Status.approved,
        "publish": Status.published,
        "reject": Status.draft,
    }
    if data.action == "publish" and report.status not in {Status.pending_review, Status.approved}:
        raise AppError("INVALID_REPORT_STATE", "只有待审核或已审核报告可以发布", 409)
    report.status = transitions[data.action]; report.reviewer_id = user.id
    db.commit()
    return {"id": report.id, "status": report.status, "comment": data.comment}


@router.get("/parent/students", tags=["reports"])
def parent_students(db: Session = Depends(get_db), user: User = Depends(require_roles("parent"))):
    rows = db.execute(select(ParentStudentLink, User).join(User, User.id == ParentStudentLink.student_id).where(ParentStudentLink.parent_id == user.id, ParentStudentLink.status == "active").order_by(User.display_name)).all()
    return [{"id": student.id, "display_name": student.display_name, "username": student.username} for _, student in rows]


@router.get("/parent/reports", tags=["reports"])
def parent_reports(student_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles("parent"))):
    student_ids = select(ParentStudentLink.student_id).where(ParentStudentLink.parent_id == user.id, ParentStudentLink.status == "active")
    if student_id is not None and not db.scalar(select(ParentStudentLink.id).where(ParentStudentLink.parent_id == user.id, ParentStudentLink.student_id == student_id, ParentStudentLink.status == "active")):
        raise PermissionDeniedError("该学生未与当前家长账号绑定")
    stmt = select(Report).where(Report.student_id.in_(student_ids), Report.status == Status.published)
    if student_id is not None:
        stmt = stmt.where(Report.student_id == student_id)
    reports = list(db.scalars(stmt.order_by(Report.period_end.desc())))
    return [{"id": x.id, "student_id": x.student_id, "course_id": x.course_id, "period_type": x.period_type, "metrics": x.metrics_json, "content": x.content_json, "status": x.status} for x in reports]
