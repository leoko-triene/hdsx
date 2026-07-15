"""为知识点图谱截图创建演示数据。运行：从 Code1 执行 python scripts/seed_kg_demo.py。"""
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.models import (  # noqa: E402
    Assignment, Course, CourseManager, CourseMember, GradingResult, KnowledgePoint,
    KnowledgePointGraph, KnowledgePointRelation, MasterySnapshot, ParentStudentLink,
    Question, Status, Submission, User,
)


def main():
    with SessionLocal() as db:
        # 1. 创建演示账号
        accounts = [
            ("admin", "系统管理员", "admin"),
            ("teacher", "演示教师", "teacher"),
            ("student", "演示学生", "student"),
            ("parent", "演示家长", "parent"),
        ]
        users = {}
        for username, name, role in accounts:
            user = db.scalar(select(User).where(User.username == username))
            if not user:
                user = User(
                    username=username,
                    display_name=name,
                    role=role,
                    password_hash=hash_password("Demo123!"),
                )
                db.add(user)
                db.flush()
            users[role] = user

        # 2. 创建课程
        course = db.scalar(select(Course).where(Course.name == "Python 与人工智能基础"))
        if not course:
            course = Course(
                name="Python 与人工智能基础",
                subject="计算机",
                grade_level="本科",
                owner_id=users["teacher"].id,
                status=Status.ready,
                description="用于演示知识点图谱、作业关联与掌握度分析。",
            )
            db.add(course)
            db.flush()

        # 3. 教师加入课程管理员，学生加入课程
        manager = db.scalar(
            select(CourseManager).where(
                CourseManager.course_id == course.id,
                CourseManager.user_id == users["teacher"].id,
            )
        )
        if not manager:
            db.add(CourseManager(
                course_id=course.id,
                user_id=users["teacher"].id,
                added_by=users["teacher"].id,
            ))

        member = db.scalar(
            select(CourseMember).where(
                CourseMember.course_id == course.id,
                CourseMember.student_id == users["student"].id,
            )
        )
        if not member:
            db.add(CourseMember(
                course_id=course.id,
                student_id=users["student"].id,
                source="approved",
                status="active",
            ))

        # 4. 家长绑定学生
        link = db.scalar(
            select(ParentStudentLink).where(
                ParentStudentLink.parent_id == users["parent"].id,
                ParentStudentLink.student_id == users["student"].id,
            )
        )
        if not link:
            db.add(ParentStudentLink(
                parent_id=users["parent"].id,
                student_id=users["student"].id,
                status="active",
            ))

        # 5. 知识点定义
        knowledge_points_data = [
            {"code": "PY-01", "name": "Python 基础语法", "description": "变量、数据类型、运算符等入门概念", "level": 1},
            {"code": "PY-02", "name": "函数与模块", "description": "函数定义、参数传递、模块导入机制", "level": 2},
            {"code": "PY-03", "name": "面向对象编程", "description": "类、对象、继承、多态等核心思想", "level": 2},
            {"code": "AI-01", "name": "机器学习基础", "description": "监督学习、特征工程、模型评估方法", "level": 2},
            {"code": "AI-02", "name": "神经网络", "description": "感知机、反向传播、激活函数", "level": 3},
            {"code": "AI-03", "name": "Transformer 架构", "description": "自注意力机制、位置编码、Encoder-Decoder", "level": 3},
        ]

        code_to_id = {}
        for item in knowledge_points_data:
            kp = db.scalar(
                select(KnowledgePoint).where(
                    KnowledgePoint.course_id == course.id,
                    KnowledgePoint.code == item["code"],
                )
            )
            if not kp:
                kp = KnowledgePoint(
                    course_id=course.id,
                    code=item["code"],
                    name=item["name"],
                    description=item["description"],
                )
                db.add(kp)
                db.flush()
            code_to_id[item["code"]] = kp.id

        # 6. 知识点关系
        relations_data = [
            {"from_code": "PY-01", "to_code": "PY-02", "type": "prerequisite", "confidence": 0.9},
            {"from_code": "PY-02", "to_code": "PY-03", "type": "prerequisite", "confidence": 0.85},
            {"from_code": "PY-02", "to_code": "AI-01", "type": "related", "confidence": 0.7},
            {"from_code": "AI-01", "to_code": "AI-02", "type": "prerequisite", "confidence": 0.9},
            {"from_code": "AI-02", "to_code": "AI-03", "type": "prerequisite", "confidence": 0.85},
        ]

        db.execute(
            select(KnowledgePointRelation).where(
                KnowledgePointRelation.course_id == course.id
            )
        )
        existing_rels = set()
        for rel in db.scalars(
            select(KnowledgePointRelation).where(
                KnowledgePointRelation.course_id == course.id
            )
        ).all():
            existing_rels.add((rel.from_kp_id, rel.to_kp_id, rel.relation_type))

        for rel in relations_data:
            from_id = code_to_id[rel["from_code"]]
            to_id = code_to_id[rel["to_code"]]
            if (from_id, to_id, rel["type"]) not in existing_rels:
                db.add(KnowledgePointRelation(
                    course_id=course.id,
                    from_kp_id=from_id,
                    to_kp_id=to_id,
                    relation_type=rel["type"],
                    confidence=rel["confidence"],
                    source="ai",
                    document_ids_json=[],
                ))

        # 7. 知识图谱版本
        graph = db.scalar(
            select(KnowledgePointGraph).where(
                KnowledgePointGraph.course_id == course.id
            ).order_by(KnowledgePointGraph.version.desc())
        )
        if not graph:
            nodes = [
                {
                    "id": code_to_id[item["code"]],
                    "code": item["code"],
                    "name": item["name"],
                    "description": item["description"],
                    "level": item["level"],
                }
                for item in knowledge_points_data
            ]
            edges = [
                {
                    "from": code_to_id[rel["from_code"]],
                    "to": code_to_id[rel["to_code"]],
                    "type": rel["type"],
                    "confidence": rel["confidence"],
                }
                for rel in relations_data
            ]
            graph = KnowledgePointGraph(
                course_id=course.id,
                version=1,
                status="approved",
                nodes_json=nodes,
                edges_json=edges,
                generated_by=users["teacher"].id,
                reviewed_by=users["teacher"].id,
                reviewed_at=datetime.utcnow(),
            )
            db.add(graph)
            db.flush()

        # 8. 发布作业与题目
        assignment = db.scalar(
            select(Assignment).where(Assignment.title == "Python 与 AI 综合练习")
        )
        if not assignment:
            assignment = Assignment(
                course_id=course.id,
                creator_id=users["teacher"].id,
                title="Python 与 AI 综合练习",
                description="用于演示知识点掌握度分析",
                due_at=datetime.utcnow(),
                total_score=Decimal("100.00"),
                status=Status.published,
            )
            db.add(assignment)
            db.flush()

        questions_data = [
            {
                "stem": "Python 中定义函数的关键字是什么？",
                "type": "single_choice",
                "answer": "def",
                "max_score": Decimal("10.00"),
                "kp_ids": [code_to_id["PY-01"]],
            },
            {
                "stem": "面向对象编程的三大特性是什么？",
                "type": "short_answer",
                "answer": "封装、继承、多态",
                "max_score": Decimal("20.00"),
                "kp_ids": [code_to_id["PY-03"]],
            },
            {
                "stem": "机器学习中用于评估分类模型性能的常见指标有哪些？",
                "type": "short_answer",
                "answer": "准确率、精确率、召回率、F1 分数",
                "max_score": Decimal("20.00"),
                "kp_ids": [code_to_id["AI-01"]],
            },
            {
                "stem": "神经网络中常用的激活函数有哪些？",
                "type": "short_answer",
                "answer": "ReLU、Sigmoid、Tanh",
                "max_score": Decimal("25.00"),
                "kp_ids": [code_to_id["AI-02"]],
            },
            {
                "stem": "Transformer 中的自注意力机制主要解决什么问题？",
                "type": "short_answer",
                "answer": "捕捉序列中任意位置之间的依赖关系",
                "max_score": Decimal("25.00"),
                "kp_ids": [code_to_id["AI-03"]],
            },
        ]

        question_objects = []
        for idx, q in enumerate(questions_data):
            existing = db.scalar(
                select(Question).where(
                    Question.assignment_id == assignment.id,
                    Question.stem == q["stem"],
                )
            )
            if existing:
                question_objects.append(existing)
                continue
            question = Question(
                assignment_id=assignment.id,
                question_type=q["type"],
                stem=q["stem"],
                standard_answer=q["answer"],
                options_json=[],
                rubric_json=[],
                knowledge_point_ids_json=q["kp_ids"],
                max_score=q["max_score"],
                sort_order=idx,
            )
            db.add(question)
            db.flush()
            question_objects.append(question)

        # 9. 学生提交与批改结果
        submission = db.scalar(
            select(Submission).where(
                Submission.assignment_id == assignment.id,
                Submission.student_id == users["student"].id,
            )
        )
        if not submission:
            answers = [
                {"question_id": q.id, "answer": q.standard_answer if i in (0, 1, 3) else ""}
                for i, q in enumerate(question_objects)
            ]
            submission = Submission(
                assignment_id=assignment.id,
                student_id=users["student"].id,
                attempt_no=1,
                answers_json=answers,
                total_score=Decimal("80.00"),
                status=Status.approved,
            )
            db.add(submission)
            db.flush()

        # 批改结果
        scores = [10.0, 20.0, 15.0, 25.0, 10.0]  # 第 3、5 题部分错误
        for question, score in zip(question_objects, scores):
            gr = db.scalar(
                select(GradingResult).where(
                    GradingResult.submission_id == submission.id,
                    GradingResult.question_id == question.id,
                )
            )
            if not gr:
                db.add(GradingResult(
                    submission_id=submission.id,
                    question_id=question.id,
                    ai_score=Decimal(str(score)),
                    final_score=Decimal(str(score)),
                    confidence=0.9,
                    feedback="",
                    evidence_json=[],
                    status=Status.approved,
                    reviewer_id=users["teacher"].id,
                ))

        # 10. 掌握度快照
        mastery_data = [
            ("PY-01", 1.0, "mastered"),
            ("PY-02", 1.0, "mastered"),
            ("PY-03", 1.0, "mastered"),
            ("AI-01", 0.75, "proficient"),
            ("AI-02", 1.0, "mastered"),
            ("AI-03", 0.4, "weak"),
        ]

        for code, score, level in mastery_data:
            kp_id = code_to_id[code]
            existing = db.scalar(
                select(MasterySnapshot).where(
                    MasterySnapshot.student_id == users["student"].id,
                    MasterySnapshot.knowledge_point_id == kp_id,
                )
            )
            if not existing:
                db.add(MasterySnapshot(
                    student_id=users["student"].id,
                    knowledge_point_id=kp_id,
                    score=score,
                    level=level,
                    evidence_count=1,
                    algorithm_version="v1",
                ))

        db.commit()
        print("知识点图谱演示数据已创建。")
        print(f"课程：Python 与人工智能基础（id={course.id}）")
        print("账号：teacher / student / parent / admin，密码均为 Demo123!")
        print(f"知识图谱版本：{graph.version}，知识点数：{len(knowledge_points_data)}")


if __name__ == "__main__":
    main()
