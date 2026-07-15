from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    display_name: str
    role: str = Field(pattern="^(admin|teacher|student|parent)$")
    email: str | None = None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    email: str | None = None
    role: str = Field(default="student", pattern="^(student|teacher|parent)$")
    student_usernames: list[str] = Field(default_factory=list, max_length=20)


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    email: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(ORMModel):
    id: int
    public_id: str
    username: str
    email: str | None
    display_name: str
    role: str
    is_active: bool


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=100)
    grade_level: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=5000)


class CourseUpdate(CourseCreate):
    pass


class CourseOut(ORMModel):
    id: int
    public_id: str
    name: str
    subject: str
    grade_level: str | None
    description: str | None
    owner_id: int
    status: str
    is_manager: bool = False


class ChapterCreate(BaseModel):
    title: str
    parent_id: int | None = None
    sort_order: int = 0


class KnowledgePointCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    chapter_id: int | None = None


class JoinRequestCreate(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class JoinRequestReview(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str | None = Field(default=None, max_length=500)


class CourseManagerAdd(BaseModel):
    user_id: int


class SearchRequest(BaseModel):
    course_id: int
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=30)


class WebSearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class WebImportPreviewRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class WebImportConfirmRequest(BaseModel):
    category: str = Field(default="web_reference", pattern="^(web_reference|textbook|courseware|extension)$")


class LessonGenerateRequest(BaseModel):
    course_id: int
    chapter_id: int | None = None
    chapter_title: str
    resource_type: str = Field(pattern="^(lesson_plan|lecture|ppt_outline|exercise)$")
    audience: str = "本科生"
    duration_minutes: int = Field(default=45, ge=10, le=240)
    requirements: str | None = None


class AssignmentCreate(BaseModel):
    course_id: int
    class_id: int | None = None
    title: str
    description: str | None = None
    due_at: datetime | None = None


class AssignmentMaterialGenerate(BaseModel):
    document_ids: list[int] = Field(min_length=1, max_length=10)
    chapter_or_topic: str = Field(min_length=1, max_length=300)
    single_choice_count: int = Field(default=2, ge=0, le=10)
    multiple_choice_count: int = Field(default=1, ge=0, le=10)
    true_false_count: int = Field(default=1, ge=0, le=10)
    short_answer_count: int = Field(default=2, ge=0, le=10)
    essay_count: int = Field(default=1, ge=0, le=10)

    @model_validator(mode="after")
    def validate_total_count(self):
        total = sum((self.single_choice_count, self.multiple_choice_count,
                     self.true_false_count, self.short_answer_count, self.essay_count))
        if total < 1:
            raise ValueError("至少生成一道题")
        if total > 10:
            raise ValueError("单次最多生成 10 道题")
        return self


class QuestionCreate(BaseModel):
    question_type: str = Field(pattern="^(single_choice|multiple_choice|true_false|short_answer|essay)$")
    stem: str
    standard_answer: str = ""
    explanation: str | None = None
    options: list[dict] | None = None
    rubric: list[dict] | None = None
    knowledge_point_ids: list[int] = Field(default_factory=list)
    max_score: Decimal = Field(gt=0)
    sort_order: int = 0


class SubmissionCreate(BaseModel):
    answers: list[dict]


class ReviewRequest(BaseModel):
    final_score: Decimal = Field(ge=0)
    feedback: str


class ParentLinkCreate(BaseModel):
    parent_id: int
    student_id: int


class ReportReviewRequest(BaseModel):
    action: str = Field(pattern="^(approve|publish|reject)$")
    comment: str | None = None


class QASessionCreate(BaseModel):
    course_id: int
    title: str = "新对话"


class QASessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class QAMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    mode: str = Field(default="auto", pattern="^(auto|direct)$")


class QAAnswerCorrection(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    note: str | None = Field(default=None, max_length=500)


class ReportGenerateRequest(BaseModel):
    student_id: int
    course_id: int
    period_type: str = Field(pattern="^(week|month)$")
    period_start: datetime
    period_end: datetime


class ModelSettingsUpdate(BaseModel):
    llm_provider: str = Field(pattern="^(ollama|openai_compatible)$")
    llm_base_url: str = Field(min_length=8, max_length=2000)
    llm_model: str = Field(min_length=1, max_length=255)
    llm_api_key: str | None = Field(default=None, max_length=4000)
    llm_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    clear_llm_api_key: bool = False
    embedding_provider: str = Field(pattern="^(ollama|openai_compatible)$")
    embedding_base_url: str = Field(min_length=8, max_length=2000)
    embedding_model: str = Field(min_length=1, max_length=255)
    embedding_api_key: str | None = Field(default=None, max_length=4000)
    clear_embedding_api_key: bool = False
    embedding_dimension: int = Field(ge=1, le=65536)
    vector_collection: str = Field(min_length=1, max_length=255)
    keep_alive: str = Field(default="-1", min_length=1, max_length=30)


class KnowledgePointNode(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    chapter_id: int | None = None
    level: int = 1


class KnowledgePointEdge(BaseModel):
    from_id: int
    to_id: int
    relation_type: str = "prerequisite"
    confidence: float = 0.85


class KnowledgeGraphGenerateRequest(BaseModel):
    course_id: int
    document_ids: list[int] | None = None
    chapter_id: int | None = None


class KnowledgeGraphGenerateResponse(BaseModel):
    task_id: str
    status: str = "queued"


class KnowledgeGraphDetail(BaseModel):
    id: int
    course_id: int
    version: int
    status: str
    nodes: list[KnowledgePointNode]
    edges: list[KnowledgePointEdge]
    generated_by: int | None = None
    reviewed_by: int | None = None
    reviewed_at: str | None = None
    created_at: str


class KnowledgePointLinkRequest(BaseModel):
    question_id: int
    knowledge_point_ids: list[int] = Field(min_length=1)


class KnowledgePointMastery(BaseModel):
    knowledge_point_id: int
    knowledge_point_name: str
    total_questions: int
    correct_count: int
    accuracy_rate: float
    level: str


class StudentKnowledgeProfile(BaseModel):
    student_id: int
    course_id: int
    knowledge_points: list[KnowledgePointMastery]
    weak_areas: list[str]
    recommended_path: list[str]
