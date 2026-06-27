from pathlib import Path

from sqlmodel import Session, SQLModel, select

from pm_agent.config import Settings
from pm_agent.db import build_engine
from pm_agent.llm import LLMClient, LLMRequest
from pm_agent.models import (
    DocumentGenerationRun,
    Project,
    ProjectDocument,
    ProjectDocumentPlan,
    ProjectDocumentVersion,
)
from pm_agent.services import DocumentGenerationService, MarkdownImportService, ProjectService


class StaticLLM(LLMClient):
    def generate(self, request: LLMRequest) -> str:
        return "# Generated\n\n" + request.user_prompt[:80]


def test_plan_document_generation_records_run_and_version(tmp_path: Path) -> None:
    session, settings = build_session(tmp_path)
    project = create_project(session)
    plan_id = first_plan_id(session, project.id)

    document = DocumentGenerationService(session, settings, StaticLLM()).generate_document(plan_id=plan_id)

    versions = session.exec(
        select(ProjectDocumentVersion).where(ProjectDocumentVersion.document_id == document.id)
    ).all()
    runs = session.exec(
        select(DocumentGenerationRun).where(DocumentGenerationRun.document_id == document.id)
    ).all()

    assert document.plan_id == plan_id
    assert document.template_id is None
    assert document.file_path
    assert Path(document.file_path).exists()
    assert len(versions) == 1
    assert len(runs) == 1
    assert runs[0].template_id is None


def test_regenerating_plan_document_appends_version(tmp_path: Path) -> None:
    session, settings = build_session(tmp_path)
    project = create_project(session)
    plan_id = first_plan_id(session, project.id)
    service = DocumentGenerationService(session, settings, StaticLLM())

    first = service.generate_document(plan_id=plan_id)
    second = service.generate_document(plan_id=plan_id)

    documents = session.exec(
        select(ProjectDocument).where(ProjectDocument.project_id == project.id)
    ).all()
    versions = session.exec(
        select(ProjectDocumentVersion).where(ProjectDocumentVersion.document_id == first.id)
    ).all()
    runs = session.exec(
        select(DocumentGenerationRun).where(DocumentGenerationRun.document_id == first.id)
    ).all()

    assert second.id == first.id
    assert len(documents) == 1
    assert len(versions) == 2
    assert len(runs) == 2


def test_plan_references_use_chinese_titles_and_dedupe_context(tmp_path: Path) -> None:
    session, settings = build_session(tmp_path)
    project = ProjectService(session).create_project(
        Project(name="测试项目", background="背景", requirements="需求"),
        task_descriptions=["任务一"],
        selected_document_codes=["req-stakeholder-map", "req-report"],
    )
    source_plan = plan_by_code(session, project.id, "req-stakeholder-map")
    target_plan = plan_by_code(session, project.id, "req-report")
    target_plan.dependency_plan_ids = [source_plan.id]
    target_plan.dependency_codes = [source_plan.code]
    session.add(target_plan)
    session.commit()

    service = DocumentGenerationService(session, settings, StaticLLM())
    source_document = service.generate_document(plan_id=source_plan.id)
    preview = service.preview_document(plan_id=target_plan.id)

    assert preview.source_document_ids == [source_document.id]
    assert preview.context_md.count("引用文档：干系人清单与访谈计划") == 1
    assert "干系人清单与访谈计划" in preview.user_prompt
    assert "req-stakeholder-map" not in preview.user_prompt


