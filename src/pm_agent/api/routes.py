from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from pm_agent.api.schemas import (
    CatalogItemRead,
    DocumentRead,
    DocumentVersionRead,
    GenerateDocumentRequest,
    GenerationPreviewRead,
    PhaseRead,
    ProjectCreate,
    ProjectDocumentPlanRead,
    ProjectRead,
    ReportingWindowCreate,
    ReportingWindowRead,
    RoleRead,
    TaskArtifactCreate,
    TaskArtifactRead,
    TaskCreate,
    TaskRead,
    TemplateCreate,
    TemplateRead,
    WorkRecordCreate,
    WorkRecordRead,
)
from pm_agent.config import get_settings
from pm_agent.db import get_session
from pm_agent.llm import OpenAICompatibleClient
from pm_agent.models import (
    DocumentCatalogItem,
    DocumentTemplate,
    LifecyclePhase,
    Project,
    ProjectDocument,
    ProjectDocumentPlan,
    ProjectDocumentVersion,
    ProjectRole,
    ProjectTask,
    ReportingWindow,
    TaskArtifact,
    WorkRecord,
)
from pm_agent.services import CatalogService, DocumentGenerationService, ProjectService
from pm_agent.template_library import TemplateLibraryService

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> Project:
    project = Project(
        name=payload.name,
        background=payload.background,
        requirements=payload.requirements,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return ProjectService(session).create_project(
        project,
        payload.tasks,
        payload.selected_document_codes,
    )


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    return list(session.exec(select(Project).order_by(Project.created_at.desc())).all())


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: Session = Depends(get_session)) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)) -> dict[str, int | str]:
    settings = get_settings()
    try:
        ProjectService(session).delete_project(project_id, settings.document_storage_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": project_id, "status": "ok"}


@router.get("/projects/{project_id}/phases", response_model=list[PhaseRead])
def list_phases(project_id: int, session: Session = Depends(get_session)) -> list[LifecyclePhase]:
    return list(
        session.exec(
            select(LifecyclePhase)
            .where(LifecyclePhase.project_id == project_id)
            .order_by(LifecyclePhase.order_index)
        ).all()
    )


@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead])
def list_tasks(project_id: int, session: Session = Depends(get_session)) -> list[ProjectTask]:
    return list(session.exec(select(ProjectTask).where(ProjectTask.project_id == project_id)).all())


@router.post("/tasks", response_model=TaskRead)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)) -> ProjectTask:
    task = ProjectTask(**payload.model_dump())
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("/projects/{project_id}/roles", response_model=list[RoleRead])
def list_roles(project_id: int, session: Session = Depends(get_session)) -> list[ProjectRole]:
    ProjectService(session).ensure_roles_and_plans(project_id)
    roles = list(session.exec(select(ProjectRole).where(ProjectRole.project_id == project_id)).all())
    if roles:
        return roles

    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    service = ProjectService(session)
    role_by_type = service._seed_roles(project_id)
    service._assign_template_roles(project_id, role_by_type)
    session.commit()
    return list(session.exec(select(ProjectRole).where(ProjectRole.project_id == project_id)).all())


@router.get("/document-catalog", response_model=list[CatalogItemRead])
def list_document_catalog(session: Session = Depends(get_session)) -> list[DocumentCatalogItem]:
    return CatalogService(session).list_catalog()


