import json
import re
import sys
from collections import Counter

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.answer import StandardAnswerAgent
from app.agents.assignment import AssignmentAgent
from app.agents.grading import GradingAgent
from app.agents.lesson import LessonAgent
from app.agents.report import ReportAgent
from app.agents.runtime import AgentRuntime
from app.agents.structured import (
    AssignmentMaterial, AssignmentMaterialsOutput, GradingOutput, ParentReportOutput,
    extract_json, validate_or_fallback,
)
from app.core.exceptions import AppError
from app.integrations.ollama import OllamaClient
from app.rag.service import KnowledgeService


def _load_model_json(raw: str):
    return extract_json(raw)


def _coerce_markdown_text(raw) -> str:
    """兼容模型误返 JSON：提取正文并转成可读 Markdown，绝不把 JSON 对象直接交给页面。"""
    if isinstance(raw, dict):
        for key in ("text", "content", "body", "lesson_plan", "lecture", "markdown"):
            if raw.get(key):
                return _coerce_markdown_text(raw[key])
        return "\n\n".join(f"## {key}\n\n{_coerce_markdown_text(item)}" for key, item in raw.items())
    if isinstance(raw, list):
        return "\n".join(f"- {_coerce_markdown_text(item)}" for item in raw)
    text = str(raw or "").strip().strip("`").strip()
    if not text:
        return ""
    if not text.startswith(("{", "[")):
        return text
    try:
        value = extract_json(text)
    except (ValueError, json.JSONDecodeError):
        return text
    return _coerce_markdown_text(value)


async def generate_lesson(db: Session, request) -> tuple[dict, list]:
    knowledge = KnowledgeService(db)
    chunks = knowledge.keyword_search(request.course_id, request.chapter_title, 8)
    if not chunks:
        candidates = await knowledge.hybrid_search(request.course_id, request.chapter_title, 8)
        chunks = [chunk for chunk in candidates if chunk.rerank_score is not None and chunk.rerank_score > 0]
    context = "\n\n".join(f"[资料{i+1}] {chunk.content}" for i, chunk in enumerate(chunks))
    if not context:
        raise AppError("INSUFFICIENT_EVIDENCE", "当前课程知识库没有找到与该主题相关的资料，请检查课程、主题名称或上传对应教材", 422)
    rules = {
        "lesson_plan": "使用完整教案格式，依次包含课程信息、教学目标、重点与难点、课前准备、教学过程、互动、示例、练习、总结和课后任务。",
        "lecture": "使用可直接讲授的课堂讲稿格式，包含开场、知识讲解、案例、互动、易错提醒和总结。",
        "ppt_outline": "使用 PPT 逐页提纲，每页写明页码、标题、3～6 个要点、建议图示和讲解提示。",
        "exercise": "按例题、练习题、思考题分组，每题包含题干、参考答案和简要解析。",
    }
    result = await LessonAgent().run({
        "resource_type": request.resource_type, "audience": request.audience,
        "duration_minutes": request.duration_minutes, "chapter_title": request.chapter_title,
        "requirements": request.requirements or "无",
        "format_rules": rules.get(request.resource_type, rules["lesson_plan"]), "context": context,
    }, tools_used=["search_course_knowledge"])
    text = _coerce_markdown_text(result.content)
    if not text:
        raise AppError("MODEL_OUTPUT_INVALID", "模型未返回备课文本", 502)
    type_name = {"lesson_plan": "完整教案", "lecture": "课堂讲稿", "ppt_outline": "PPT 提纲", "exercise": "课堂练习"}.get(request.resource_type, "备课资料")
    content = {"title": request.chapter_title, "text": text, "format": "markdown", "resource_type": request.resource_type, "type_name": type_name}
    citations = [{"chunk_id": chunk.chunk_id, "filename": chunk.filename, "source_url": chunk.source_url} for chunk in chunks]
    return content, citations