def test_plan_context_uses_latest_document_when_old_duplicates_exist(tmp_path: Path) -> None:
    session, settings = build_session(tmp_path)
    project = ProjectService(session).create_project(
        Project(name="测试项目", background="背景", requirements="需求"),
        task_descriptions=["任务一"],
        selected_document_codes=["req-business-process", "req-report"],
    )
    source_plan = plan_by_code(session, project.id, "req-business-process")
    target_plan = plan_by_code(session, project.id, "req-report")
    old_document = ProjectDocument(
        project_id=project.id,
        phase_id=source_plan.phase_id,
        plan_id=source_plan.id,
        title=source_plan.title,
        content_md="旧版本内容",
    )
    latest_document = ProjectDocument(
        project_id=project.id,
        phase_id=source_plan.phase_id,
        plan_id=source_plan.id,
        title=source_plan.title,
        content_md="最新版本内容",
    )
    session.add(old_document)
    session.add(latest_document)
    session.commit()
    session.refresh(latest_document)

    preview = DocumentGenerationService(session, settings, StaticLLM()).preview_document(
        plan_id=target_plan.id
    )

    assert preview.source_document_ids == [latest_document.id]
    assert "最新版本内容" in preview.context_md
    assert "旧版本内容" not in preview.context_md


def test_imported_markdown_document_can_be_explicit_plan_context(tmp_path: Path) -> None:
    session, settings = build_session(tmp_path)
    project = create_project(session)
    plan = plan_by_code(session, project.id, "req-stakeholder-map")

    result = MarkdownImportService(session, settings).import_markdown(
        project_id=project.id,
        filename="legacy.md",
        content_md="# Legacy Reference\n\n## Background\n\nImportant imported fact.",
        phase_id=plan.phase_id,
    )
    assert result.document is not None
    plan.reference_document_ids = [result.document.id]
    session.add(plan)
    session.commit()

    preview = DocumentGenerationService(session, settings, StaticLLM()).preview_document(
        plan_id=plan.id
    )

    assert preview.source_document_ids == [result.document.id]
    assert "Important imported fact." in preview.context_md


def test_imported_markdown_template_is_numbered_and_archived(tmp_path: Path) -> None:
    session, settings = build_session(tmp_path)
    project = create_project(session)
    plan = plan_by_code(session, project.id, "req-stakeholder-map")

    result = MarkdownImportService(session, settings).import_markdown(
        project_id=project.id,
        filename="legacy.md",
        content_md="# Legacy Template\n\n## Scope\n\nBody\n\n### Details\n\nMore",
        phase_id=plan.phase_id,
    )

    assert result.catalog_item is not None
    assert result.catalog_item.sort_order > 100
    assert result.catalog_item.template_file_path
    template_path = Path(result.catalog_item.template_file_path)
    assert template_path.exists()
    archived = template_path.read_text(encoding="utf-8")
    assert "code: imported-" in archived
    assert "# Legacy Template" in archived
    assert "## Scope" in archived
    assert "### Details" in archived
    assert "Body" not in result.catalog_item.outline_md


def build_session(tmp_path: Path) -> tuple[Session, Settings]:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    settings = Settings(
        DATABASE_URL=str(engine.url),
        DOCUMENT_STORAGE_PATH=str(tmp_path / "documents"),
        TEMPLATE_LIBRARY_PATH=str(tmp_path / "template-library"),
    )
    return Session(engine), settings


def create_project(session: Session) -> Project:
    return ProjectService(session).create_project(
        Project(name="测试项目", background="背景", requirements="需求"),
        task_descriptions=["任务一"],
        selected_document_codes=["req-stakeholder-map"],
    )


def first_plan_id(session: Session, project_id: int | None) -> int:
    plan_id = session.exec(
        select(ProjectDocument.plan_id).where(ProjectDocument.project_id == project_id)
    ).first()
    assert plan_id is None

    plan = session.exec(
        select(ProjectDocumentPlan).where(ProjectDocumentPlan.project_id == project_id)
    ).first()
    assert plan is not None
    assert plan.id is not None
    return plan.id


def plan_by_code(session: Session, project_id: int | None, code: str) -> ProjectDocumentPlan:
    plan = session.exec(
        select(ProjectDocumentPlan).where(
            ProjectDocumentPlan.project_id == project_id,
            ProjectDocumentPlan.code == code,
        )
    ).first()
    assert plan is not None
    assert plan.id is not None
    return plan
