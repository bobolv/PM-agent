from pathlib import Path

from sqlmodel import Session, SQLModel, select

from pm_agent.config import Settings
from pm_agent.db import build_engine
from pm_agent.models import DocumentCatalogItem, RoleType
from pm_agent.template_library import (
    TemplateLibraryService,
    apply_template_metadata,
    parse_template_file,
)


def test_parse_template_file_with_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "template.md"
    path.write_text(
        "---\n"
        "code: req-report\n"
        "name: 需求调研报告\n"
        "phase_name: 需求调研\n"
        "default_role_type: researcher\n"
        "dependency_codes: req-plan, req-minutes\n"
        "---\n\n"
        "# 需求调研报告\n\n## 背景\n",
        encoding="utf-8",
    )

    template = parse_template_file(path)

    assert template.metadata["code"] == "req-report"
    assert template.body.startswith("# 需求调研报告")


def test_apply_template_metadata_updates_catalog_item(tmp_path: Path) -> None:
    path = tmp_path / "template.md"
    path.write_text(
        "---\n"
        "code: req-report\n"
        "name: 需求调研报告\n"
        "phase_name: 需求调研\n"
        "default_role_type: researcher\n"
        "is_periodic: false\n"
        "default_selected: true\n"
        "sort_order: 100\n"
        "dependency_codes: req-plan,req-minutes\n"
        "---\n\n"
        "# 需求调研报告\n",
        encoding="utf-8",
    )
    item = DocumentCatalogItem(code="req-report", name="旧名称", outline_md="")

    apply_template_metadata(item, parse_template_file(path))

    assert item.name == "需求调研报告"
    assert item.default_role_type == RoleType.researcher
    assert item.dependency_codes == ["req-plan", "req-minutes"]


def test_export_template_writes_obsidian_wikilinks_for_dependencies(tmp_path: Path) -> None:
    session, settings = build_template_session(tmp_path)
    source = DocumentCatalogItem(code="source", name="Source Doc", outline_md="# Source\n", sort_order=1)
    target = DocumentCatalogItem(
        code="target",
        name="Target Doc",
        outline_md="# Target\n",
        sort_order=2,
        dependency_codes=["source"],
    )
    session.add(source)
    session.add(target)
    session.commit()

    TemplateLibraryService(session, settings).export_catalog_to_markdown(overwrite=True)
    session.refresh(source)
    session.refresh(target)

    target_text = Path(target.template_file_path).read_text(encoding="utf-8")
    source_text = Path(source.template_file_path).read_text(encoding="utf-8")
    assert "## 关联文件" in target_text
    assert "- [[0001-Source Doc]]" in target_text
    assert "forward_links" not in target_text
    assert "back_links" not in source_text


def test_sync_template_wikilinks_update_dependency(tmp_path: Path) -> None:
    session, settings = build_template_session(tmp_path)
    source = DocumentCatalogItem(code="source", name="Source Doc", outline_md="# Source\n", sort_order=1)
    target = DocumentCatalogItem(code="target", name="Target Doc", outline_md="# Target\n", sort_order=2)
    session.add(source)
    session.add(target)
    session.commit()
    service = TemplateLibraryService(session, settings)
    service.export_catalog_to_markdown(overwrite=True)
    session.refresh(target)
    target_path = Path(target.template_file_path)
    target_path.write_text(
        "---\n"
        "code: target\n"
        "name: Target Doc\n"
        "sort_order: 2\n"
        "---\n\n"
        "# Target\n\n"
        "See [[0001-Source Doc]] before drafting.\n",
        encoding="utf-8",
    )

    service.sync_markdown_to_catalog()
    refreshed = session.exec(
        select(DocumentCatalogItem).where(DocumentCatalogItem.code == "target")
    ).one()

    assert refreshed.dependency_codes == ["source"]
    assert refreshed.outline_md.strip() == "# Target\n\nSee [[0001-Source Doc]] before drafting."


def build_template_session(tmp_path: Path) -> tuple[Session, Settings]:
    engine = build_engine(f"sqlite:///{tmp_path / 'templates.db'}")
    SQLModel.metadata.create_all(engine)
    settings = Settings(
        DATABASE_URL=str(engine.url),
        TEMPLATE_LIBRARY_PATH=str(tmp_path / "template-library"),
    )
    return Session(engine), settings
