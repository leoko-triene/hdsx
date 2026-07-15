"""Knowledge graph API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, require_roles
from app.api.schemas import (
    KnowledgeGraphDetail,
    KnowledgeGraphGenerateRequest,
    KnowledgeGraphGenerateResponse,
    KnowledgePointNode,
    StudentKnowledgeProfile,
)
from app.db.session import get_db
from app.modules.models import User
from app.services.knowledge_graph import KnowledgeGraphService

router = APIRouter(prefix="/knowledge-graphs", tags=["knowledge-graph"])


def _to_detail(graph) -> dict:
    return {
        "id": graph.id,
        "course_id": graph.course_id,
        "version": graph.version,
        "status": graph.status,
        "nodes": graph.nodes_json or [],
        "edges": graph.edges_json or [],
        "generated_by": graph.generated_by,
        "reviewed_by": graph.reviewed_by,
        "reviewed_at": graph.reviewed_at.isoformat() if graph.reviewed_at else None,
        "created_at": graph.created_at.isoformat() if graph.created_at else None,
    }


@router.post("/generate", response_model=KnowledgeGraphGenerateResponse)
async def generate_knowledge_graph(
    req: KnowledgeGraphGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("teacher", "admin")),
):
    """Extract a knowledge graph from course documents."""
    service = KnowledgeGraphService(db)
    graph = await service.generate_from_documents(user, req.course_id, req.document_ids)
    return {"task_id": f"kg-{graph.id}", "status": "completed"}


@router.get("/course/{course_id}")
def get_course_graph(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("teacher", "admin")),
):
    """Get the latest knowledge graph for a course."""
    service = KnowledgeGraphService(db)
    graph = service.get_graph(course_id)
    return _to_detail(graph)


@router.get("/course/{course_id}/points", response_model=list[KnowledgePointNode])
def get_course_knowledge_points(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """List knowledge points for a course (used by selectors)."""
    service = KnowledgeGraphService(db)
    # Teachers/admins must manage the course; students must be enrolled.
    if user.role in {"teacher", "admin"}:
        service._owned_course(course_id, user)
    else:
        service._visible_course(course_id, user)
    return service.get_knowledge_points(course_id)


@router.post("/approve/{graph_id}")
def approve_graph(
    graph_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("teacher", "admin")),
):
    """Approve a generated knowledge graph."""
    service = KnowledgeGraphService(db)
    graph = service.approve_graph(graph_id, user)
    return {"status": graph.status, "id": graph.id}


@router.get("/student-mastery/{student_id}/course/{course_id}", response_model=StudentKnowledgeProfile)
def get_student_mastery(
    student_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Get a student's knowledge point mastery for a course."""
    service = KnowledgeGraphService(db)
    service._assert_student_access(student_id, course_id, user)
    return service.get_student_mastery(student_id, course_id)
