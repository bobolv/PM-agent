from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class ProjectStatus(StrEnum):
    active = "active"
    archived = "archived"


class DocumentStatus(StrEnum):
    draft = "draft"
    generated = "generated"
    approved = "approved"


class DocumentPlanStatus(StrEnum):
    planned = "planned"
    skipped = "skipped"
    in_progress = "in_progress"
    generated = "generated"
    approved = "approved"


class RoleType(StrEnum):
    project_owner = "project_owner"
    project_manager = "project_manager"
    development_manager = "development_manager"
    developer = "developer"
    test_engineer = "test_engineer"
    operations_engineer = "operations_engineer"
    researcher = "researcher"


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    background: str
    requirements: str
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus = ProjectStatus.active
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectTask(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    title: str
    description: str = ""
    granularity: str = "feature"
    owner: str | None = None
    status: str = "todo"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectRole(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    role_type: RoleType
    name: str
    responsibility: str = ""
    agent_prompt: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LifecyclePhase(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    name: str
    description: str = ""
    order_index: int
    start_date: date | None = None
    end_date: date | None = None


class DocumentTemplate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(default=None, index=True, foreign_key="project.id")
    phase_id: int | None = Field(default=None, index=True, foreign_key="lifecyclephase.id")
    name: str
    description: str = ""
    outline_md: str
    is_periodic: bool = False
    period_type: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentCatalogItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    lifecycle_template: str = Field(default="standard", index=True)
    phase_name: str | None = Field(default=None, index=True)
    name: str
    description: str = ""
    outline_md: str
    default_role_type: RoleType = RoleType.project_manager
    is_periodic: bool = False
    period_type: str | None = None
    default_selected: bool = True
    sort_order: int = 0
    dependency_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    template_file_path: str | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectDocumentPlan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    phase_id: int | None = Field(default=None, index=True, foreign_key="lifecyclephase.id")
    catalog_item_id: int = Field(index=True, foreign_key="documentcatalogitem.id")
    role_id: int | None = Field(default=None, index=True, foreign_key="projectrole.id")
    code: str = Field(index=True)
    title: str
    description: str = ""
    outline_md: str
    status: DocumentPlanStatus = DocumentPlanStatus.planned
    is_enabled: bool = True
    is_periodic: bool = False
    period_type: str | None = None
    sort_order: int = 0
    dependency_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentRoleAssignment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    template_id: int = Field(index=True, foreign_key="documenttemplate.id")
    role_id: int = Field(index=True, foreign_key="projectrole.id")


class ProjectDocument(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    phase_id: int | None = Field(default=None, index=True, foreign_key="lifecyclephase.id")
    plan_id: int | None = Field(default=None, index=True, foreign_key="projectdocumentplan.id")
    template_id: int | None = Field(default=None, index=True, foreign_key="documenttemplate.id")
    title: str
    status: DocumentStatus = DocumentStatus.draft
    content_md: str = ""
    file_path: str | None = None
    source_document_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectDocumentVersion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(index=True, foreign_key="projectdocument.id")
    version_number: int
    content_md: str
    change_summary: str = ""
    prompt_snapshot: str = ""
    context_snapshot: str = ""
    created_by_role_id: int | None = Field(default=None, index=True, foreign_key="projectrole.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReportingWindow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    name: str
    window_type: str = "weekly"
    start_date: date
    end_date: date
    phase_id: int | None = Field(default=None, index=True, foreign_key="lifecyclephase.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskArtifact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    task_id: int = Field(index=True, foreign_key="projecttask.id")
    window_id: int | None = Field(default=None, index=True, foreign_key="reportingwindow.id")
    document_id: int | None = Field(default=None, index=True, foreign_key="projectdocument.id")
    title: str
    artifact_type: str = "note"
    content: str = ""
    created_by_role_id: int | None = Field(default=None, index=True, foreign_key="projectrole.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorkRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    task_id: int | None = Field(default=None, index=True, foreign_key="projecttask.id")
    phase_id: int | None = Field(default=None, index=True, foreign_key="lifecyclephase.id")
    window_id: int | None = Field(default=None, index=True, foreign_key="reportingwindow.id")
    document_id: int | None = Field(default=None, index=True, foreign_key="projectdocument.id")
    title: str
    record_type: str = "progress"
    content: str = ""
    evidence_uri: str | None = None
    created_by_role_id: int | None = Field(default=None, index=True, foreign_key="projectrole.id")
    happened_on: date | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentGenerationRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    template_id: int | None = Field(default=None, index=True, foreign_key="documenttemplate.id")
    plan_id: int | None = Field(default=None, index=True, foreign_key="projectdocumentplan.id")
    document_id: int | None = Field(default=None, index=True, foreign_key="projectdocument.id")
    role_id: int | None = Field(default=None, index=True, foreign_key="projectrole.id")
    prompt: str
    context_md: str
    source_document_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    source_artifact_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    source_work_record_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
