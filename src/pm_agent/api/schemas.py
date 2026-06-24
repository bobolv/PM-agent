from datetime import date, datetime

from pydantic import BaseModel, Field

from pm_agent.models import DocumentPlanStatus, DocumentStatus, ProjectStatus


class ProjectCreate(BaseModel):
    name: str
    background: str
    requirements: str
    start_date: date | None = None
    end_date: date | None = None
    tasks: list[str] = Field(default_factory=list)
    selected_document_codes: list[str] | None = None


class ProjectRead(BaseModel):
    id: int
    name: str
    background: str
    requirements: str
    start_date: date | None
    end_date: date | None
    status: ProjectStatus
    created_at: datetime


class PhaseRead(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    order_index: int


class TaskRead(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    granularity: str
    status: str


class TaskCreate(BaseModel):
    project_id: int
    title: str
    description: str = ""
    granularity: str = "feature"
    owner: str | None = None
    status: str = "todo"


class RoleRead(BaseModel):
    id: int
    project_id: int
    role_type: str
    name: str
    responsibility: str
    agent_prompt: str


class TemplateCreate(BaseModel):
    project_id: int | None = None
    phase_id: int | None = None
    name: str
    description: str = ""
    outline_md: str
    is_periodic: bool = False
    period_type: str | None = None


class TemplateRead(BaseModel):
    id: int
    project_id: int | None
    phase_id: int | None
    name: str
    description: str
    outline_md: str
    is_periodic: bool
    period_type: str | None


class CatalogItemRead(BaseModel):
    id: int
    code: str
    lifecycle_template: str
    phase_name: str | None
    name: str
    description: str
    outline_md: str
    default_role_type: str
    is_periodic: bool
    period_type: str | None
    default_selected: bool
    sort_order: int
    dependency_codes: list[str]


class ProjectDocumentPlanRead(BaseModel):
    id: int
    project_id: int
    phase_id: int | None
    catalog_item_id: int
    role_id: int | None
    code: str
    title: str
    description: str
    outline_md: str
    status: DocumentPlanStatus
    is_enabled: bool
    is_periodic: bool
    period_type: str | None
    sort_order: int
    dependency_codes: list[str]


class GenerateDocumentRequest(BaseModel):
    plan_id: int | None = None
    template_id: int | None = None
    extra_instruction: str = ""


class GenerationPreviewRead(BaseModel):
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


class DocumentRead(BaseModel):
    id: int
    project_id: int
    phase_id: int | None
    plan_id: int | None
    template_id: int | None
    title: str
    status: DocumentStatus
    content_md: str
    file_path: str | None
    source_document_ids: list[int]
    created_at: datetime
    updated_at: datetime


class DocumentVersionRead(BaseModel):
    id: int
    document_id: int
    version_number: int
    content_md: str
    change_summary: str
    prompt_snapshot: str
    context_snapshot: str
    created_by_role_id: int | None
    created_at: datetime


class ReportingWindowCreate(BaseModel):
    project_id: int
    name: str
    window_type: str = "weekly"
    start_date: date
    end_date: date
    phase_id: int | None = None


class ReportingWindowRead(BaseModel):
    id: int
    project_id: int
    name: str
    window_type: str
    start_date: date
    end_date: date
    phase_id: int | None


class TaskArtifactCreate(BaseModel):
    project_id: int
    task_id: int
    window_id: int | None = None
    document_id: int | None = None
    title: str
    artifact_type: str = "note"
    content: str = ""
    created_by_role_id: int | None = None


class TaskArtifactRead(BaseModel):
    id: int
    project_id: int
    task_id: int
    window_id: int | None
    document_id: int | None
    title: str
    artifact_type: str
    content: str
    created_by_role_id: int | None
    created_at: datetime


class WorkRecordCreate(BaseModel):
    project_id: int
    task_id: int | None = None
    phase_id: int | None = None
    window_id: int | None = None
    document_id: int | None = None
    title: str
    record_type: str = "progress"
    content: str = ""
    evidence_uri: str | None = None
    created_by_role_id: int | None = None
    happened_on: date | None = None


class WorkRecordRead(BaseModel):
    id: int
    project_id: int
    task_id: int | None
    phase_id: int | None
    window_id: int | None
    document_id: int | None
    title: str
    record_type: str
    content: str
    evidence_uri: str | None
    created_by_role_id: int | None
    happened_on: date | None
    created_at: datetime
