from fastapi import HTTPException

from app.builders.kubernetes_builder import KubernetesBuildOrchestrator
from app.compatibility.advisor import CompatibilityAdvisor
from app.guardrails.validator import GuardrailValidator
from app.models.ee_request import (
    BuildMode,
    BuildRequest,
    CompatibilityReport,
    EERequestCreate,
    EERequestRecord,
    Finding,
    NewVersionRequest,
    Severity,
)
from app.repositories.local_store import LocalStore
from app.security.vulnerability_advisor import VulnerabilityAdvisor
from app.services.documentation_service import DocumentationService
from app.services.generator import EEFileGenerator


class EERequestService:
    def __init__(self) -> None:
        self.store = LocalStore()
        self.validator = GuardrailValidator()
        self.advisor = CompatibilityAdvisor()
        self.vulnerability_advisor = VulnerabilityAdvisor()
        self.generator = EEFileGenerator(self.store)
        self.documentation = DocumentationService(self.store)
        self.build_orchestrator = KubernetesBuildOrchestrator()

    def create(self, payload: EERequestCreate) -> EERequestRecord:
        record = self.store.create_request(payload)
        findings = self.validator.validate(payload)
        record.validation_findings = findings
        record.status = "VALIDATION_BLOCKED" if self._has_blockers(findings) else "VALIDATED"
        self.store.save_record(record)
        self.store.write_json(record.id, "logs/validation.log", [finding.model_dump() for finding in findings])
        return record

    def list_requests(self) -> list[EERequestRecord]:
        return self.store.list_requests()

    def get(self, request_id: str) -> EERequestRecord:
        try:
            return self.store.get_request(request_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="EE request not found") from exc

    def validate(self, request_id: str) -> list[Finding]:
        record = self.get(request_id)
        findings = self.validator.validate(EERequestCreate.model_validate(record.model_dump()))
        record.validation_findings = findings
        record.status = "VALIDATION_BLOCKED" if self._has_blockers(findings) else "VALIDATED"
        self.store.save_record(record)
        return findings

    def compatibility_report(self, request_id: str) -> CompatibilityReport:
        record = self.get(request_id)
        return self.advisor.analyze(
            request_id,
            EERequestCreate.model_validate(record.model_dump()),
            record.validation_findings,
        )

    def vulnerability_report(self, request_id: str):
        record = self.get(request_id)
        report = self.vulnerability_advisor.analyze(
            request_id,
            EERequestCreate.model_validate(record.model_dump()),
        )
        record.vulnerability_findings = report.findings
        self.store.write_text(request_id, "vulnerability-report.md", report.markdown)
        path = self.store.write_text(request_id, "vulnerability-report.json", report.model_dump_json(indent=2))
        record.vulnerability_report_path = str(path)
        self.store.save_record(record)
        return report

    def generate(self, request_id: str) -> dict[str, str]:
        record = self.get(request_id)
        findings = self.validator.validate(EERequestCreate.model_validate(record.model_dump()))
        if self._has_blockers(findings):
            record.validation_findings = findings
            record.status = "VALIDATION_BLOCKED"
            self.store.save_record(record)
            raise HTTPException(status_code=422, detail=[finding.model_dump() for finding in findings])
        request_model = EERequestCreate.model_validate(record.model_dump())
        report = self.advisor.analyze(request_id, request_model, findings)
        vulnerability_report = self.vulnerability_advisor.analyze(request_id, request_model)
        if self._has_blockers(vulnerability_report.findings):
            record.vulnerability_findings = vulnerability_report.findings
            record.status = "VULNERABILITY_BLOCKED"
            self.store.save_record(record)
            raise HTTPException(status_code=422, detail=[finding.model_dump() for finding in vulnerability_report.findings])
        return self.generator.generate(record, report, vulnerability_report)

    def generated_files(self, request_id: str) -> dict[str, str]:
        record = self.get(request_id)
        if not record.generated_files:
            raise HTTPException(status_code=404, detail="Generated files are not available yet")
        return self.generator.list_generated_files(record)

    def create_new_version(self, request_id: str, payload: NewVersionRequest) -> EERequestRecord:
        source = self.get(request_id)
        clone_payload = EERequestCreate.model_validate(source.model_dump()).model_copy(
            update={
                "image_tag": payload.image_tag,
                "change_summary": payload.change_summary,
                "parent_request_id": source.id,
                "source": "IDP_VERSION",
            }
        )
        return self.create(clone_payload)

    def build(self, request_id: str, payload: BuildRequest) -> dict[str, object]:
        record = self.get(request_id)
        if record.approval_status != "GENERATED_FILES_APPROVED":
            raise HTTPException(status_code=409, detail="Approve generated files before building")
        if not record.generated_files:
            raise HTTPException(status_code=409, detail="Generate files before building")
        if self.store.exists(request_id, "build-result.json") and payload.mode != BuildMode.publish_after_approval:
            current_status = self.build_status(request_id)
            return {
                "request_id": request_id,
                "status": current_status["build_status"],
                "job_name": current_status["job_name"],
                "submitted": False,
                "already_exists": True,
                "message": (
                    "Build metadata already exists for this request. Use Refresh build status to view the result, "
                    "or create a new tagged version before rebuilding."
                ),
            }

        result = self.build_orchestrator.submit_job(record, payload.mode)
        self.store.write_json(record.id, "builder-job.json", result["manifest"])
        record.build_job_name = str(result["job_name"])
        if result.get("already_exists"):
            record.build_status = "JOB_ALREADY_EXISTS"
            if record.status not in {"BUILT", "PUBLISHED"}:
                record.status = "BUILD_QUEUED"
        else:
            record.build_status = "JOB_CREATED" if result["submitted"] else "JOB_SPEC_GENERATED"
            record.status = "BUILD_QUEUED" if result["submitted"] else "BUILD_JOB_SPEC_GENERATED"
        self.store.save_record(record)
        return {
            "request_id": request_id,
            "status": record.build_status,
            "job_name": record.build_job_name,
            "submitted": result["submitted"],
            "already_exists": result.get("already_exists", False),
            "message": result["message"],
        }

    def build_status(self, request_id: str) -> dict[str, object]:
        record = self.get(request_id)
        result: object | None = None
        if self.store.exists(request_id, "build-result.json"):
            result = self.store.read_json(request_id, "build-result.json")
            if isinstance(result, dict):
                status = str(result.get("status", record.status))
                record.status = status
                record.build_status = status
                metadata = result.get("metadata")
                if isinstance(metadata, dict):
                    digest = metadata.get("digest")
                    if isinstance(digest, str):
                        record.image_digest = digest
                if status == "PUBLISHED":
                    record.publish_status = "PUBLISHED"
                self.store.save_record(record)
        return {
            "request_id": request_id,
            "status": record.status,
            "build_status": record.build_status,
            "publish_status": record.publish_status,
            "image_digest": record.image_digest,
            "job_name": record.build_job_name,
            "result": result,
        }

    def approve_publish(self, request_id: str) -> EERequestRecord:
        record = self.get(request_id)
        record.status = "PUBLISH_APPROVED"
        record.publish_status = "PUBLISH_APPROVED"
        self.store.save_record(record)
        return record

    def publish(self, request_id: str) -> dict[str, object]:
        record = self.get(request_id)
        if record.publish_status != "PUBLISH_APPROVED":
            raise HTTPException(status_code=409, detail="Approve publish before pushing to registry")
        return self.build(request_id, BuildRequest(mode=BuildMode.publish_after_approval, use_kubernetes=True))

    def generate_docs(self, request_id: str) -> str:
        record = self.get(request_id)
        return self.documentation.generate(record)

    def _has_blockers(self, findings: list[Finding]) -> bool:
        return any(finding.severity == Severity.blocker for finding in findings)
