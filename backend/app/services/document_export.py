"""将备课资源（LessonResource）导出为 Word 或 PPT。"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from docx import Document as DocxDocument
from docx.shared import Inches, Pt
from pptx import Presentation
from pptx.util import Inches as PptxInches
from pptx.util import Pt as PptxPt

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.models import GeneratedDocument, LessonResource, Status


# 来源资源类型 -> 允许导出的文档类型
_ALLOWED_EXPORTS: dict[str, set[str]] = {
    "lesson_plan": {"docx"},
    "lecture": {"docx"},
    "ppt_outline": {"pptx"},
    "exercise": {"docx"},
}


def _extract_slide_title(line: str) -> str | None:
    """从二级标题行中提取 slide 标题。"""
    stripped = line.strip()
    if not stripped.startswith("##"):
        return None
    text = stripped.lstrip("#").strip()
    # 匹配 "第1页｜标题" / "第 1 页｜标题" / "第1页:标题" / "第1页 | 标题" / "1. 标题" / "幻灯片 1：标题"
    patterns = [
        r"第\s*\d+\s*页\s*[｜|:：\|]\s*(.+)",
        r"幻灯片\s*\d+\s*[｜|:：\|]\s*(.+)",
        r"Slide\s*\d+\s*[｜|:：\|]\s*(.+)",
        r"\d+\.\s*(.+)",
    ]
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return text


def parse_ppt_outline(markdown_text: str) -> list[dict[str, Any]]:
    """从 PPT 大纲 markdown 中提取 slides。

    支持格式示例：
        # 课程标题
        ## 第1页｜引言
        - 要点 1
        - 要点 2
        讲解提示：...

        ## 第2页｜核心概念
        - 要点 A
        - 要点 B
    """
    slides: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    title_match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
    deck_title = title_match.group(1).strip() if title_match else "PPT"

    lines = markdown_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        # 二级标题作为新 slide 标题
        slide_title = _extract_slide_title(stripped)
        if slide_title is not None:
            current = {"title": slide_title, "points": [], "notes": []}
            slides.append(current)
            index += 1
            continue

        if current is None:
            # 在第一个 slide 标题前遇到的普通段落，当作封面备注
            index += 1
            continue

        # 列表项作为要点
        list_match = re.match(r"^\s*[-*•]\s+(.+)$", stripped)
        if list_match:
            point = list_match.group(1).strip()
            if point:
                current["points"].append(point)
            index += 1
            continue

        # 编号列表作为要点
        number_match = re.match(r"^\s*\d+[\.、)]\s+(.+)$", stripped)
        if number_match:
            point = number_match.group(1).strip()
            if point:
                current["points"].append(point)
            index += 1
            continue

        # 讲解提示/备注
        note_match = re.match(r"^(?:讲解提示|备注|讲师备注|说明|讲者备注|提示)[:：]\s*(.+)$", stripped)
        if note_match:
            note = note_match.group(1).strip()
            if note:
                current["notes"].append(note)
            index += 1
            continue

        # 普通段落：如果是当前 slide 已经有点，作为备注；否则可能是下一 slide 标题（无 ## 前缀）
        if stripped and not stripped.startswith("#"):
            if current["points"]:
                current["notes"].append(stripped)
            else:
                # 无 markdown 标记的标题行，可能是格式不规范，当作标题
                current["title"] += " " + stripped
        index += 1

    # 清理空 slide（只有默认标题没有内容）
    slides = [
        s for s in slides
        if s["points"] or s["notes"] or s["title"] != "PPT"
    ]

    # 如果完全没有解析到 slides，把整个 markdown 作为一页
    if not slides:
        slides.append({"title": deck_title, "points": ["见原始大纲"], "notes": []})

    return slides


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def generate_docx(title: str, markdown_text: str, output_path: Path) -> Path:
    """将 Markdown 文本导出为 Word 文档。"""
    _ensure_dir(output_path)
    doc = DocxDocument()

    # 标题
    heading = doc.add_heading(_clean_text(title), level=0)
    heading.alignment = 1  # 居中

    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # 标题
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = _clean_text(stripped.lstrip("#").strip())
            doc.add_heading(text, level=min(level, 6))
            continue
        # 列表项
        if stripped.startswith(("-", "*")):
            text = _clean_text(re.sub(r"^[-*\s]+", "", stripped))
            doc.add_paragraph(text, style="List Bullet")
            continue
        if re.match(r"^\d+\.\s", stripped):
            text = _clean_text(re.sub(r"^\d+\.\s+", "", stripped))
            doc.add_paragraph(text, style="List Number")
            continue
        # 普通段落
        doc.add_paragraph(_clean_text(stripped))

    doc.save(output_path)
    return output_path


def _clean_text(text: str) -> str:
    """移除 XML 不友好字符，避免 Office 修复提示。"""
    # 保留 \t\n\r，移除其他控制字符
    return "".join(char for char in text if char == "\t" or char == "\n" or char == "\r" or ord(char) >= 0x20)


def generate_pptx(title: str, slides: list[dict[str, Any]], output_path: Path) -> Path:
    """将 slides 数据导出为 PPT，使用标准布局提高 Office 兼容性。"""
    _ensure_dir(output_path)
    prs = Presentation()
    # 使用默认尺寸（4:3），避免自定义尺寸与布局不一致导致 Office 修复提示

    title_slide_layout = prs.slide_layouts[0]  # 标题幻灯片
    title_content_layout = prs.slide_layouts[1]  # 标题和内容

    # 封面
    cover = prs.slides.add_slide(title_slide_layout)
    cover.shapes.title.text = _clean_text(title)
    subtitle = cover.placeholders[1]
    subtitle.text = "AI 教育智能体生成"

    # 内容页
    for slide in slides:
        sld = prs.slides.add_slide(title_content_layout)
        sld.shapes.title.text = _clean_text(slide.get("title", ""))

        body_shape = sld.placeholders[1]
        tf = body_shape.text_frame
        tf.clear()

        points = slide.get("points") or []
        for idx, point in enumerate(points):
            point = _clean_text(point)
            if idx == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = point
            p.level = 0
            p.font.size = PptxPt(20)

        # 备注：暂时不写入 notes slide，避免部分 Office 版本兼容性修复提示
        # notes = slide.get("notes") or []
        # if notes:
        #     notes_slide = sld.notes_slide
        #     notes_text_frame = notes_slide.notes_text_frame
        #     notes_text_frame.text = _clean_text("\n".join(notes))

    prs.save(output_path)
    return output_path


def export_from_resource(resource: LessonResource, doc_type: str, storage_root: Path) -> GeneratedDocument:
    """根据 LessonResource 生成 docx/pptx 文件并返回数据库记录。"""
    allowed = _ALLOWED_EXPORTS.get(resource.resource_type, set())
    if doc_type not in allowed:
        allowed_str = ", ".join(sorted(allowed)) if allowed else "无"
        raise AppError(
            "INVALID_EXPORT_TYPE",
            f"类型为 {resource.resource_type} 的备课资料不支持导出为 {doc_type}，仅支持：{allowed_str}",
            422,
        )

    content = resource.content_json or {}
    title = content.get("title") or resource.title or "未命名"
    text = content.get("text") or ""

    export_dir = storage_root / "exports" / str(resource.course_id)
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}_{doc_type}."
    output_path = export_dir / f"{filename}{doc_type}"

    if doc_type == "docx":
        generate_docx(title, text, output_path)
    elif doc_type == "pptx":
        slides = parse_ppt_outline(text)
        generate_pptx(title, slides, output_path)
    else:
        raise AppError("INVALID_EXPORT_TYPE", f"不支持的导出类型：{doc_type}", 422)

    return GeneratedDocument(
        course_id=resource.course_id,
        chapter_id=resource.chapter_id,
        creator_id=resource.creator_id,
        source_resource_id=resource.id,
        doc_type=doc_type,
        title=title,
        storage_path=str(output_path.resolve()),
        status=Status.ready,
    )
