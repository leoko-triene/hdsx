"""
# 放到：backend/app/services/knowledge_graph.py
# 说明：知识点图谱核心业务逻辑，包括从文档抽取、图谱存储、学生掌握度分析
"""
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.agents.structured import extract_json, validate_or_fallback
from app.core.exceptions import AppError
from app.integrations.ollama import OllamaClient
from app.modules.models import (
    Assignment, CourseManager, Document, DocumentChunk,
    GradingResult, KnowledgePoint, KnowledgePointGraph,
    KnowledgePointRelation, Question, Status, Submission,
)
from pydantic import BaseModel, Field

class ExtractedKnowledgePoint(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    chapter_id: int | None = None
    level: int = 1

class ExtractedRelation(BaseModel):
    from_code: str = Field(min_length=1)
    to_code: str = Field(min_length=1)
    relation_type: str = Field(pattern="^(prerequisite|related|contains)$")
    confidence: float = Field(ge=0, le=1)

class ExtractionOutput(BaseModel):
    knowledge_points: list[ExtractedKnowledgePoint]
    relations: list[ExtractedRelation]

class KnowledgeGraphService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_course_access(self, user, course_id: int) -> None:
        if user.role == "admin":
            return
        if user.role == "teacher":
            allowed = self.db.scalar(
                select(CourseManager.id).where(
                    CourseManager.course_id == course_id,
                    CourseManager.user_id == user.id
                )
            )
        else:
            allowed = None
        if not allowed:
            raise AppError("COURSE_ACCESS_DENIED", "无权操作该课程", 403)

    def _build_extraction_prompt(self, context: str) -> str:
        return (
            "从以下教材内容中提取知识点，输出JSON。\n\n"
            "要求：\n"
            "1. knowledge_points: 每个知识点有 code(如KP-01-001)、name、description、level(1基础/2核心/3应用)\n"
            "2. relations: 关系有 from_code、to_code、relation_type(prerequisite/related/contains)、confidence(0-1)\n\n"
            "只输出纯JSON，不要任何解释或markdown代码块。\n\n"
            "教材内容：\n"
            f"{context}\n\n"
            "输出格式："
            '{"knowledge_points":[{"code":"KP-01-001","name":"知识点名称","description":"描述","level":1}],'
            '"relations":[{"from_code":"KP-01-001","to_code":"KP-01-002","relation_type":"prerequisite","confidence":0.85}]}'
        )

    async def generate_from_documents(
        self, user, course_id: int, document_ids: list[int] | None = None
    ) -> KnowledgePointGraph:
        self._ensure_course_access(user, course_id)

        stmt = select(DocumentChunk, Document).join(
            Document, Document.id == DocumentChunk.document_id
        ).where(
            Document.course_id == course_id,
            Document.status == Status.ready
        )
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))

        rows = self.db.execute(stmt.limit(50)).all()
        if not rows:
            raise AppError("NO_DOCUMENTS", "没有可用文档", 422)

        context = "\n\n".join([
            f"[{doc.filename}] {chunk.content}"
            for chunk, doc in rows
        ])[:3000]

        prompt = self._build_extraction_prompt(context)
        raw = await OllamaClient().chat("你是一个教育内容分析助手，必须只输出JSON格式", prompt)

        # 调试：打印 AI 原始响应，方便排查格式问题
        print(f"[KG DEBUG] AI raw response (first 800 chars): {str(raw)[:800]}")

        output = validate_or_fallback(
            raw,
            ExtractionOutput,
            lambda: {"knowledge_points": [], "relations": []}
        )

        print(f"[KG DEBUG] Parsed: {len(output.knowledge_points)} knowledge_points, {len(output.relations)} relations")

        code_to_id = {}
        for kp in output.knowledge_points:
            existing = self.db.scalar(
                select(KnowledgePoint.id).where(
                    KnowledgePoint.course_id == course_id,
                    KnowledgePoint.code == kp.code
                )
            )
            if existing:
                code_to_id[kp.code] = existing
            else:
                new_kp = KnowledgePoint(
                    course_id=course_id,
                    code=kp.code,
                    name=kp.name,
                    description=kp.description,
                    chapter_id=kp.chapter_id,
                )
                self.db.add(new_kp)
                self.db.flush()
                code_to_id[kp.code] = new_kp.id

        self.db.execute(
            delete(KnowledgePointRelation).where(
                KnowledgePointRelation.course_id == course_id
            )
        )
        for rel in output.relations:
            from_id = code_to_id.get(rel.from_code)
            to_id = code_to_id.get(rel.to_code)
            if from_id and to_id and from_id != to_id:
                self.db.add(KnowledgePointRelation(
                    course_id=course_id,
                    from_kp_id=from_id,
                    to_kp_id=to_id,
                    relation_type=rel.relation_type,
                    confidence=rel.confidence,
                    source="ai",
                    document_ids_json=[d.id for _, d in rows],
                ))

        graph = KnowledgePointGraph(
            course_id=course_id,
            version=1,
            status="draft",
            nodes_json=[
                {"id": code_to_id[kp.code], "code": kp.code, "name": kp.name,
                 "description": kp.description, "level": kp.level}
                for kp in output.knowledge_points if kp.code in code_to_id
            ],
            edges_json=[
                {"from": code_to_id[rel.from_code], "to": code_to_id[rel.to_code],
                 "type": rel.relation_type, "confidence": rel.confidence}
                for rel in output.relations
                if rel.from_code in code_to_id and rel.to_code in code_to_id
            ],
            generated_by=user.id,
        )
        self.db.add(graph)
        self.db.commit()
        return graph

    def get_graph(self, course_id: int) -> dict:
        graph = self.db.scalar(
            select(KnowledgePointGraph).where(
                KnowledgePointGraph.course_id == course_id
            ).order_by(KnowledgePointGraph.id.desc())
        )
        if not graph:
            raise AppError("GRAPH_NOT_FOUND", "该课程尚未生成知识点图谱", 404)
        return {
            "id": graph.id,
            "course_id": graph.course_id,
            "version": graph.version,
            "status": graph.status,
            "nodes": graph.nodes_json,
            "edges": graph.edges_json,
        }

    def get_knowledge_points(self, course_id: int) -> list[dict]:
        kps = self.db.scalars(
            select(KnowledgePoint).where(KnowledgePoint.course_id == course_id)
        ).all()
        return [
            {"id": kp.id, "code": kp.code, "name": kp.name,
             "description": kp.description, "chapter_id": kp.chapter_id}
            for kp in kps
        ]

    def get_student_mastery(self, student_id: int, course_id: int) -> dict:
        questions = self.db.execute(
            select(Question, Assignment).join(
                Assignment, Assignment.id == Question.assignment_id
            ).where(
                Assignment.course_id == course_id,
                Assignment.status == Status.published
            )
        ).all()

        kp_stats = {}
        for q, _ in questions:
            for kp_id in (q.knowledge_point_ids_json or []):
                if kp_id not in kp_stats:
                    kp_stats[kp_id] = {"total": 0, "correct": 0}
                kp_stats[kp_id]["total"] += 1

        submissions = self.db.execute(
            select(Submission, GradingResult, Question).join(
                GradingResult, GradingResult.submission_id == Submission.id
            ).join(
                Question, Question.id == GradingResult.question_id
            ).where(
                Submission.student_id == student_id,
                Submission.assignment_id.in_([a.id for _, a in questions])
            )
        ).all()

        for sub, gr, q in submissions:
            for kp_id in (q.knowledge_point_ids_json or []):
                if kp_id in kp_stats and gr.final_score is not None and gr.final_score >= q.max_score * 0.6:
                    kp_stats[kp_id]["correct"] += 1

        result = []
        for kp_id, stats in kp_stats.items():
            kp = self.db.scalar(select(KnowledgePoint).where(KnowledgePoint.id == kp_id))
            if not kp:
                continue
            accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            level = "mastered" if accuracy >= 0.9 else "proficient" if accuracy >= 0.7 else "developing" if accuracy >= 0.5 else "weak"
            result.append({
                "knowledge_point_id": kp_id,
                "knowledge_point_name": kp.name,
                "total_questions": stats["total"],
                "correct_count": stats["correct"],
                "accuracy_rate": round(accuracy, 2),
                "level": level,
            })

        return {
            "student_id": student_id,
            "course_id": course_id,
            "knowledge_points": sorted(result, key=lambda x: x["accuracy_rate"]),
            "weak_areas": [r["knowledge_point_name"] for r in result if r["level"] in ["weak", "developing"]],
            "recommended_path": [r["knowledge_point_name"] for r in result if r["level"] == "weak"][:5],
        }
