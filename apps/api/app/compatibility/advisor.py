import tarfile
import tempfile
from pathlib import Path
from shutil import which
from subprocess import run

import yaml
from packaging.requirements import InvalidRequirement, Requirement

from app.core.config import get_settings
from app.core.config_loader import load_yaml
from app.models.ee_request import CompatibilityReport, EERequestCreate, Finding, Severity


class CompatibilityAdvisor:
    def __init__(self) -> None:
        settings = get_settings()
        taxonomy = load_yaml(settings.config_dir / "domain-taxonomy.yml")
        self.collection_domains: dict[str, str] = taxonomy.get("collection_domains", {})

    def analyze(self, request_id: str, request: EERequestCreate, guardrail_findings: list[Finding]) -> CompatibilityReport:
        mapped = {
            collection.name: self.collection_domains.get(collection.name, "unknown")
            for collection in request.collections
        }
        findings = list(guardrail_findings)
        resolution_metadata = self._resolve_collection_metadata(request)
        findings.extend(resolution_metadata["findings"])
        findings.extend(self._detect_python_constraint_conflicts(request, resolution_metadata["python_requirements"]))
        unknown = [name for name, domain in mapped.items() if domain == "unknown"]
        if unknown:
            findings.append(
                Finding(
                    severity=Severity.info,
                    code="COLLECTION_METADATA_NOT_RESOLVED",
                    field="collections",
                    message="Some collections are not in the local taxonomy: " + ", ".join(unknown),
                )
            )
        markdown = self._to_markdown(request, findings, mapped, resolution_metadata)
        return CompatibilityReport(
            request_id=request_id,
            findings=findings,
            collection_domains=mapped,
            markdown=markdown,
            metadata={
                "mode": "taxonomy-plus-best-effort-metadata",
                "collection_resolution": resolution_metadata,
            },
        )

    def _resolve_collection_metadata(self, request: EERequestCreate) -> dict[str, object]:
        metadata: dict[str, object] = {
            "enabled": True,
            "tool": "ansible-galaxy",
            "available": False,
            "python_requirements": [],
            "system_requirements": [],
            "findings": [],
        }
        ansible_galaxy = which("ansible-galaxy")
        if not ansible_galaxy:
            metadata["findings"] = [
                Finding(
                    severity=Severity.info,
                    code="COLLECTION_METADATA_RESOLUTION_SKIPPED",
                    field="collections",
                    message="ansible-galaxy is not installed in the API runtime, so collection package metadata was not downloaded.",
                )
            ]
            return metadata

        metadata["available"] = True
        with tempfile.TemporaryDirectory(prefix="ee-factory-collections-") as temporary_dir:
            temp_path = Path(temporary_dir)
            requirements_path = temp_path / "requirements.yml"
            download_dir = temp_path / "downloads"
            download_dir.mkdir(parents=True, exist_ok=True)
            requirements_path.write_text(
                yaml.safe_dump(
                    {
                        "collections": [
                            {"name": collection.name, "version": collection.version}
                            for collection in request.collections
                        ]
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            command = [
                ansible_galaxy,
                "collection",
                "download",
                "-r",
                str(requirements_path),
                "-p",
                str(download_dir),
            ]
            result = run(command, capture_output=True, text=True, timeout=120, check=False)
            metadata["command"] = ["ansible-galaxy", "collection", "download", "-r", "requirements.yml", "-p", "downloads"]
            metadata["returncode"] = result.returncode
            metadata["stdout_tail"] = result.stdout[-4000:]
            metadata["stderr_tail"] = result.stderr[-4000:]
            if result.returncode != 0:
                metadata["findings"] = [
                    Finding(
                        severity=Severity.warning,
                        code="COLLECTION_METADATA_RESOLUTION_FAILED",
                        field="collections",
                        message="ansible-galaxy could not download selected collections for metadata inspection.",
                    )
                ]
                return metadata

            python_requirements: list[str] = []
            system_requirements: list[str] = []
            for tarball in download_dir.glob("*.tar.gz"):
                extracted = self._read_collection_dependency_files(tarball)
                python_requirements.extend(extracted["python"])
                system_requirements.extend(extracted["system"])

            metadata["python_requirements"] = python_requirements
            metadata["system_requirements"] = system_requirements
            metadata["findings"] = [
                Finding(
                    severity=Severity.info,
                    code="COLLECTION_METADATA_RESOLVED",
                    field="collections",
                    message="Selected collections were downloaded to a temporary workspace for dependency metadata inspection.",
                )
            ]
            return metadata

    def _read_collection_dependency_files(self, tarball: Path) -> dict[str, list[str]]:
        dependencies: dict[str, list[str]] = {"python": [], "system": []}
        with tarfile.open(tarball, mode="r:gz") as archive:
            for member in archive.getmembers():
                member_name = member.name.lower()
                if not member.isfile():
                    continue
                if member_name.endswith("/requirements.txt") or member_name == "requirements.txt":
                    dependencies["python"].extend(self._read_tar_text_lines(archive, member))
                if member_name.endswith("/bindep.txt") or member_name == "bindep.txt":
                    dependencies["system"].extend(self._read_tar_text_lines(archive, member))
        return dependencies

    def _read_tar_text_lines(self, archive: tarfile.TarFile, member: tarfile.TarInfo) -> list[str]:
        file_object = archive.extractfile(member)
        if file_object is None:
            return []
        return [
            line.strip()
            for line in file_object.read().decode("utf-8", errors="ignore").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def _detect_python_constraint_conflicts(
        self,
        request: EERequestCreate,
        collection_python_requirements: object,
    ) -> list[Finding]:
        requirements = list(request.python_dependencies)
        if isinstance(collection_python_requirements, list):
            requirements.extend([str(item) for item in collection_python_requirements])

        exact_versions: dict[str, set[str]] = {}
        for dependency in requirements:
            try:
                parsed = Requirement(dependency)
            except InvalidRequirement:
                continue
            exact = {specifier.version for specifier in parsed.specifier if specifier.operator == "=="}
            if exact:
                exact_versions.setdefault(parsed.name.lower(), set()).update(exact)

        findings: list[Finding] = []
        for package_name, versions in exact_versions.items():
            if len(versions) > 1:
                findings.append(
                    Finding(
                        severity=Severity.warning,
                        code="PYTHON_EXACT_VERSION_CONFLICT",
                        field="python_dependencies",
                        message=(
                            f"Package {package_name} has multiple exact version constraints: "
                            + ", ".join(sorted(versions))
                        ),
                    )
                )
        return findings

    def _to_markdown(
        self,
        request: EERequestCreate,
        findings: list[Finding],
        mapped: dict[str, str],
        resolution_metadata: dict[str, object],
    ) -> str:
        lines = [
            f"# Compatibility Report: {request.ee_name}",
            "",
            "This report is produced by deterministic guardrails, domain taxonomy, and best-effort collection metadata inspection.",
            "",
            "## Declared Scope",
            "",
            f"- Domain: `{request.automation_domain}`",
            f"- Base image: `{request.base_image}`",
            f"- Image tag: `{request.image_tag}`",
            "",
            "## Collection Domains",
            "",
        ]
        for name, domain in mapped.items():
            lines.append(f"- `{name}` -> `{domain}`")
        lines.extend(["", "## Collection Metadata", ""])
        if resolution_metadata.get("available"):
            lines.append("- ansible-galaxy was available for temporary collection download.")
            python_requirements = resolution_metadata.get("python_requirements", [])
            system_requirements = resolution_metadata.get("system_requirements", [])
            lines.append(f"- Python requirements discovered: `{len(python_requirements)}`")
            lines.append(f"- System requirements discovered: `{len(system_requirements)}`")
        else:
            lines.append("- ansible-galaxy was not available, so metadata resolution used taxonomy-only mode.")
        lines.extend(["", "## Findings", ""])
        if not findings:
            lines.append("- INFO: No guardrail findings.")
        for finding in findings:
            lines.append(f"- {finding.severity}: `{finding.code}` - {finding.message}")
        lines.extend(
            [
                "",
                "## Recommendation",
                "",
                "Keep the EE focused on one automation domain unless a single workflow genuinely requires the combined dependencies.",
                "When domains are disconnected, create a new tagged request per EE and publish separate images after approval.",
            ]
        )
        return "\n".join(lines) + "\n"
