"""
# 放到：backend/app/api/knowledge_graph.py
# 说明：新增 API 路由，提供知识点图谱生成/查询/审核/学生掌握度接口
# 需要在 backend/app/api/router.py 中注册此路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, require_roles
from app.db.session import get_db
from app.core.exceptions import AppError
from app.modules.models import KnowledgePointGraph
from app.services.knowledge_graph import KnowledgeGraphService
from app.api.schemas import KnowledgeGraphGenerateRequest

router = APIRouter(prefix="/knowledge-graphs", tags=["knowledge-graph"])

@router.post("/generate")
async def generate_knowledge_graph(
    req: KnowledgeGraphGenerateRequest,
    db: Session = Depends(get_db),
    user = Depends(current_user),
):
    """从课程文档生成知识点图谱"""
    service = KnowledgeGraphService(db)
    graph = await service.generate_from_documents(
        user, req.course_id, req.document_ids
    )
    return {"task_id": f"kg-{graph.id}", "status": "completed"}

@router.get("/course/{course_id}")
def get_course_graph(
    course_id: int,
    db: Session = Depends(get_db),
    user = Depends(current_user),
):
    """获取课程知识点图谱"""
    service = KnowledgeGraphService(db)
    return service.get_graph(course_id)

@router.get("/course/{course_id}/points")
def get_course_knowledge_points(
    course_id: int,
    db: Session = Depends(get_db),
    user = Depends(current_user),
):
    """获取课程知识点列表（用于下拉选择）"""
    service = KnowledgeGraphService(db)
    return service.get_knowledge_points(course_id)

@router.post("/approve/{graph_id}")
def approve_graph(
    graph_id: int,
    db: Session = Depends(get_db),
    user = Depends(current_user),
):
    """教师审核通过图谱"""
    from datetime import datetime
    graph = db.get(KnowledgePointGraph, graph_id)
    if not graph:
        raise AppError("NOT_FOUND", "图谱不存在", 404)
    graph.status = "approved"
    graph.reviewed_by = user.id
    graph.reviewed_at = datetime.utcnow()
    db.commit()
    return {"status": "approved"}

@router.get("/student-mastery/{student_id}/course/{course_id}")
def get_student_mastery(
    student_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    user = Depends(current_user),
):
    """获取学生知识点掌握度"""
    service = KnowledgeGraphService(db)
    if user.role == "student" and user.id != student_id:
        raise AppError("FORBIDDEN", "无权查看他人数据", 403)
    return service.get_student_mastery(student_id, course_id)