async def grade_subjective(question, answer: str, knowledge_context: str = "") -> dict:
    payload = {"standard_answer": question.standard_answer, "explanation": getattr(question, 'explanation', None) or "",
               "rubric": question.rubric_json or [], "max_score": float(question.max_score),
               "student_answer": answer, "course_knowledge": knowledge_context}
    result = await GradingAgent().run(
        {"payload": json.dumps(payload, ensure_ascii=False)},
        output_schema=GradingOutput.model_json_schema(),
        tools_used=["get_course_context"] if knowledge_context else [],
    )
    max_score = float(question.max_score)

    def fallback() -> GradingOutput:
        reference = str(question.standard_answer or knowledge_context).strip()
        expected = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", reference.lower()))
        actual = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", answer.lower()))
        ratio = len(expected & actual) / max(1, min(len(expected), 12))
        score = round(max_score * min(1.0, ratio), 2) if answer.strip() else 0
        return GradingOutput(score=score, confidence=.35,
            feedback="AI 暂未能完整批改你的作答，以下是根据参考答案关键词匹配的保守评分，最终成绩以教师复核为准。",
            evidence=[{"point": "参考答案关键词匹配", "source": "标准答案与课程知识库"}])

    data = validate_or_fallback(str(result.content), GradingOutput, fallback).model_dump()
    data["score"] = max(0, min(max_score, data["score"]))
    return data


def _normalize_assignment_materials(data) -> dict:
    items = data if isinstance(data, list) else data.get("items") or data.get("questions") or data.get("materials") or []
    if isinstance(items, dict):
        items = list(items.values())
    type_map = {"单选题": "single_choice", "多选题": "multiple_choice", "判断题": "true_false",
                "简答题": "short_answer", "论述题": "essay",
                "single_choice": "single_choice", "multiple_choice": "multiple_choice",
                "true_false": "true_false", "short_answer": "short_answer", "essay": "essay",
                "true_or_false": "true_false", "choice": "single_choice",
                "单选": "single_choice", "多选": "multiple_choice",
                "判断": "true_false", "简答": "short_answer", "论述": "essay"}
    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_type = (item.get("question_type") or item.get("type") or "short_answer")
        question_type = type_map.get(raw_type, raw_type)
        options = item.get("options") or item.get("选项")
        if isinstance(options, dict):
            options = [{"key": str(key), "content": str(value)} for key, value in options.items()]
        elif isinstance(options, list):
            options = [value if isinstance(value, dict) else {"key": chr(65 + index), "content": str(value)} for index, value in enumerate(options)]
        elif isinstance(options, str):
            parts = re.split(r'[|；;]\s*', options)
            if len(parts) >= 2:
                options = [{"key": chr(65 + i), "content": p.strip()} for i, p in enumerate(parts)]
            else:
                options = None
        # 过滤空选项、去重ABCD前缀、排版修正
        if isinstance(options, list):
            cleaned = []
            for o in options:
                if not isinstance(o, dict):
                    continue
                raw = o.get("content")
                if raw is None or not str(raw).strip():
                    continue
                content = str(raw).strip()
                # 去掉模型可能自带的字母前缀，如 "A. xxx" → "xxx"
                content = re.sub(r'^[A-H][.、)）]\s*', '', content)
                cleaned.append(content)
            if cleaned:
                options = [{"key": chr(65 + i), "content": c} for i, c in enumerate(cleaned)]
            else:
                options = None
        if question_type == "true_false":
            options = [{"key": "true", "content": "正确"}, {"key": "false", "content": "错误"}]
        answer = item.get("standard_answer") or item.get("answer") or item.get("参考答案") or ""
        if isinstance(answer, list):
            answer = ",".join(map(str, answer))
        if question_type == "true_false":
            answer = "true" if str(answer).lower().strip() in {"true", "正确", "对", "是", "1"} else "false"
        explanation = item.get("explanation") or item.get("解析") or item.get("answer_explanation") or ""
        stem = str(item.get("stem") or item.get("question") or item.get("题干") or "").strip()
        if question_type == "single_choice" and "（单选）" not in stem and "(单选)" not in stem:
            stem += "（单选）"
        elif question_type == "multiple_choice" and "（多选）" not in stem and "(多选)" not in stem:
            stem += "（多选）"
        output.append({
            "material_type": item.get("material_type", "exercise"),
            "question_type": question_type,
            "stem": stem,
            "standard_answer": str(answer).strip(),
            "explanation": str(explanation).strip(),
            "options": options,
            "max_score": max(1, min(20, float(item.get("max_score") or item.get("score") or 5))),
        })
    return {"items": output}


