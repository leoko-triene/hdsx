"""Knowledge graph extraction, storage and student mastery analysis."""
from datetime import datetime

from sqlalchemy import func, select, delete
from sqlalchemy.orm import Session

from app.agents.knowledge_graph import KnowledgeGraphAgent
from app.agents.structured import extract_json
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.modules.models import (
    Assignment,
    CourseMember,
    Document,
    DocumentChunk,
    KnowledgePoint,
    KnowledgePointGraph,
    KnowledgePointRelation,
    MasterySnapshot,
    Question,
    Status,
)


class KnowledgeGraphService:
    def __init__(self, db: Session):
        self.db = db

    def _owned_course(self, course_id: int, user) -> None:
        from app.api.router import owned_course
        owned_course(self.db, course_id, user)

    def _visible_course(self, course_id: int, user) -> None:
        from app.api.router import visible_course
        visible_course(self.db, course_id, user)

    def _assert_student_access(self, student_id: int, course_id: int, user) -> None:
        """Validate that *user* may view *student_id*'s data for *course_id*."""
        if user.role == "student" and user.id != student_id:
            raise PermissionDeniedError("无权查看他人数据")
        if user.role == "parent":
            from app.modules.models import ParentStudentLink
            linked = self.db.scalar(
                select(ParentStudentLink.id).where(
                    ParentStudentLink.parent_id == user.id,
                    ParentStudentLink.student_id == student_id,
                    ParentStudentLink.status == "active",
                )
            )
            if not linked:
                raise PermissionDeniedError("未关联该学生")
            self._visible_course(course_id, user)
        elif user.role in {"teacher", "admin"}:
            self._owned_course(course_id, user)
            enrolled = self.db.scalar(
                select(CourseMember.id).where(
                    CourseMember.course_id == course_id,
                    CourseMember.student_id == student_id,
                    CourseMember.status == "active",
                )
            )
            if not enrolled:
                raise NotFoundError("课程学生")
        else:
            raise PermissionDeniedError()

    async def generate_from_documents(
        self, user, course_id: int, document_ids: list[int] | None = None
    ) -> KnowledgePointGraph:
        self._owned_course(course_id, user)

        stmt = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.course_id == course_id,
                Document.status == Status.ready,
            )
        )
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))

        rows = self.db.execute(stmt.limit(50)).all()
        if not rows:
            raise AppError("NO_DOCUMENTS", "没有可用文档", 422)

        context = "\n\n".join(
            f"[{doc.filename}] {chunk.content}" for chunk, doc in rows
        )[:6000]

        result = await KnowledgeGraphAgent().run(
            {"course_id": course_id, "context": context},
            output_schema={
                "type": "object",
                "required": ["knowledge_points", "relations"],
                "properties": {
                    "knowledge_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["code", "name"],
                            "properties": {
                                "code": {"type": "string"},
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "chapter_id": {"type": ["integer", "null"]},
                                "level": {"type": "integer"},
                            },
                        },
                    },
                    "relations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["from_code", "to_code"],
                            "properties": {
                                "from_code": {"type": "string"},
                                "to_code": {"type": "string"},
                                "relation_type": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                        },
                    },
                },
            },
        )
        raw = str(result.content) if result.content is not None else ""
        data = extract_json(raw) or {}
        knowledge_points = data.get("knowledge_points", [])
        relations = data.get("relations", [])

        if not knowledge_points:
            raise AppError("KG_EXTRACTION_EMPTY", "未能从文档中抽取到知识点", 422)

        try:
            code_to_id = self._upsert_knowledge_points(course_id, knowledge_points)
            self._replace_relations(course_id, relations, code_to_id, rows)
            next_version = (
                self.db.scalar(
                    select(func.max(KnowledgePointGraph.version)).where(
                        KnowledgePointGraph.course_id == course_id
                    )
                )
                or 0
            ) + 1

            graph = KnowledgePointGraph(
                course_id=course_id,
                version=next_version,
                status="draft",
                nodes_json=[
                    {
                        "id": code_to_id[kp["code"]],
                        "code": kp["code"],
                        "name": kp["name"],
                        "description": kp.get("description"),
                        "level": kp.get("level", 1),
                    }
                    for kp in knowledge_points
                    if kp["code"] in code_to_id
                ],
                edges_json=[
                    {
                        "from": code_to_id[rel["from_code"]],
                        "to": code_to_id[rel["to_code"]],
                        "type": rel.get("relation_type", "prerequisite"),
                        "confidence": rel.get("confidence", 0.85),
                    }
                    for rel in relations
                    if rel.get("from_code") in code_to_id
                    and rel.get("to_code") in code_to_id
                    and rel.get("from_code") != rel.get("to_code")
                ],
                generated_by=user.id,
            )
            self.db.add(graph)
            self.db.commit()
            self.db.refresh(graph)
            return graph
        except Exception as exc:
            self.db.rollback()
            raise AppError("KG_GENERATION_FAILED", f"图谱生成失败: {exc}", 500) from exc

    def _upsert_knowledge_points(self, course_id: int, items: list[dict]) -> dict[str, int]:
        code_to_id = {}
        for item in items:
            code = item.get("code")
            name = item.get("name")
            if not code or not name:
                continue
            existing = self.db.scalar(
                select(KnowledgePoint).where(
                    KnowledgePoint.course_id == course_id,
                    KnowledgePoint.code == code,
                )
            )
            if existing:
                existing.name = name
                existing.description = item.get("description") or existing.description
                existing.chapter_id = item.get("chapter_id") or existing.chapter_id
                self.db.flush()
                code_to_id[code] = existing.id
            else:
                kp = KnowledgePoint(
                    course_id=course_id,
                    code=code,
                    name=name,
                    description=item.get("description"),
                    chapter_id=item.get("chapter_id"),
                )
                self.db.add(kp)
                self.db.flush()
                code_to_id[code] = kp.id
        return code_to_id

    def _replace_relations(
        self,
        course_id: int,
        relations: list[dict],
        code_to_id: dict[str, int],
        rows: list,
    ) -> None:
        self.db.execute(
            delete(KnowledgePointRelation).where(
                KnowledgePointRelation.course_id == course_id
            )
        )
        document_ids = list({doc.id for _, doc in rows})
        for rel in relations:
            from_code = rel.get("from_code")
            to_code = rel.get("to_code")
            from_id = code_to_id.get(from_code)
            to_id = code_to_id.get(to_code)
            if not from_id or not to_id or from_id == to_id:
                continue
            self.db.add(
                KnowledgePointRelation(
                    course_id=course_id,
                    from_kp_id=from_id,
                    to_kp_id=to_id,
                    relation_type=rel.get("relation_type", "prerequisite"),
                    confidence=float(rel.get("confidence", 0.85)),
                    source="ai",
                    document_ids_json=document_ids,
                )
            )

    def get_graph(self, course_id: int) -> KnowledgePointGraph:
        graph = self.db.scalar(
            select(KnowledgePointGraph)
            .where(KnowledgePointGraph.course_id == course_id)
            .order_by(KnowledgePointGraph.version.desc())
        )
        if not graph:
            raise NotFoundError("知识点图谱")
        return graph

    def get_knowledge_points(self, course_id: int) -> list[dict]:
        kps = self.db.scalars(
            select(KnowledgePoint).where(KnowledgePoint.course_id == course_id)
        ).all()
        return [
            {
                "id": kp.id,
                "code": kp.code,
                "name": kp.name,
                "description": kp.description,
                "chapter_id": kp.chapter_id,
            }
            for kp in kps
        ]

    def get_student_mastery(self, student_id: int, course_id: int) -> dict:
        # Aggregate how many published questions reference each knowledge point.
        questions = self.db.execute(
            select(Question, Assignment).join(
                Assignment, Assignment.id == Question.assignment_id
            ).where(
                Assignment.course_id == course_id,
                Assignment.status == Status.published,
            )
        ).all()

        kp_question_counts = {}
        for question, _ in questions:
            for kp_id in question.knowledge_point_ids_json or []:
                kp_question_counts[kp_id] = kp_question_counts.get(kp_id, 0) + 1

        # Reuse existing MasterySnapshot records for the latest score per KP.
        rows = self.db.execute(
            select(MasterySnapshot, KnowledgePoint)
            .join(KnowledgePoint, KnowledgePoint.id == MasterySnapshot.knowledge_point_id)
            .where(
                MasterySnapshot.student_id == student_id,
                KnowledgePoint.course_id == course_id,
            )
            .order_by(MasterySnapshot.created_at.desc())
        ).all()

        latest = {}
        for snapshot, point in rows:
            latest.setdefault(point.id, (snapshot, point))

        result = []
        for kp_id, (snapshot, point) in latest.items():
            total = kp_question_counts.get(kp_id, 0)
            accuracy = max(0.0, min(1.0, snapshot.score))
            level = (
                "mastered" if accuracy >= 0.9
                else "proficient" if accuracy >= 0.7
                else "developing" if accuracy >= 0.5
                else "weak"
            )
            result.append({
                "knowledge_point_id": kp_id,
                "knowledge_point_name": point.name,
                "total_questions": total,
                "correct_count": round(accuracy * total) if total else 0,
                "accuracy_rate": round(accuracy, 2),
                "level": level,
            })

        result.sort(key=lambda x: x["accuracy_rate"])
        weak = [r for r in result if r["level"] in ("weak", "developing")]
        return {
            "student_id": student_id,
            "course_id": course_id,
            "knowledge_points": result,
            "weak_areas": [r["knowledge_point_name"] for r in weak],
            "recommended_path": [r["knowledge_point_name"] for r in result if r["level"] == "weak"][:5],
        }

    def approve_graph(self, graph_id: int, user) -> KnowledgePointGraph:
        graph = self.db.get(KnowledgePointGraph, graph_id)
        if not graph:
            raise NotFoundError("知识点图谱")
        self._owned_course(graph.course_id, user)
        graph.status = "approved"
        graph.reviewed_by = user.id
        graph.reviewed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(graph)
        return graph
