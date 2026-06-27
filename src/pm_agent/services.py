import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, col, select

from pm_agent.config import Settings
from pm_agent.lifecycle import DEFAULT_PHASES, DEFAULT_ROLES, DOCUMENT_CATALOG
from pm_agent.llm import LLMClient, LLMRequest
from pm_agent.models import (
    DocumentCatalogItem,
    DocumentGenerationRun,
    DocumentPlanStatus,
    DocumentRoleAssignment,
    DocumentStatus,
    DocumentTemplate,
    LifecyclePhase,
    Project,
    ProjectDocument,
    ProjectDocumentPlan,
    ProjectDocumentVersion,
    ProjectRole,
    ProjectTask,
    ReportingWindow,
    RoleType,
    TaskArtifact,
    WorkRecord,
)
from pm_agent.template_library import TemplateLibraryService, sanitize_path_part


@dataclass(frozen=True)
class GenerationPreview:
    project_id: int
    plan_id: int | None
    template_id: int | None
    role_id: int | None
    role_name: str
    system_prompt: str
    user_prompt: str
    context_md: str
    source_document_ids: list[int]
    source_artifact_ids: list[int]
    source_work_record_ids: list[int]


@dataclass(frozen=True)
class MarkdownImportResult:
    document: ProjectDocument | None
    catalog_item: DocumentCatalogItem | None


def extract_markdown_outline(content_md: str, fallback_title: str) -> str:
    headings: list[tuple[int, str]] = []
    for line in content_md.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
        if not match:
            continue
        text = match.group(2).strip().strip("#").strip()
        if text:
            headings.append((len(match.group(1)), text))

    if not headings:
        return f"# {fallback_title}\n\n## 内容要点\n"

    normalized: list[str] = []
    has_h1 = any(level == 1 for level, _ in headings)
    if not has_h1:
        normalized.append(f"# {fallback_title}")
    for level, text in headings:
        normalized.append(f"{'#' * min(level, 6)} {text}")
    return "\n\n".join(normalized).strip() + "\n"


def ascii_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-+", "-", slug)


class CatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def seed_document_catalog(self) -> None:
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

    def list_catalog(self) -> list[DocumentCatalogItem]:
        self.seed_document_catalog()
        return list(
            self.session.exec(
                select(DocumentCatalogItem).order_by(
                    DocumentCatalogItem.is_periodic,
                    DocumentCatalogItem.sort_order,
                    DocumentCatalogItem.id,
                )
            ).all()
        )


