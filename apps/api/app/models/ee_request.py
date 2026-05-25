from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Severity(StrEnum):
    blocker = "BLOCKER"
    warning = "WARNING"
    info = "INFO"


class Finding(BaseModel):
    severity: Severity
    code: str
    message: str
    field: str | None = None


class AnsibleCollection(BaseModel):
    name: str = Field(min_length=3)
    version: str | None = None


class OverrideJustification(BaseModel):
    allow_unpinned: str | None = None
    custom_base_image: str | None = None
    broad_domain_scope: str | None = None
    additional_build_steps: str | None = None


class DependencyExcludes(BaseModel):
    python: list[str] = Field(default_factory=list)
    system: list[str] = Field(default_factory=list)


class EERequestCreate(BaseModel):
    ee_name: str
    description: str
    purpose: str
    automation_domain: str
    base_image: str = "quay.io/rockylinux/rockylinux:9"
    ansible_core_version: str = "2.15.13"
    ansible_runner_version: str = "2.4.0"
    collections: list[AnsibleCollection]
    python_dependencies: list[str] = Field(default_factory=list)
    system_dependencies: list[str] = Field(default_factory=list)
    dependencies_exclude: DependencyExcludes = Field(default_factory=DependencyExcludes)
    additional_build_steps: dict[str, list[str]] = Field(default_factory=dict)
    image_tag: str = "0.1.0"
    registry_namespace: str
    publish_target: str = "quay.io"
    source: str = "PORTAL"
    change_summary: str | None = None
    parent_request_id: str | None = None
    allow_unpinned: bool = False
    custom_base_image: bool = False
    override_justification: OverrideJustification = Field(default_factory=OverrideJustification)

    @field_validator("collections")
    @classmethod
    def require_collection(cls, value: list[AnsibleCollection]) -> list[AnsibleCollection]:
        if not value:
            raise ValueError("At least one collection is required")
        return value


class EERequestRecord(EERequestCreate):
    id: str
    pipeline_run_id: str | None = None
    build_job_name: str | None = None
    status: str = "REQUESTED"
    approval_status: str = "PENDING_GENERATED_FILES_APPROVAL"
    build_status: str = "NOT_STARTED"
    publish_status: str = "NOT_REQUESTED"
    validation_findings: list[Finding] = Field(default_factory=list)
    compatibility_findings: list[Finding] = Field(default_factory=list)
    vulnerability_findings: list[Finding] = Field(default_factory=list)
    generated_files: dict[str, str] = Field(default_factory=dict)
    compatibility_report_path: str | None = None
    workspace_path: str | None = None
    registry_target: str | None = None
    image_digest: str | None = None
    validation_log_path: str | None = None
    build_log_path: str | None = None
    publish_log_path: str | None = None
    generated_documentation_path: str | None = None
    vulnerability_report_path: str | None = None
    created_at: str
    updated_at: str


class GeneratedFile(BaseModel):
    name: str
    content: str


class GeneratedFilesResponse(BaseModel):
    request_id: str
    files: list[GeneratedFile]


class CompatibilityReport(BaseModel):
    request_id: str
    findings: list[Finding]
    collection_domains: dict[str, str]
    markdown: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class VulnerabilityReport(BaseModel):
    request_id: str
    findings: list[Finding]
    markdown: str
    scanned_packages: list[dict[str, str]] = Field(default_factory=list)
    vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BuildMode(StrEnum):
    build_only = "build_only"
    stage_for_approval = "stage_for_approval"
    publish_after_approval = "publish_after_approval"


class BuildRequest(BaseModel):
    mode: BuildMode = BuildMode.build_only
    use_kubernetes: bool = True


class NewVersionRequest(BaseModel):
    image_tag: str
    change_summary: str
