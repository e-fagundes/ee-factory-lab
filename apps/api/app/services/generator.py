import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from packaging.version import InvalidVersion, Version

from app.core.config import get_settings
from app.models.ee_request import CompatibilityReport, EERequestRecord, Finding, Severity, VulnerabilityReport
from app.repositories.local_store import LocalStore


FEDORA_PYTHON_BOOTSTRAP_COMMAND = "RUN dnf install -y python3 python3-pip && dnf clean all"


class EEFileGenerator:
    def __init__(self, store: LocalStore | None = None) -> None:
        self.settings = get_settings()
        self.store = store or LocalStore()
        self.env = Environment(
            loader=FileSystemLoader(self.settings.template_dir),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(
        self,
        record: EERequestRecord,
        report: CompatibilityReport,
        vulnerability_report: VulnerabilityReport | None = None,
    ) -> dict[str, str]:
        self._apply_platform_managed_build_steps(record, report)
        context = {"request": record, "report": report, "vulnerability_report": vulnerability_report}
        rendered = {
            "execution-environment.yml": self._render("execution-environment.yml.j2", context),
            "requirements.yml": self._render("requirements.yml.j2", context),
            "requirements.txt": self._render("requirements.txt.j2", context),
            "bindep.txt": self._render("bindep.txt.j2", context),
            "compatibility-report.md": report.markdown,
            "compatibility-report.json": report.model_dump_json(indent=2),
            "generated-readme.md": self._render("generated-readme.md.j2", context),
            "manifest.json": self._manifest(record, report),
        }
        if vulnerability_report:
            rendered["vulnerability-report.md"] = vulnerability_report.markdown
            rendered["vulnerability-report.json"] = vulnerability_report.model_dump_json(indent=2)
        paths: dict[str, str] = {}
        for name, content in rendered.items():
            path = self.store.write_text(record.id, name, content)
            paths[name] = str(path)
        record.generated_files = paths
        record.compatibility_findings = report.findings
        record.compatibility_report_path = paths["compatibility-report.md"]
        record.generated_documentation_path = paths["generated-readme.md"]
        if vulnerability_report:
            record.vulnerability_findings = vulnerability_report.findings
            record.vulnerability_report_path = paths["vulnerability-report.md"]
        record.status = "GENERATED"
        self.store.save_record(record)
        return rendered

    def _render(self, template_name: str, context: dict[str, object]) -> str:
        return self.env.get_template(template_name).render(**context)

    def _apply_platform_managed_build_steps(
        self,
        record: EERequestRecord,
        report: CompatibilityReport,
    ) -> None:
        if not self._requires_fedora_python_bootstrap(record):
            return
        prepend_base = list(record.additional_build_steps.get("prepend_base", []))
        if FEDORA_PYTHON_BOOTSTRAP_COMMAND not in prepend_base:
            record.additional_build_steps = {
                **record.additional_build_steps,
                "prepend_base": [FEDORA_PYTHON_BOOTSTRAP_COMMAND, *prepend_base],
            }
        record.override_justification.additional_build_steps = (
            "Platform-managed Fedora Python bootstrap required before ansible-builder can run pip_install."
        )
        finding = Finding(
            severity=Severity.info,
            code="FEDORA_PYTHON_BOOTSTRAP_ADDED",
            field="base_image",
            message=(
                "Fedora base images do not guarantee /usr/bin/python3 in the initial container layer. "
                "A platform-managed prepend_base step installs python3 and python3-pip before ansible-builder pip_install."
            ),
        )
        if not any(existing.code == finding.code for existing in report.findings):
            report.findings.append(finding)
            report.markdown += (
                "\n## Platform Build Steps\n\n"
                "- INFO: `FEDORA_PYTHON_BOOTSTRAP_ADDED` - "
                f"{finding.message}\n"
            )

    def _requires_fedora_python_bootstrap(self, record: EERequestRecord) -> bool:
        if not record.base_image.startswith("registry.fedoraproject.org/fedora:"):
            return False
        try:
            return Version(record.ansible_core_version) >= Version("2.16.0")
        except InvalidVersion:
            return False

    def _manifest(self, record: EERequestRecord, report: CompatibilityReport) -> str:
        payload = {
            "request_id": record.id,
            "ee_name": record.ee_name,
            "image": f"{record.publish_target}/{record.registry_namespace}/{record.ee_name}:{record.image_tag}",
            "automation_domain": record.automation_domain,
            "base_image": record.base_image,
            "ansible_core_version": record.ansible_core_version,
            "ansible_runner_version": record.ansible_runner_version,
            "collections": [collection.model_dump() for collection in record.collections],
            "additional_build_steps": record.additional_build_steps,
            "findings": [finding.model_dump() for finding in report.findings],
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    def list_generated_files(self, record: EERequestRecord) -> dict[str, str]:
        files: dict[str, str] = {}
        for name in record.generated_files:
            path = Path(record.generated_files[name])
            files[name] = path.read_text(encoding="utf-8")
        return files
