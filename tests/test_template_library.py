from pathlib import Path

from pm_agent.models import DocumentCatalogItem, RoleType
from pm_agent.template_library import apply_template_metadata, parse_template_file


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
