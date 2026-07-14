from pathlib import Path

import pytest

from app.services.document_export import generate_docx, generate_pptx, parse_ppt_outline


class TestParsePptOutline:
    def test_parse_simple_outline(self):
        text = """# 机器学习入门

## 第1页：课程介绍
- 什么是机器学习
- 典型应用场景
讲解提示：用图片引发兴趣

## 第2页：监督学习
- 定义与特点
- 常见算法
"""
        slides = parse_ppt_outline(text)
        assert len(slides) == 2
        assert slides[0]["title"] == "课程介绍"
        assert slides[0]["points"] == ["什么是机器学习", "典型应用场景"]
        assert "用图片引发兴趣" in slides[0]["notes"]
        assert slides[1]["title"] == "监督学习"

    def test_parse_fallback(self):
        slides = parse_ppt_outline("一些没有结构的文本")
        assert len(slides) == 1
        assert slides[0]["title"] == "PPT"


class TestGenerateDocx:
    def test_generates_file(self, tmp_path: Path):
        output = tmp_path / "test.docx"
        result = generate_docx("测试教案", "# 目标\n- 掌握基础\n普通段落。", output)
        assert result.exists()
        assert result.stat().st_size > 0


class TestGeneratePptx:
    def test_generates_file(self, tmp_path: Path):
        output = tmp_path / "test.pptx"
        slides = [
            {"title": "封面", "points": ["主题 A", "主题 B"], "notes": ["备注"]}
        ]
        result = generate_pptx("测试 PPT", slides, output)
        assert result.exists()
        assert result.stat().st_size > 0
