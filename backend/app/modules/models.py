import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, DECIMAL, Enum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.db.base import Base, TimestampMixin


class Status(str, enum.Enum):
    draft = "draft"
    processing = "processing"
    ready = "ready"
    published = "published"
    pending_review = "pending_review"
    approved = "approved"
    failed = "failed"
    archived = "archived"


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ParentStudentLink(Base, TimestampMixin):
    __tablename__ = "parent_student_links"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    __table_args__ = (UniqueConstraint("parent_id", "student_id"),)


class Course(Base, TimestampMixin):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(100))
    grade_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.draft)


class CourseManager(Base, TimestampMixin):
    __tablename__ = "course_managers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("course_id", "user_id"),)


class CourseMember(Base, TimestampMixin):
    __tablename__ = "course_members"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(30), default="approved")
    status: Mapped[str] = mapped_column(String(30), default="active")
    __table_args__ = (UniqueConstraint("course_id", "student_id"),)


class CourseJoinRequest(Base, TimestampMixin):
    __tablename__ = "course_join_requests"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("course_id", "student_id"),)


class ClassGroup(Base, TimestampMixin):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    term: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.ready)
    __table_args__ = (UniqueConstraint("course_id", "name"),)


class ClassMember(Base, TimestampMixin):
    __tablename__ = "class_members"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    member_role: Mapped[str] = mapped_column(String(32))
    __table_args__ = (UniqueConstraint("class_id", "user_id"),)


class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class KnowledgePoint(Base, TimestampMixin):
    __tablename__ = "knowledge_points"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("course_id", "code"),)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(String(1000))
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    mime_type: Mapped[str] = mapped_column(String(120))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    dedup_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.processing)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("course_id", "dedup_key"),)


class WebImportDraft(Base, TimestampMixin):
    __tablename__ = "web_import_drafts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_url: Mapped[str] = mapped_column(String(2000))
    resolved_url: Mapped[str] = mapped_column(String(2000))
    source_domain: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(MEDIUMTEXT)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    confirmed_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    milvus_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("ft_document_chunks_content", "content", mysql_prefix="FULLTEXT"),
    )


class LessonResource(Base, TimestampMixin):
    __tablename__ = "lesson_resources"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    resource_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    content_json: Mapped[dict] = mapped_column(JSON)
    citations_json: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.draft)


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"), nullable=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_score: Mapped[Decimal] = mapped_column(DECIMAL(7, 2), default=0)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.draft)


class Question(Base, TimestampMixin):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    question_type: Mapped[str] = mapped_column(String(40))
    stem: Mapped[str] = mapped_column(Text)
    standard_answer: Mapped[str] = mapped_column(Text)
    options_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rubric_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    knowledge_point_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    material_type: Mapped[str] = mapped_column(String(30), default="exercise")
    max_score: Mapped[Decimal] = mapped_column(DECIMAL(7, 2))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Submission(Base, TimestampMixin):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    answers_json: Mapped[list] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_score: Mapped[Decimal | None] = mapped_column(DECIMAL(7, 2), nullable=True)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.pending_review)
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", "attempt_no", name="uq_submission_attempt"),)


class GradingResult(Base, TimestampMixin):
    __tablename__ = "grading_results"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    rule_score: Mapped[Decimal | None] = mapped_column(DECIMAL(7, 2), nullable=True)
    ai_score: Mapped[Decimal | None] = mapped_column(DECIMAL(7, 2), nullable=True)
    final_score: Mapped[Decimal | None] = mapped_column(DECIMAL(7, 2), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    feedback: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.pending_review)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("submission_id", "question_id"),)


class QASession(Base, TimestampMixin):
    __tablename__ = "qa_sessions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="新对话")
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.ready)


class QAMessage(Base, TimestampMixin):
    __tablename__ = "qa_messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("qa_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    needs_teacher: Mapped[bool] = mapped_column(Boolean, default=False)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    original_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    corrected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    notification_type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(String(1000))
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notification_key: Mapped[str] = mapped_column(String(180), unique=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class MasterySnapshot(Base, TimestampMixin):
    __tablename__ = "mastery_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(30))
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    algorithm_version: Mapped[str] = mapped_column(String(30), default="v1")


class LearningPath(Base, TimestampMixin):
    __tablename__ = "learning_paths"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    items_json: Mapped[list] = mapped_column(JSON)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.ready)


class Report(Base, TimestampMixin):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    period_type: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    metrics_json: Mapped[dict] = mapped_column(JSON)
    content_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.draft)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AsyncTask(Base, TimestampMixin):
    __tablename__ = "async_tasks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    task_type: Mapped[str] = mapped_column(String(80))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class KnowledgePointRelation(Base, TimestampMixin):
    __tablename__ = "knowledge_point_relations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    from_kp_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    to_kp_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(30), default="prerequisite")
    confidence: Mapped[float] = mapped_column(Float, default=0.85)
    source: Mapped[str] = mapped_column(String(50), default="ai")
    document_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (
        UniqueConstraint("from_kp_id", "to_kp_id", "relation_type"),
        Index("idx_kp_rel_course", "course_id", "relation_type"),
    )


class KnowledgePointGraph(Base, TimestampMixin):
    __tablename__ = "knowledge_point_graphs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    nodes_json: Mapped[list] = mapped_column(JSON, default=list)
    edges_json: Mapped[list] = mapped_column(JSON, default=list)
    generated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