async def generate_assignment_materials(db: Session, course_id: int, document_ids: list[int], documents: list, request) -> list[dict]:
    filenames = "、".join(document.filename for document in documents)
    doc_id_set = set(document_ids)

    # RAG 检索：用老师主题做混合检索，召回 TOP-8 最相关片段
    rag_chunks = []
    no_material_warning = ""
    try:
        rag_chunks = await KnowledgeService(db).hybrid_search(course_id, request.chapter_or_topic, 8)
        rag_chunks = [c for c in rag_chunks if int(c.document_id) in doc_id_set]
    except Exception:
        rag_chunks = []

    # 如果 RAG 结果不够，用 keyword 搜索补充
    if len(rag_chunks) < 3:
        try:
            kw_chunks = KnowledgeService(db).keyword_search(course_id, request.chapter_or_topic, 8)
            existing_ids = {c.chunk_id for c in rag_chunks}
            for c in kw_chunks:
                if int(c.document_id) in doc_id_set and c.chunk_id not in existing_ids:
                    rag_chunks.append(c)
        except Exception:
            pass

    # 构建 prompt 上下文
    if rag_chunks:
        context = "\n\n".join(f"[来源：{c.filename}]\n{c.content}" for c in rag_chunks[:8])
    else:
        context = ""
        no_material_warning = "注意：未找到相关参考资料，以下题目完全由 AI 大模型生成，未基于课程知识库，请教师审核后使用。"

    # 通过 v2 prompt 出题
    type_desc = []
    if request.single_choice_count: type_desc.append(f"单选题{request.single_choice_count}道")
    if request.multiple_choice_count: type_desc.append(f"多选题{request.multiple_choice_count}道")
    if request.true_false_count: type_desc.append(f"判断题{request.true_false_count}道")
    if request.short_answer_count: type_desc.append(f"简答题{request.short_answer_count}道")
    if request.essay_count: type_desc.append(f"论述题{request.essay_count}道")

    total_requested = sum([request.single_choice_count, request.multiple_choice_count,
                          request.true_false_count, request.short_answer_count, request.essay_count])
    schema_hint = json.dumps({"items": [{"question_type": "single_choice", "stem": "题干", "standard_answer": "A", "options": [{"key": "A", "content": "选项A"}, {"key": "B", "content": "选项B"}, {"key": "C", "content": "选项C"}, {"key": "D", "content": "选项D"}], "max_score": 5, "explanation": "解析"}]}, ensure_ascii=False)

    # 第一轮：全量出题
    complete: list[dict] = []
    client = OllamaClient()
    type_labels = {"single_choice": "单选题", "multiple_choice": "多选题", "true_false": "判断题",
                   "short_answer": "简答题", "essay": "论述题"}
    type_counts = {"single_choice": request.single_choice_count, "multiple_choice": request.multiple_choice_count,
                   "true_false": request.true_false_count, "short_answer": request.short_answer_count, "essay": request.essay_count}

    def parse_items(raw_text) -> list[dict]:
        try:
            raw = extract_json(raw_text)
        except Exception:
            return []
        items = raw if isinstance(raw, list) else raw.get("items") or raw.get("questions") or []
        if isinstance(raw, dict) and "question_type" in raw:
            items = [raw]
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                norm = _normalize_assignment_materials({"items": [item]})
                m = AssignmentMaterial.model_validate(norm["items"][0])
                # 选择题必须带选项，且答案必须在选项中
                if m.question_type in ("single_choice", "multiple_choice"):
                    if not m.options or len(m.options) < 2:
                        continue
                    keys = {str(o.get("key", "")) for o in m.options}
                    ans_parts = {p for p in re.split(r"[,，\s]+", m.standard_answer) if p}
                    if not ans_parts or not ans_parts.issubset(keys):
                        continue
                result.append(m.model_dump())
            except (ValidationError, TypeError, IndexError, ValueError):
                continue
        return result

    # 第一轮：全量出题
    result = await AssignmentAgent(AgentRuntime(client)).run({
        "topic": request.chapter_or_topic,
        "counts": "，".join(type_desc),
        "schema": schema_hint,
        "filenames": filenames,
        "context": context or "(无参考资料)",
    }, tools_used=["get_document_context"])
    complete = parse_items(str(result.content))

    # 多轮补齐：反复检查缺失题型，接受任何有效题目，直到全部满足或连续两轮无进展
    for _ in range(6):
        existing = Counter(item["question_type"] for item in complete)
        missing_types = {qt: needed - existing.get(qt, 0) for qt, needed in type_counts.items() if needed - existing.get(qt, 0) > 0}
        if not missing_types:
            break
        before = len(complete)
        for qt, _ in missing_types.items():
            label = type_labels[qt]
            has_opts = qt in ("single_choice", "multiple_choice", "true_false")
            try:
                resp = str(await client.chat("你是出题助手。",
                    f"为主题「{request.chapter_or_topic}」生成1道{label}。输出JSON数组，每项含question_type,stem,standard_answer,options(选择题),explanation。",
                    json_mode=True))
                for item in parse_items(resp):
                    if item["question_type"] in type_counts:
                        complete.append(item)
                        break
            except Exception:
                continue
        if len(complete) == before:
            break

    if not complete:
        raise AppError("MATERIAL_GENERATION_FAILED",
            "AI 出题失败，请重试或手动添加题目。", 502)

    # 按题型排列：单选 → 多选 → 判断 → 简答 → 论述
    order = {"single_choice": 0, "multiple_choice": 1, "true_false": 2, "short_answer": 3, "essay": 4}
    complete.sort(key=lambda x: order.get(x.get("question_type", ""), 99))

    return complete, no_material_warning