@router.post("/document-catalog/export-md")
def export_document_catalog_md(
    overwrite: bool = False,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    settings = get_settings()
    paths = TemplateLibraryService(session, settings).export_catalog_to_markdown(overwrite)
    return {"exported": len(paths), "paths": paths}


@router.post("/document-catalog/reset-builtin-md")
def reset_builtin_document_catalog_md(
    overwrite: bool = True,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    settings = get_settings()
    service = TemplateLibraryService(session, settings)
    reset_count = service.reset_builtin_catalog()
    paths = service.export_catalog_to_markdown(overwrite)
    return {"reset": reset_count, "exported": len(paths), "paths": paths}


@router.post("/document-catalog/sync-md")
def sync_document_catalog_md(session: Session = Depends(get_session)) -> dict[str, int]:
    settings = get_settings()
    count = TemplateLibraryService(session, settings).sync_markdown_to_catalog()
    return {"synced": count}


@router.get("/projects/{project_id}/document-plans", response_model=list[ProjectDocumentPlanRead])
def list_document_plans(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[ProjectDocumentPlan]:
    ProjectService(session).ensure_roles_and_plans(project_id)
    return list(
        session.exec(
            select(ProjectDocumentPlan)
            .where(ProjectDocumentPlan.project_id == project_id, ProjectDocumentPlan.is_enabled)
            .order_by(ProjectDocumentPlan.is_periodic, ProjectDocumentPlan.sort_order)
        ).all()
    )


@router.get(
    "/projects/{project_id}/phases/{phase_id}/document-plans",
    response_model=list[ProjectDocumentPlanRead],
)
def list_phase_document_plans(
    project_id: int,
    phase_id: int,
    session: Session = Depends(get_session),
) -> list[ProjectDocumentPlan]:
    ProjectService(session).ensure_roles_and_plans(project_id)
    return list(
        session.exec(
            select(ProjectDocumentPlan)
            .where(
                ProjectDocumentPlan.project_id == project_id,
                ProjectDocumentPlan.phase_id == phase_id,
                ProjectDocumentPlan.is_enabled,
            )
            .order_by(ProjectDocumentPlan.sort_order)
        ).all()
    )


@router.post("/templates", response_model=TemplateRead)
def create_template(
    payload: TemplateCreate,
    session: Session = Depends(get_session),
) -> DocumentTemplate:
    template = DocumentTemplate(**payload.model_dump())
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@router.get("/projects/{project_id}/templates", response_model=list[TemplateRead])
def list_templates(project_id: int, session: Session = Depends(get_session)) -> list[DocumentTemplate]:
    return list(
        session.exec(
            select(DocumentTemplate)
            .where(DocumentTemplate.project_id == project_id)
            .order_by(DocumentTemplate.is_periodic, DocumentTemplate.id)
        ).all()
    )


@router.get("/projects/{project_id}/documents", response_model=list[DocumentRead])
def list_documents(project_id: int, session: Session = Depends(get_session)) -> list[ProjectDocument]:
    return list(
        session.exec(
            select(ProjectDocument)
            .where(ProjectDocument.project_id == project_id)
            .order_by(ProjectDocument.updated_at.desc())
        ).all()
    )


@router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionRead])
def list_document_versions(
    document_id: int,
    session: Session = Depends(get_session),
) -> list[ProjectDocumentVersion]:
    return list(
        session.exec(
            select(ProjectDocumentVersion)
            .where(ProjectDocumentVersion.document_id == document_id)
            .order_by(ProjectDocumentVersion.version_number.desc())
        ).all()
    )


@router.post("/windows", response_model=ReportingWindowRead)
def create_reporting_window(
    payload: ReportingWindowCreate,
    session: Session = Depends(get_session),
) -> ReportingWindow:
    window = ReportingWindow(**payload.model_dump())
    session.add(window)
    session.commit()
    session.refresh(window)
    return window


@router.get("/projects/{project_id}/windows", response_model=list[ReportingWindowRead])
def list_reporting_windows(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[ReportingWindow]:
    return list(
        session.exec(
            select(ReportingWindow)
            .where(ReportingWindow.project_id == project_id)
            .order_by(ReportingWindow.end_date.desc())
        ).all()
    )


@router.post("/artifacts", response_model=TaskArtifactRead)
def create_task_artifact(
    payload: TaskArtifactCreate,
    session: Session = Depends(get_session),
) -> TaskArtifact:
    artifact = TaskArtifact(**payload.model_dump())
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


@router.get("/projects/{project_id}/artifacts", response_model=list[TaskArtifactRead])
def list_task_artifacts(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[TaskArtifact]:
    return list(
        session.exec(
            select(TaskArtifact)
            .where(TaskArtifact.project_id == project_id)
            .order_by(TaskArtifact.created_at.desc())
        ).all()
    )


@router.post("/work-records", response_model=WorkRecordRead)
def create_work_record(
    payload: WorkRecordCreate,
    session: Session = Depends(get_session),
) -> WorkRecord:
    record = WorkRecord(**payload.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.get("/projects/{project_id}/work-records", response_model=list[WorkRecordRead])
def list_work_records(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[WorkRecord]:
    return list(
        session.exec(
            select(WorkRecord)
            .where(WorkRecord.project_id == project_id)
            .order_by(WorkRecord.created_at.desc())
        ).all()
    )


@router.post("/documents/preview", response_model=GenerationPreviewRead)
def preview_document(
    payload: GenerateDocumentRequest,
    session: Session = Depends(get_session),
) -> GenerationPreviewRead:
    settings = get_settings()
    service = DocumentGenerationService(
        session=session,
        settings=settings,
        llm=OpenAICompatibleClient(settings),
    )
    try:
        preview = service.preview_document(
            plan_id=payload.plan_id,
            template_id=payload.template_id,
            extra_instruction=payload.extra_instruction,
        )
        return GenerationPreviewRead(**preview.__dict__)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents/generate", response_model=DocumentRead)
def generate_document(
    payload: GenerateDocumentRequest,
    session: Session = Depends(get_session),
) -> ProjectDocument:
    settings = get_settings()
    service = DocumentGenerationService(
        session=session,
        settings=settings,
        llm=OpenAICompatibleClient(settings),
    )
    try:
        return service.generate_document(
            plan_id=payload.plan_id,
            template_id=payload.template_id,
            extra_instruction=payload.extra_instruction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
