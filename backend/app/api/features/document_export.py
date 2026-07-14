"""备课资料导出功能：生成 docx/pptx 并下载。"""

import re
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import owned_course, require_roles
from app.api.registry import register_feature_router
from app.api.schemas import DocumentExportRequest, GeneratedDocumentOut
from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.db.session import get_db
from app.modules.models import GeneratedDocument, LessonResource, Status, User

router = APIRouter(tags=["lesson"])
register_feature_router(router)


@router.post("/lesson-resources/{resource_id}/export")
def export_lesson_resource(
    resource_id: int,
    data: DocumentExportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("teacher", "admin")),
):
    """生成 docx/pptx 并直接返回文件流。"""
    from app.services.document_export import export_from_resource

    item = db.get(LessonResource, resource_id)
    if not item or (item.creator_id != user.id and user.role != "admin"):
        raise NotFoundError("备课记录")
    owned_course(db, item.course_id, user)
    settings = get_settings()
    record = export_from_resource(item, data.doc_type, Path(settings.storage_root))
    db.add(record)
    db.commit()
    db.refresh(record)

    path = Path(record.storage_path)
    safe_title = re.sub(r'[\\/:*?"<>|｜]', "_", record.title).strip()
    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if record.doc_type == "docx"
        else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    return FileResponse(
        path,
        media_type=media_type,
        filename=f"{safe_title}.{record.doc_type}",
    )


@router.get("/generated-documents", response_model=list[GeneratedDocumentOut])
def list_generated_documents(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("teacher", "admin")),
):
    stmt = select(GeneratedDocument)
    if course_id:
        owned_course(db, course_id, user)
        stmt = stmt.where(GeneratedDocument.course_id == course_id)
    else:
        if user.role != "admin":
            stmt = stmt.where(GeneratedDocument.creator_id == user.id)
    stmt = stmt.order_by(GeneratedDocument.created_at.desc()).limit(200)
    return db.execute(stmt).scalars().all()


@router.get("/generated-documents/{document_id}/download")
def download_generated_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("teacher", "admin")),
):
    item = db.get(GeneratedDocument, document_id)
    if not item or (item.creator_id != user.id and user.role != "admin"):
        raise NotFoundError("导出记录")
    if item.status != Status.ready:
        raise AppError("DOCUMENT_NOT_READY", "文件尚未生成或生成失败", 400)
    path = Path(item.storage_path)
    if not path.exists():
        raise AppError("FILE_NOT_FOUND", "文件已丢失", 404)
    safe_title = re.sub(r'[\\/:*?"<>|｜]', "_", item.title).strip()
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument."
        + ("wordprocessingml.document" if item.doc_type == "docx" else "presentationml.presentation"),
        filename=f"{safe_title}.{item.doc_type}",
    )