async def generate_standard_answer(db: Session, course_id: int, question_type: str, stem: str, options: list | None) -> str:
    context = "\n\n".join(chunk.content for chunk in KnowledgeService(db).course_context(course_id, 6))
    result = await StandardAnswerAgent().run({"question_type": question_type, "stem": stem,
        "options": json.dumps(options or [], ensure_ascii=False), "context": context},
        tools_used=["get_course_context"])
    answer = str(result.content).strip().strip("`").strip()
    if answer:
        return answer
    if question_type == "true_false":
        return "true"
    if question_type == "single_choice" and options:
        return str(options[0].get("key", "A"))
    if question_type == "multiple_choice" and options:
        return ",".join(str(item.get("key")) for item in options[:2] if item.get("key"))
    evidence = re.sub(r"\s+", " ", context).strip()[:500]
    return f"参考答案应结合题意说明以下课程要点：{evidence or stem}"


async def generate_parent_report(metrics: dict) -> dict:
    result = await ReportAgent().run({"metrics": json.dumps(metrics, ensure_ascii=False)},
        output_schema=ParentReportOutput.model_json_schema(), tools_used=["get_student_mastery_summary"])

    def normalize(value):
        for field in ("highlights", "needs_attention", "action_plan"):
            item = value.get(field, [])
            value[field] = [part.strip() for part in re.split(r"[\n；;]+", item) if part.strip()] if isinstance(item, str) else (item if isinstance(item, list) else [])
        for field in ("overview", "encouragement", "metrics_explanation"):
            item = value.get(field, "")
            value[field] = "；".join(map(str, item)) if isinstance(item, list) else str(item or "")
        return value

    def fallback() -> ParentReportOutput:
        average, weak_count = float(metrics.get("average_mastery") or 0), len(metrics.get("weak_points") or [])
        return ParentReportOutput(overview=f"本阶段平均掌握度为 {average:.0%}，共有 {weak_count} 个知识点需要继续巩固。",
            highlights=["已完成本阶段学习与练习记录"], needs_attention=[f"优先复习 {weak_count} 个薄弱知识点"] if weak_count else ["继续保持当前学习节奏"],
            action_plan=["每天安排固定复习时间", "结合错题进行一次针对性练习"], encouragement="稳步积累比一次高分更重要，请继续保持。",
            metrics_explanation="掌握度综合参考作业表现和知识点学习记录。")

    return validate_or_fallback(str(result.content), ParentReportOutput, fallback, normalize).model_dump()
