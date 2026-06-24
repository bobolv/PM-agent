from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from pm_agent.config import Settings
from pm_agent.lifecycle import DOCUMENT_CATALOG
from pm_agent.models import DocumentCatalogItem, RoleType


@dataclass(frozen=True)
class TemplateFile:
    metadata: dict[str, str]
    body: str
    path: Path


class TemplateLibraryService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    @property
    def root(self) -> Path:
        return Path(self.settings.template_library_path)

    def export_catalog_to_markdown(self, overwrite: bool = False) -> list[str]:
        self.root.mkdir(parents=True, exist_ok=True)
        exported: list[str] = []
        items = self.session.exec(
            select(DocumentCatalogItem).order_by(
                DocumentCatalogItem.is_periodic,
                DocumentCatalogItem.sort_order,
                DocumentCatalogItem.id,
            )
        ).all()
        for item in items:
            path = self._path_for_item(item)
            if path.exists() and not overwrite:
                item.template_file_path = str(path)
                self.session.add(item)
                continue

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._render_template_file(item), encoding="utf-8")
            item.template_file_path = str(path)
            item.updated_at = datetime.utcnow()
            self.session.add(item)
            exported.append(str(path))

        self.session.commit()
        return exported

    def sync_markdown_to_catalog(self) -> int:
        if not self.root.exists():
            return 0

        count = 0
        for path in self.root.rglob("*.md"):
            template = parse_template_file(path)
            code = template.metadata.get("code")
            if not code:
                continue

            item = self.session.exec(
                select(DocumentCatalogItem).where(DocumentCatalogItem.code == code)
            ).first()
            if item is None:
                item = DocumentCatalogItem(
                    code=code,
                    name=template.metadata.get("name", path.stem),
                    outline_md=template.body,
                )

            apply_template_metadata(item, template)
            self.session.add(item)
            count += 1

        self.session.commit()
        return count

    def generate_missing_templates(self, overwrite: bool = False) -> list[str]:
        self._ensure_catalog_seeded()
        return self.export_catalog_to_markdown(overwrite=overwrite)

    def reset_builtin_catalog(self) -> int:
        existing_items = {
            item.code: item for item in self.session.exec(select(DocumentCatalogItem)).all()
        }
        count = 0
        for seed in DOCUMENT_CATALOG:
            item = existing_items.get(seed.code)
            if item is None:
                item = DocumentCatalogItem(code=seed.code)
            item.phase_name = seed.phase_name
            item.name = seed.name
            item.description = seed.description
            item.outline_md = seed.outline_md
            item.default_role_type = seed.role_type
            item.is_periodic = seed.is_periodic
            item.period_type = seed.period_type
            item.default_selected = seed.default_selected
            item.sort_order = seed.sort_order
            item.dependency_codes = seed.dependency_codes
            item.updated_at = datetime.utcnow()
            self.session.add(item)
            count += 1
        self.session.commit()
        return count

    def _ensure_catalog_seeded(self) -> None:
        existing_codes = set(self.session.exec(select(DocumentCatalogItem.code)).all())
        for seed in DOCUMENT_CATALOG:
            if seed.code in existing_codes:
                continue
            self.session.add(
                DocumentCatalogItem(
                    code=seed.code,
                    phase_name=seed.phase_name,
                    name=seed.name,
                    description=seed.description,
                    outline_md=seed.outline_md,
                    default_role_type=seed.role_type,
                    is_periodic=seed.is_periodic,
                    period_type=seed.period_type,
                    default_selected=seed.default_selected,
                    sort_order=seed.sort_order,
                    dependency_codes=seed.dependency_codes,
                )
            )
        self.session.commit()

    def _path_for_item(self, item: DocumentCatalogItem) -> Path:
        folder = item.phase_name or ("周期文档" if item.is_periodic else "未分组")
        filename = f"{item.sort_order:04d}-{item.code}.md"
        return self.root / sanitize_path_part(folder) / filename

    def _render_template_file(self, item: DocumentCatalogItem) -> str:
        metadata = {
            "code": item.code,
            "name": item.name,
            "phase_name": item.phase_name or "",
            "description": item.description,
            "default_role_type": item.default_role_type.value,
            "is_periodic": str(item.is_periodic).lower(),
            "period_type": item.period_type or "",
            "default_selected": str(item.default_selected).lower(),
            "sort_order": str(item.sort_order),
            "dependency_codes": ",".join(item.dependency_codes),
        }
        lines = ["---", *[f"{key}: {value}" for key, value in metadata.items()], "---", ""]
        return "\n".join(lines) + item.outline_md.strip() + "\n"


def parse_template_file(path: Path) -> TemplateFile:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return TemplateFile(metadata={}, body=text.strip(), path=path)

    parts = text.split("---", 2)
    if len(parts) < 3:
        return TemplateFile(metadata={}, body=text.strip(), path=path)

    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return TemplateFile(metadata=metadata, body=parts[2].strip(), path=path)


def apply_template_metadata(item: DocumentCatalogItem, template: TemplateFile) -> None:
    metadata = template.metadata
    item.name = metadata.get("name", item.name)
    item.phase_name = blank_to_none(metadata.get("phase_name", item.phase_name))
    item.description = metadata.get("description", item.description)
    item.outline_md = template.body
    item.default_role_type = RoleType(metadata.get("default_role_type", item.default_role_type.value))
    item.is_periodic = parse_bool(metadata.get("is_periodic"), item.is_periodic)
    item.period_type = blank_to_none(metadata.get("period_type", item.period_type))
    item.default_selected = parse_bool(metadata.get("default_selected"), item.default_selected)
    item.sort_order = int(metadata.get("sort_order", item.sort_order))
    item.dependency_codes = parse_csv(metadata.get("dependency_codes"))
    item.template_file_path = str(template.path)
    item.updated_at = datetime.utcnow()


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def sanitize_path_part(value: str) -> str:
    return "".join("-" if char in '<>:"/\\|?*' else char for char in value).strip() or "未分组"