class ProjectService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_project(
        self,
        project: Project,
        task_descriptions: list[str],
        selected_document_codes: list[str] | None = None,
    ) -> Project:
        CatalogService(self.session).seed_document_catalog()
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)

        role_by_type = self._seed_roles(project.id)
        phase_by_name = self._seed_lifecycle(project.id)
        self._seed_document_plans(project.id, phase_by_name, role_by_type, selected_document_codes)
        self._seed_tasks(project.id, task_descriptions)

        self.session.commit()
        self.session.refresh(project)
        return project

    def _seed_roles(self, project_id: int | None) -> dict[RoleType, ProjectRole]:
        if project_id is None:
            return {}

        role_by_type = {}
        for role_type, name, responsibility, agent_prompt in DEFAULT_ROLES:
            role = ProjectRole(
                project_id=project_id,
                role_type=role_type,
                name=name,
                responsibility=responsibility,
                agent_prompt=agent_prompt,
            )
            self.session.add(role)
            self.session.flush()
            role_by_type[role_type] = role
        return role_by_type

    def _seed_lifecycle(self, project_id: int | None) -> dict[str, LifecyclePhase]:
        if project_id is None:
            return {}

        phase_by_name: dict[str, LifecyclePhase] = {}
        for index, phase_seed in enumerate(DEFAULT_PHASES, start=1):
            phase = LifecyclePhase(
                project_id=project_id,
                name=phase_seed.name,
                description=phase_seed.description,
                order_index=index,
            )
            self.session.add(phase)
            self.session.flush()
            phase_by_name[phase.name] = phase
        return phase_by_name

    def _seed_document_plans(
        self,
        project_id: int | None,
        phase_by_name: dict[str, LifecyclePhase],
        role_by_type: dict[RoleType, ProjectRole],
        selected_document_codes: list[str] | None,
    ) -> None:
        if project_id is None:
            return

        selected_codes = set(selected_document_codes or [])
        catalog_items = self.session.exec(
            select(DocumentCatalogItem).order_by(DocumentCatalogItem.sort_order)
        ).all()
        created_plans: list[ProjectDocumentPlan] = []
        for item in catalog_items:
            enabled = item.default_selected if not selected_codes else item.code in selected_codes
            if not enabled:
                continue

            phase = phase_by_name.get(item.phase_name or "")
            role = role_by_type.get(item.default_role_type, role_by_type.get(RoleType.project_manager))
            plan = ProjectDocumentPlan(
                project_id=project_id,
                phase_id=phase.id if phase else None,
                catalog_item_id=item.id or 0,
                role_id=role.id if role else None,
                code=item.code,
                title=item.name,
                description=item.description,
                outline_md=item.outline_md,
                is_periodic=item.is_periodic,
                period_type=item.period_type,
                sort_order=item.sort_order,
                dependency_codes=item.dependency_codes,
            )
            self.session.add(plan)
            created_plans.append(plan)

        self.session.flush()
        plan_by_code = {plan.code: plan for plan in created_plans}
        for plan in created_plans:
            plan.dependency_plan_ids = [
                dependency.id
                for code in plan.dependency_codes
                if (dependency := plan_by_code.get(code)) is not None and dependency.id is not None
            ]
            self.session.add(plan)

    def ensure_roles_and_plans(self, project_id: int) -> None:
        project = self.session.get(Project, project_id)
        if project is None:
            raise ValueError("Project not found")

        role_by_type = {
            role.role_type: role
            for role in self.session.exec(
                select(ProjectRole).where(ProjectRole.project_id == project_id)
            ).all()
        }
        if not role_by_type:
            role_by_type = self._seed_roles(project_id)

        phase_by_name = {
            phase.name: phase
            for phase in self.session.exec(
                select(LifecyclePhase).where(LifecyclePhase.project_id == project_id)
            ).all()
        }
        if not phase_by_name:
            phase_by_name = self._seed_lifecycle(project_id)

        has_plans = self.session.exec(
            select(ProjectDocumentPlan.id).where(ProjectDocumentPlan.project_id == project_id)
        ).first()
        if has_plans is None:
            CatalogService(self.session).seed_document_catalog()
            self._seed_document_plans(project_id, phase_by_name, role_by_type, None)

        self.session.commit()

    def delete_project(self, project_id: int, document_storage_path: str | None = None) -> None:
        project = self.session.get(Project, project_id)
        if project is None:
            raise ValueError("Project not found")

        documents = self.session.exec(
            select(ProjectDocument).where(ProjectDocument.project_id == project_id)
        ).all()
        document_ids = [document.id for document in documents if document.id is not None]
        if document_ids:
            self._delete_all(
                ProjectDocumentVersion,
                col(ProjectDocumentVersion.document_id).in_(document_ids),
            )

        self._delete_all(DocumentGenerationRun, DocumentGenerationRun.project_id == project_id)
        self._delete_all(WorkRecord, WorkRecord.project_id == project_id)
        self._delete_all(TaskArtifact, TaskArtifact.project_id == project_id)
        self._delete_all(ReportingWindow, ReportingWindow.project_id == project_id)

        template_ids = [
            template.id
            for template in self.session.exec(
                select(DocumentTemplate).where(DocumentTemplate.project_id == project_id)
            ).all()
            if template.id is not None
        ]
        role_ids = [
            role.id
            for role in self.session.exec(
                select(ProjectRole).where(ProjectRole.project_id == project_id)
            ).all()
            if role.id is not None
        ]
        if template_ids:
            self._delete_all(
                DocumentRoleAssignment,
                col(DocumentRoleAssignment.template_id).in_(template_ids),
            )
        if role_ids:
            self._delete_all(
                DocumentRoleAssignment,
                col(DocumentRoleAssignment.role_id).in_(role_ids),
            )

        self._delete_all(ProjectDocument, ProjectDocument.project_id == project_id)
        self._delete_all(ProjectDocumentPlan, ProjectDocumentPlan.project_id == project_id)
        self._delete_all(DocumentTemplate, DocumentTemplate.project_id == project_id)
        self._delete_all(ProjectRole, ProjectRole.project_id == project_id)
        self._delete_all(ProjectTask, ProjectTask.project_id == project_id)
        self._delete_all(LifecyclePhase, LifecyclePhase.project_id == project_id)

        self.session.delete(project)
        self.session.commit()

        if document_storage_path:
            self._delete_project_document_dir(project_id, document_storage_path)

    def _delete_all(self, model: type, condition: object) -> None:
        for item in self.session.exec(select(model).where(condition)).all():
            self.session.delete(item)

    def _delete_project_document_dir(self, project_id: int, document_storage_path: str) -> None:
        root = Path(document_storage_path).resolve()
        target = (root / f"project-{project_id}").resolve()
        if not target.exists() or not target.is_dir():
            return
        if not target.is_relative_to(root):
            return
        for path in sorted(target.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        target.rmdir()

    def _seed_tasks(self, project_id: int | None, task_descriptions: list[str]) -> None:
        if project_id is None:
            return

        for index, description in enumerate(task_descriptions, start=1):
            text = description.strip()
            if text:
                self.session.add(
                    ProjectTask(
                        project_id=project_id,
                        title=f"任务 {index}",
                        description=text,
                    )
                )


class MarkdownImportService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def import_markdown(
        self,
        *,
        project_id: int,
        filename: str,
        content_md: str,
        phase_id: int | None,
        import_as_template: bool = True,
        import_as_reference_document: bool = True,
        template_name: str | None = None,
        description: str = "",
    ) -> MarkdownImportResult:
        project = self.session.get(Project, project_id)
        if project is None or project.id is None:
            raise ValueError("Project not found")

        phase = self._get_phase(project_id, phase_id)
        title = (template_name or self._title_from_markdown(filename, content_md)).strip()
        if not title:
            raise ValueError("Document title is required")
        if not content_md.strip():
            raise ValueError("Markdown content is required")

        document = None
        if import_as_reference_document:
            document = ProjectDocument(
                project_id=project.id,
                phase_id=phase.id if phase else None,
                title=title,
                status=DocumentStatus.approved,
                content_md=content_md.strip(),
            )
            self.session.add(document)
            self.session.flush()
            self.session.refresh(document)
            document.file_path = self._write_imported_document(project, document, filename)
            self.session.add(document)

        catalog_item = None
        if import_as_template:
            catalog_item = self._create_catalog_item(
                title=title,
                phase=phase,
                outline_md=extract_markdown_outline(content_md, fallback_title=title),
                description=description or f"Imported from {filename}",
            )
            self.session.add(catalog_item)
            self.session.flush()
            TemplateLibraryService(self.session, self.settings).export_catalog_to_markdown(
                overwrite=False
            )

        self.session.commit()
        if document is not None:
            self.session.refresh(document)
        if catalog_item is not None:
            self.session.refresh(catalog_item)
        return MarkdownImportResult(document=document, catalog_item=catalog_item)

    def _get_phase(self, project_id: int, phase_id: int | None) -> LifecyclePhase | None:
        if phase_id is None:
            return None
        phase = self.session.get(LifecyclePhase, phase_id)
        if phase is None or phase.project_id != project_id:
            raise ValueError("Lifecycle phase not found")
        return phase

    def _create_catalog_item(
        self,
        *,
        title: str,
        phase: LifecyclePhase | None,
        outline_md: str,
        description: str,
    ) -> DocumentCatalogItem:
        sort_order = self._next_sort_order(phase)
        code = self._unique_code(title, sort_order)
        return DocumentCatalogItem(
            code=code,
            phase_name=phase.name if phase else None,
            name=title,
            description=description,
            outline_md=outline_md,
            default_role_type=RoleType.project_manager,
            default_selected=False,
            sort_order=sort_order,
        )

    def _next_sort_order(self, phase: LifecyclePhase | None) -> int:
        statement = select(DocumentCatalogItem)
        if phase is None:
            statement = statement.where(DocumentCatalogItem.is_periodic)
            base = 1000
        else:
            statement = statement.where(DocumentCatalogItem.phase_name == phase.name)
            base = phase.order_index * 100
        items = self.session.exec(statement.order_by(DocumentCatalogItem.sort_order.desc())).all()
        current_max = items[0].sort_order if items else base
        return max(base, current_max) + 1

    def _unique_code(self, title: str, sort_order: int) -> str:
        base = ascii_slug(title) or "markdown"
        prefix = f"imported-{sort_order}-{base}"[:80].strip("-")
        code = prefix
        index = 2
        existing_codes = set(self.session.exec(select(DocumentCatalogItem.code)).all())
        while code in existing_codes:
            code = f"{prefix}-{index}"
            index += 1
        return code

    def _title_from_markdown(self, filename: str, content_md: str) -> str:
        for line in content_md.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return Path(filename).stem

    def _write_imported_document(
        self,
        project: Project,
        document: ProjectDocument,
        filename: str,
    ) -> str:
        root = Path(self.settings.document_storage_path)
        project_dir = root / f"project-{project.id}" / "imports"
        project_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix or ".md"
        filename_part = sanitize_path_part(document.title)
        path = project_dir / f"{document.id}-{filename_part}{suffix}"
        path.write_text(render_project_document_file(document, []), encoding="utf-8")
        return str(path)


class DocumentGenerationService:
    def __init__(self, session: Session, settings: Settings, llm: LLMClient) -> None:
        self.session = session
        self.settings = settings
        self.llm = llm

    def preview_document(
        self,
        plan_id: int | None = None,
        template_id: int | None = None,
        extra_instruction: str = "",
    ) -> GenerationPreview:
        if plan_id is not None:
            return self._preview_plan(plan_id, extra_instruction)
        if template_id is not None:
            return self._preview_legacy_template(template_id, extra_instruction)
        raise ValueError("Document plan or template is required")

    def generate_document(
        self,
        plan_id: int | None = None,
        template_id: int | None = None,
        extra_instruction: str = "",
    ) -> ProjectDocument:
        preview = self.preview_document(plan_id, template_id, extra_instruction)

        if preview.plan_id is not None:
            plan = self.session.get(ProjectDocumentPlan, preview.plan_id)
            if plan is None:
                raise ValueError("Document plan not found")
            project = self._get_project(plan.project_id)
            document = self._get_existing_document(project.id, plan_id=plan.id) or ProjectDocument(
                project_id=project.id,
                phase_id=plan.phase_id,
                plan_id=plan.id,
                title=plan.title,
            )
            document.phase_id = plan.phase_id
            document.title = plan.title
            plan.status = DocumentPlanStatus.generated
            plan.updated_at = datetime.utcnow()
            self.session.add(plan)
        else:
            template = self.session.get(DocumentTemplate, preview.template_id)
            if template is None:
                raise ValueError("Document template not found")
            project = self._get_project(template.project_id)
            document = self._get_existing_document(
                project.id,
                template_id=template.id,
            ) or ProjectDocument(
                project_id=project.id,
                phase_id=template.phase_id,
                template_id=template.id,
                title=template.name,
            )
            document.phase_id = template.phase_id
            document.title = template.name

        content = self.llm.generate(
            LLMRequest(system_prompt=preview.system_prompt, user_prompt=preview.user_prompt)
        )
        document.content_md = content
        document.status = DocumentStatus.generated
        document.source_document_ids = preview.source_document_ids
        document.updated_at = datetime.utcnow()
        self.session.add(document)
        self.session.flush()
        self.session.refresh(document)

        document.file_path = self._write_document(project, document)
        self.session.add(document)
        self.session.flush()

        self._create_document_version(document, content, preview, "生成文档版本")
        self.session.add(
            DocumentGenerationRun(
                project_id=project.id,
                template_id=preview.template_id,
                plan_id=preview.plan_id,
                document_id=document.id,
                role_id=preview.role_id,
                prompt=preview.user_prompt,
                context_md=preview.context_md,
                source_document_ids=preview.source_document_ids,
                source_artifact_ids=preview.source_artifact_ids,
                source_work_record_ids=preview.source_work_record_ids,
            )
        )
        self.session.commit()
        self.session.refresh(document)
        return document

    def _get_existing_document(
        self,
        project_id: int,
        *,
        plan_id: int | None = None,
        template_id: int | None = None,
    ) -> ProjectDocument | None:
        statement = select(ProjectDocument).where(ProjectDocument.project_id == project_id)
        if plan_id is not None:
            statement = statement.where(ProjectDocument.plan_id == plan_id)
        elif template_id is not None:
            statement = statement.where(ProjectDocument.template_id == template_id)
        else:
            return None
        return self.session.exec(statement.order_by(ProjectDocument.id.desc())).first()

    def _preview_plan(self, plan_id: int, extra_instruction: str) -> GenerationPreview:
        plan = self.session.get(ProjectDocumentPlan, plan_id)
        if plan is None:
            raise ValueError("Document plan not found")

        project = self._get_project(plan.project_id)
        phase = self.session.get(LifecyclePhase, plan.phase_id) if plan.phase_id else None
        role = self.session.get(ProjectRole, plan.role_id) if plan.role_id else None
        context_docs = self._select_context_documents_for_plan(plan)
        work_records = self._select_work_records_for_plan(plan)
        legacy_artifacts = self._select_legacy_artifacts_for_plan(plan)
        context_md = self._build_context(context_docs, work_records, legacy_artifacts)
        user_prompt = self._build_plan_prompt(
            project=project,
            phase=phase,
            plan=plan,
            context_md=context_md,
            role=role,
            extra_instruction=extra_instruction,
        )
        return GenerationPreview(
            project_id=project.id,
            plan_id=plan.id,
            template_id=None,
            role_id=role.id if role else None,
            role_name=role.name if role else "项目经理",
            system_prompt=self._build_system_prompt(role),
            user_prompt=user_prompt,
            context_md=context_md,
            source_document_ids=[doc.id for doc in context_docs if doc.id is not None],
            source_artifact_ids=[artifact.id for artifact in legacy_artifacts if artifact.id is not None],
            source_work_record_ids=[record.id for record in work_records if record.id is not None],
        )

    def _preview_legacy_template(self, template_id: int, extra_instruction: str) -> GenerationPreview:
        template = self.session.get(DocumentTemplate, template_id)
        if template is None:
            raise ValueError("Document template not found")

        project = self._get_project(template.project_id)
        phase = self.session.get(LifecyclePhase, template.phase_id) if template.phase_id else None
        role = self._select_legacy_role(template)
        context_docs = self._select_context_documents_for_template(template)
        legacy_artifacts = self._select_legacy_artifacts_for_template(template)
        context_md = self._build_context(context_docs, [], legacy_artifacts)
        user_prompt = self._build_template_prompt(
            project=project,
            phase=phase,
            template=template,
            context_md=context_md,
            role=role,
            extra_instruction=extra_instruction,
        )
        return GenerationPreview(
            project_id=project.id,
            plan_id=None,
            template_id=template.id,
            role_id=role.id if role else None,
            role_name=role.name if role else "项目经理",
            system_prompt=self._build_system_prompt(role),
            user_prompt=user_prompt,
            context_md=context_md,
            source_document_ids=[doc.id for doc in context_docs if doc.id is not None],
            source_artifact_ids=[artifact.id for artifact in legacy_artifacts if artifact.id is not None],
            source_work_record_ids=[],
        )

    def _get_project(self, project_id: int | None) -> Project:
        project = self.session.get(Project, project_id)
        if project is None or project.id is None:
            raise ValueError("Project not found")
        return project

    def _select_context_documents_for_plan(self, plan: ProjectDocumentPlan) -> list[ProjectDocument]:
        statement = select(ProjectDocument).where(ProjectDocument.project_id == plan.project_id)
        explicit_docs = self._documents_by_reference_ids(plan)
        if plan.is_periodic:
            return self._dedupe_documents(
                explicit_docs
                + list(self.session.exec(statement.order_by(ProjectDocument.updated_at.desc())).all())[:6]
            )

        dependency_docs = self._dedupe_documents(
            explicit_docs
            + self._documents_by_dependency_plan_ids(plan)
            + self._documents_by_dependency_codes(plan)
        )
        if dependency_docs:
            return dependency_docs

        if plan.phase_id is None:
            return []
        phase = self.session.get(LifecyclePhase, plan.phase_id)
        if phase is None:
            return []
        previous_phase_ids = self.session.exec(
            select(LifecyclePhase.id)
            .where(
                LifecyclePhase.project_id == plan.project_id,
                LifecyclePhase.order_index < phase.order_index,
            )
            .order_by(LifecyclePhase.order_index.desc())
        ).all()
        if not previous_phase_ids:
            return []
        return self._dedupe_documents(
            list(
                self.session.exec(
                    statement.where(col(ProjectDocument.phase_id).in_(previous_phase_ids)).order_by(
                        ProjectDocument.updated_at.desc()
                    )
                ).all()[:6]
            )
        )

    def _documents_by_dependency_plan_ids(self, plan: ProjectDocumentPlan) -> list[ProjectDocument]:
        return self._latest_documents_for_plan_ids(plan.dependency_plan_ids or [])

    def _documents_by_reference_ids(self, plan: ProjectDocumentPlan) -> list[ProjectDocument]:
        reference_ids = plan.reference_document_ids or []
        if not reference_ids:
            return []
        return list(
            self.session.exec(
                select(ProjectDocument)
                .where(
                    ProjectDocument.project_id == plan.project_id,
                    col(ProjectDocument.id).in_(reference_ids),
                )
                .order_by(ProjectDocument.updated_at.desc(), ProjectDocument.id.desc())
            ).all()
        )

    def _documents_by_dependency_codes(self, plan: ProjectDocumentPlan) -> list[ProjectDocument]:
        if not plan.dependency_codes:
            return []

        dependency_plans = self.session.exec(
            select(ProjectDocumentPlan).where(
                ProjectDocumentPlan.project_id == plan.project_id,
                col(ProjectDocumentPlan.code).in_(plan.dependency_codes),
            )
        ).all()
        dependency_plan_ids = [item.id for item in dependency_plans if item.id is not None]
        if not dependency_plan_ids:
            return []
        return self._latest_documents_for_plan_ids(dependency_plan_ids)

    def _latest_documents_for_plan_ids(self, plan_ids: list[int]) -> list[ProjectDocument]:
        if not plan_ids:
            return []
        documents = self.session.exec(
            select(ProjectDocument)
            .where(col(ProjectDocument.plan_id).in_(plan_ids))
            .order_by(ProjectDocument.updated_at.desc(), ProjectDocument.id.desc())
        ).all()
        seen_plan_ids: set[int] = set()
        latest_documents: list[ProjectDocument] = []
        for document in documents:
            if document.plan_id is None or document.plan_id in seen_plan_ids:
                continue
            seen_plan_ids.add(document.plan_id)
            latest_documents.append(document)
        return latest_documents

    def _dedupe_documents(self, documents: list[ProjectDocument]) -> list[ProjectDocument]:
        seen_document_ids: set[int] = set()
        seen_plan_ids: set[int] = set()
        seen_titles: set[tuple[int, str]] = set()
        result: list[ProjectDocument] = []
        for document in documents:
            if document.id is not None and document.id in seen_document_ids:
                continue
            if document.plan_id is not None:
                if document.plan_id in seen_plan_ids:
                    continue
                seen_plan_ids.add(document.plan_id)
            title_key = (document.phase_id or 0, document.title.strip())
            if document.title and title_key in seen_titles:
                continue
            if document.id is not None:
                seen_document_ids.add(document.id)
            if document.title:
                seen_titles.add(title_key)
            result.append(document)
        return result

    def _select_work_records_for_plan(self, plan: ProjectDocumentPlan) -> list[WorkRecord]:
        statement = select(WorkRecord).where(WorkRecord.project_id == plan.project_id)
        if plan.is_periodic:
            latest_window = self.session.exec(
                select(ReportingWindow)
                .where(
                    ReportingWindow.project_id == plan.project_id,
                    ReportingWindow.window_type == (plan.period_type or "weekly"),
                )
                .order_by(ReportingWindow.end_date.desc())
            ).first()
            if latest_window is not None:
                statement = statement.where(WorkRecord.window_id == latest_window.id)
        elif plan.phase_id is not None:
            statement = statement.where(WorkRecord.phase_id == plan.phase_id)
        return list(self.session.exec(statement.order_by(WorkRecord.created_at.desc())).all()[:12])

    def _select_legacy_artifacts_for_plan(self, plan: ProjectDocumentPlan) -> list[TaskArtifact]:
        statement = select(TaskArtifact).where(TaskArtifact.project_id == plan.project_id)
        if plan.is_periodic:
            latest_window = self.session.exec(
                select(ReportingWindow)
                .where(
                    ReportingWindow.project_id == plan.project_id,
                    ReportingWindow.window_type == (plan.period_type or "weekly"),
                )
                .order_by(ReportingWindow.end_date.desc())
            ).first()
            if latest_window is not None:
                statement = statement.where(TaskArtifact.window_id == latest_window.id)
        return list(self.session.exec(statement.order_by(TaskArtifact.created_at.desc())).all()[:8])

    def _select_context_documents_for_template(self, template: DocumentTemplate) -> list[ProjectDocument]:
        statement = select(ProjectDocument).where(ProjectDocument.project_id == template.project_id)
        if template.is_periodic:
            return self._dedupe_documents(
                list(self.session.exec(statement.order_by(ProjectDocument.updated_at.desc())).all())[:6]
            )
        if template.phase_id is None:
            return []
        phase = self.session.get(LifecyclePhase, template.phase_id)
        if phase is None:
            return []
        previous_phase_ids = self.session.exec(
            select(LifecyclePhase.id)
            .where(
                LifecyclePhase.project_id == template.project_id,
                LifecyclePhase.order_index < phase.order_index,
            )
            .order_by(LifecyclePhase.order_index.desc())
        ).all()
        if not previous_phase_ids:
            return []
        return self._dedupe_documents(
            list(
                self.session.exec(
                    statement.where(col(ProjectDocument.phase_id).in_(previous_phase_ids)).order_by(
                        ProjectDocument.updated_at.desc()
                    )
                ).all()[:6]
            )
        )

    def _select_legacy_artifacts_for_template(self, template: DocumentTemplate) -> list[TaskArtifact]:
        statement = select(TaskArtifact).where(TaskArtifact.project_id == template.project_id)
        if template.is_periodic:
            latest_window = self.session.exec(
                select(ReportingWindow)
                .where(
                    ReportingWindow.project_id == template.project_id,
                    ReportingWindow.window_type == (template.period_type or "weekly"),
                )
                .order_by(ReportingWindow.end_date.desc())
            ).first()
            if latest_window is not None:
                statement = statement.where(TaskArtifact.window_id == latest_window.id)
        return list(self.session.exec(statement.order_by(TaskArtifact.created_at.desc())).all()[:8])

    def _build_context(
        self,
        context_docs: list[ProjectDocument],
        work_records: list[WorkRecord],
        legacy_artifacts: list[TaskArtifact],
    ) -> str:
        doc_block = "\n\n".join(
            f"## 引用文档：{doc.title}\n{doc.content_md[:4000]}" for doc in context_docs
        )
        record_block = "\n\n".join(
            f"## 工作记录：{record.title}\n{record.content[:2000]}" for record in work_records
        )
        artifact_block = "\n\n".join(
            f"## 历史任务产物：{artifact.title}\n{artifact.content[:2000]}"
            for artifact in legacy_artifacts
        )
        return "\n\n".join(block for block in [doc_block, record_block, artifact_block] if block) or (
            "暂无可引用的前序文档或工作记录。请只基于当前阶段、当前模板和必要项目摘要生成，不要编造事实。"
        )

    def _build_system_prompt(self, role: ProjectRole | None) -> str:
        role_prompt = role.agent_prompt if role else "你是项目经理，请关注项目交付质量。"
        return (
            f"{role_prompt}\n"
            "请使用严谨、可交付的中文 Markdown 生成项目文档；保持阶段继承关系；"
            "显式引用输入材料中的关键信息；不要编造未出现在项目材料中的确定性事实。"
        )

    def _project_summary(self, project: Project, phase: LifecyclePhase | None) -> str:
        requirement_note = ""
        if phase is not None and phase.name == "需求调研":
            requirement_note = f"\n需求原始材料：\n{project.requirements[:3000]}"
        return (
            f"项目名称：{project.name}\n"
            f"项目背景：{project.background[:1200]}\n"
            f"项目周期：{project.start_date or '未设置'} 至 {project.end_date or '未设置'}"
            f"{requirement_note}"
        )

    def _build_plan_prompt(
        self,
        project: Project,
        phase: LifecyclePhase | None,
        plan: ProjectDocumentPlan,
        context_md: str,
        role: ProjectRole | None,
        extra_instruction: str,
    ) -> str:
        role_block = (
            f"{role.name}：{role.responsibility}" if role else "项目经理：负责组织项目交付物。"
        )
        phase_block = f"{phase.name}：{phase.description}" if phase else "周期性项目管理文档"
        dependencies = self._dependency_summary(plan)
        return f"""
请生成文档：{plan.title}

负责角色：
{role_block}

当前阶段：
{phase_block}

必要项目摘要：
{self._project_summary(project, phase)}

文档大纲模板：
{plan.outline_md}

依赖文档策略：
优先导入并引用以下前序文档的已生成版本：{dependencies}。
如果依赖文档不存在，只能使用当前阶段信息、必要项目摘要和已提供上下文，不得强行补全事实。

已选择的上下文材料：
{context_md}

额外要求：
{extra_instruction or "无"}
""".strip()

    def _dependency_summary(self, plan: ProjectDocumentPlan) -> str:
        dependency_plan_ids = list(plan.dependency_plan_ids or [])
        if not dependency_plan_ids and plan.dependency_codes:
            dependency_plan_ids = [
                item.id
                for item in self.session.exec(
                    select(ProjectDocumentPlan).where(
                        ProjectDocumentPlan.project_id == plan.project_id,
                        col(ProjectDocumentPlan.code).in_(plan.dependency_codes),
                    )
                ).all()
                if item.id is not None
            ]
        if not dependency_plan_ids:
            return "无显式依赖"

        plans = self.session.exec(
            select(ProjectDocumentPlan)
            .where(col(ProjectDocumentPlan.id).in_(dependency_plan_ids))
            .order_by(ProjectDocumentPlan.sort_order)
        ).all()
        seen: set[int] = set()
        names: list[str] = []
        for dependency in plans:
            if dependency.id is None or dependency.id in seen:
                continue
            seen.add(dependency.id)
            names.append(dependency.title)
        return "、".join(names) if names else "无显式依赖"

    def _build_template_prompt(
        self,
        project: Project,
        phase: LifecyclePhase | None,
        template: DocumentTemplate,
        context_md: str,
        role: ProjectRole | None,
        extra_instruction: str,
    ) -> str:
        role_block = (
            f"{role.name}：{role.responsibility}" if role else "项目经理：负责组织项目交付物。"
        )
        phase_block = f"{phase.name}：{phase.description}" if phase else "周期性项目管理文档"
        return f"""
请生成文档：{template.name}

负责角色：
{role_block}

当前阶段：
{phase_block}

必要项目摘要：
{self._project_summary(project, phase)}

文档大纲模板：
{template.outline_md}

已选择的上下文材料：
{context_md}

额外要求：
{extra_instruction or "无"}
""".strip()

    def _select_legacy_role(self, template: DocumentTemplate) -> ProjectRole | None:
        assignment = self.session.exec(
            select(DocumentRoleAssignment).where(DocumentRoleAssignment.template_id == template.id)
        ).first()
        if assignment is not None:
            return self.session.get(ProjectRole, assignment.role_id)

        return self.session.exec(
            select(ProjectRole).where(
                ProjectRole.project_id == template.project_id,
                ProjectRole.role_type == RoleType.project_manager,
            )
        ).first()

    def _create_document_version(
        self,
        document: ProjectDocument,
        content: str,
        preview: GenerationPreview,
        change_summary: str,
    ) -> None:
        if document.id is None:
            return
        latest = self.session.exec(
            select(ProjectDocumentVersion)
            .where(ProjectDocumentVersion.document_id == document.id)
            .order_by(ProjectDocumentVersion.version_number.desc())
        ).first()
        version_number = 1 if latest is None else latest.version_number + 1
        self.session.add(
            ProjectDocumentVersion(
                document_id=document.id,
                version_number=version_number,
                content_md=content,
                change_summary=change_summary,
                prompt_snapshot=preview.user_prompt,
                context_snapshot=preview.context_md,
                created_by_role_id=preview.role_id,
            )
        )

    def _write_document(self, project: Project, document: ProjectDocument) -> str:
        root = Path(self.settings.document_storage_path)
        project_dir = root / f"project-{project.id}"
        project_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{document.id}-{document.title}.md".replace("/", "-").replace("\\", "-")
        path = project_dir / filename
        forward_documents = self._documents_by_ids(document.source_document_ids or [])
        path.write_text(render_project_document_file(document, forward_documents), encoding="utf-8")
        return str(path)

    def _documents_by_ids(self, document_ids: list[int]) -> list[ProjectDocument]:
        if not document_ids:
            return []
        return list(
            self.session.exec(
                select(ProjectDocument)
                .where(col(ProjectDocument.id).in_(document_ids))
                .order_by(ProjectDocument.updated_at.desc(), ProjectDocument.id.desc())
            ).all()
        )


def render_project_document_file(
    document: ProjectDocument,
    forward_documents: list[ProjectDocument],
) -> str:
    metadata = {
        "project_id": str(document.project_id),
        "document_id": str(document.id or ""),
        "phase_id": str(document.phase_id or ""),
        "plan_id": str(document.plan_id or ""),
        "template_id": str(document.template_id or ""),
        "status": document.status.value,
    }
    lines = ["---", *[f"{key}: {value}" for key, value in metadata.items()], "---", ""]
    links = [obsidian_link_for_project_document(item) for item in forward_documents]
    body = render_project_document_link_section(links) + strip_markdown_frontmatter(
        document.content_md
    ).strip()
    return "\n".join(lines) + body.strip() + "\n"


def obsidian_link_for_project_document(document: ProjectDocument) -> str:
    return f"[[{obsidian_note_title_for_project_document(document)}]]"


def obsidian_note_title_for_project_document(document: ProjectDocument) -> str:
    if document.file_path:
        return Path(document.file_path).stem
    return f"{document.id or 'draft'}-{sanitize_path_part(document.title)}"


def render_project_document_link_section(links: list[str]) -> str:
    if not links:
        return ""
    lines = ["## 关联文件", "", *[f"- {link}" for link in links], ""]
    return "\n".join(lines) + "\n"


def strip_markdown_frontmatter(content_md: str) -> str:
    if not content_md.startswith("---\n"):
        return content_md
    parts = content_md.split("---", 2)
    if len(parts) < 3:
        return content_md
    return parts[2].lstrip()
