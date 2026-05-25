import re
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

from app.core.config import get_settings
from app.core.config_loader import load_yaml
from app.models.ee_request import EERequestCreate, Finding, Severity

FEDORA_PYTHON_BOOTSTRAP_COMMAND = "RUN dnf install -y python3 python3-pip && dnf clean all"


class GuardrailValidator:
    def __init__(self) -> None:
        settings = get_settings()
        self.taxonomy = load_yaml(settings.config_dir / "domain-taxonomy.yml")
        self.allowed_images = load_yaml(settings.config_dir / "allowed-base-images.yml")["allowed_base_images"]
        self.guardrails = load_yaml(settings.config_dir / "guardrails.yml")
        self.name_pattern = re.compile(self.guardrails["name_pattern"])
        self.image_tag_pattern = re.compile(self.guardrails["image_tag_pattern"])
        self.collection_domains: dict[str, str] = self.taxonomy.get("collection_domains", {})
        self.domains: dict[str, object] = self.taxonomy.get("domains", {})

    def validate(self, request: EERequestCreate) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._validate_name(request))
        findings.extend(self._validate_image_tag(request))
        findings.extend(self._validate_domain(request))
        findings.extend(self._validate_base_image(request))
        findings.extend(self._validate_ansible_core_base_image_compatibility(request))
        findings.extend(self._validate_collections(request))
        findings.extend(self._validate_dependencies(request))
        findings.extend(self._validate_additional_build_steps(request))
        findings.extend(self._validate_domain_mixing(request))
        return findings

    def _validate_name(self, request: EERequestCreate) -> list[Finding]:
        if self.name_pattern.match(request.ee_name):
            return []
        return [
            Finding(
                severity=Severity.blocker,
                code="EE_NAME_INVALID",
                field="ee_name",
                message="EE name must use lowercase letters, numbers, and hyphens, and be 3-63 characters.",
            )
        ]

    def _validate_image_tag(self, request: EERequestCreate) -> list[Finding]:
        if self.image_tag_pattern.match(request.image_tag):
            return []
        return [
            Finding(
                severity=Severity.blocker,
                code="IMAGE_TAG_INVALID",
                field="image_tag",
                message="Image tag must be a valid container tag.",
            )
        ]

    def _validate_domain(self, request: EERequestCreate) -> list[Finding]:
        if not request.automation_domain:
            return [
                Finding(
                    severity=Severity.blocker,
                    code="DOMAIN_REQUIRED",
                    field="automation_domain",
                    message="Automation domain must be declared.",
                )
            ]
        if request.automation_domain not in self.domains:
            return [
                Finding(
                    severity=Severity.warning,
                    code="CUSTOM_DOMAIN",
                    field="automation_domain",
                    message="Automation domain is custom. Ensure ownership and support boundaries are documented.",
                )
            ]
        return []

    def _validate_base_image(self, request: EERequestCreate) -> list[Finding]:
        if request.base_image in self.allowed_images:
            return []
        if request.custom_base_image and request.override_justification.custom_base_image:
            return [
                Finding(
                    severity=Severity.warning,
                    code="CUSTOM_BASE_IMAGE",
                    field="base_image",
                    message="Custom base image mode is enabled. This image requires platform review before enterprise use.",
                )
            ]
        return [
            Finding(
                severity=Severity.blocker,
                code="BASE_IMAGE_NOT_ALLOWED",
                field="base_image",
                message="Base image must be from the allowed RPM-based list unless custom base image mode has justification.",
            )
        ]

    def _validate_ansible_core_base_image_compatibility(self, request: EERequestCreate) -> list[Finding]:
        if not self._is_python39_rpm_base(request.base_image):
            return []
        try:
            requested_version = Version(request.ansible_core_version)
        except InvalidVersion:
            return [
                Finding(
                    severity=Severity.blocker,
                    code="ANSIBLE_CORE_VERSION_INVALID",
                    field="ansible_core_version",
                    message="ansible-core version must be a valid Python package version.",
                )
            ]
        if requested_version >= Version("2.16.0"):
            return [
                Finding(
                    severity=Severity.blocker,
                    code="ANSIBLE_CORE_BASE_IMAGE_INCOMPATIBLE",
                    field="ansible_core_version",
                    message=(
                        "Rocky Linux 9 and CentOS Stream 9 provide Python 3.9 by default. "
                        "ansible-core 2.16+ is not installable on that Python runtime in this lab. "
                        "Use ansible-core 2.15.13 or choose a reviewed base image with a newer Python runtime."
                    ),
                )
            ]
        return []

    def _is_python39_rpm_base(self, base_image: str) -> bool:
        return base_image in {
            "quay.io/rockylinux/rockylinux:9",
            "quay.io/centos/centos:stream9",
        }

    def _validate_collections(self, request: EERequestCreate) -> list[Finding]:
        findings: list[Finding] = []
        for collection in request.collections:
            if collection.version:
                continue
            if request.allow_unpinned and request.override_justification.allow_unpinned:
                findings.append(
                    Finding(
                        severity=Severity.warning,
                        code="UNPINNED_COLLECTION_ALLOWED",
                        field="collections",
                        message=f"{collection.name} is unpinned by explicit override. This should not be used for production EEs.",
                    )
                )
            else:
                findings.append(
                    Finding(
                        severity=Severity.blocker,
                        code="COLLECTION_VERSION_REQUIRED",
                        field="collections",
                        message=f"{collection.name} must have a pinned version.",
                    )
                )
        return findings

    def _validate_dependencies(self, request: EERequestCreate) -> list[Finding]:
        findings: list[Finding] = []
        blocked_patterns = [item.lower() for item in self.guardrails.get("blocked_secret_patterns", [])]
        exclude_python = request.dependencies_exclude.python
        exclude_system = request.dependencies_exclude.system
        for dependency in [*request.python_dependencies, *request.system_dependencies, *exclude_python, *exclude_system]:
            lowered = dependency.lower()
            if any(pattern in lowered for pattern in blocked_patterns):
                findings.append(
                    Finding(
                        severity=Severity.blocker,
                        code="SECRET_LIKE_DEPENDENCY",
                        message="Dependency values must not contain secret-like names or values.",
                    )
                )
        for dependency in request.python_dependencies:
            try:
                Requirement(dependency)
            except InvalidRequirement:
                findings.append(
                    Finding(
                        severity=Severity.blocker,
                        code="PYTHON_REQUIREMENT_INVALID",
                        field="python_dependencies",
                        message=f"Python dependency '{dependency}' is not valid requirement syntax.",
                    )
                )
        allowed_system_dependencies = set(self.guardrails.get("allowed_system_dependencies", []))
        warn_system_dependencies = set(self.guardrails.get("warn_system_dependencies", []))
        system_dependency_pattern = re.compile(self.guardrails["system_dependency_pattern"])
        for dependency in request.system_dependencies:
            package_name = dependency.split("[", maxsplit=1)[0].strip()
            if not system_dependency_pattern.match(dependency):
                findings.append(
                    Finding(
                        severity=Severity.blocker,
                        code="SYSTEM_REQUIREMENT_INVALID",
                        field="system_dependencies",
                        message=f"System dependency '{dependency}' is not valid safe bindep syntax for this lab.",
                    )
                )
            elif package_name not in allowed_system_dependencies:
                findings.append(
                    Finding(
                        severity=Severity.warning,
                        code="SYSTEM_REQUIREMENT_NOT_ALLOWLISTED",
                        field="system_dependencies",
                        message=f"System dependency '{dependency}' is not in the allowlist and should be reviewed.",
                    )
                )
            elif package_name in warn_system_dependencies:
                findings.append(
                    Finding(
                        severity=Severity.warning,
                        code="SYSTEM_REQUIREMENT_REVIEW",
                        field="system_dependencies",
                        message=f"System dependency '{dependency}' can expand the build toolchain and should be justified.",
                    )
                )
        return findings

    def _validate_additional_build_steps(self, request: EERequestCreate) -> list[Finding]:
        if not request.additional_build_steps:
            return []
        if self._is_platform_managed_fedora_python_bootstrap(request):
            return [
                Finding(
                    severity=Severity.info,
                    code="FEDORA_PYTHON_BOOTSTRAP_ADDED",
                    field="additional_build_steps",
                    message="Platform-managed Fedora Python bootstrap is present for ansible-core 2.16+ compatibility.",
                )
            ]
        if request.override_justification.additional_build_steps:
            return [
                Finding(
                    severity=Severity.warning,
                    code="ADDITIONAL_BUILD_STEPS_REVIEW",
                    field="additional_build_steps",
                    message="Additional build steps are enabled and require platform review before enterprise use.",
                )
            ]
        return [
            Finding(
                severity=Severity.blocker,
                code="ADDITIONAL_BUILD_STEPS_JUSTIFICATION_REQUIRED",
                field="additional_build_steps",
                message="Additional build steps require an explicit justification.",
            )
        ]

    def _is_platform_managed_fedora_python_bootstrap(self, request: EERequestCreate) -> bool:
        prepend_base = request.additional_build_steps.get("prepend_base", [])
        return (
            request.base_image.startswith("registry.fedoraproject.org/fedora:")
            and FEDORA_PYTHON_BOOTSTRAP_COMMAND in prepend_base
            and request.override_justification.additional_build_steps
            == "Platform-managed Fedora Python bootstrap required before ansible-builder can run pip_install."
        )

    def _validate_domain_mixing(self, request: EERequestCreate) -> list[Finding]:
        mapped_domains = {
            self.collection_domains[collection.name]
            for collection in request.collections
            if collection.name in self.collection_domains
        }
        findings: list[Finding] = []
        unknown_collections = [
            collection.name for collection in request.collections if collection.name not in self.collection_domains
        ]
        for collection_name in unknown_collections:
            findings.append(
                Finding(
                    severity=Severity.warning,
                    code="COLLECTION_DOMAIN_UNMAPPED",
                    field="collections",
                    message=f"{collection_name} is not mapped in the domain taxonomy. Add it before production use.",
                )
            )
        if not mapped_domains:
            findings.append(
                Finding(
                    severity=Severity.warning,
                    code="UNKNOWN_COLLECTION_DOMAINS",
                    field="collections",
                    message="No selected collections are mapped in the current domain taxonomy.",
                )
            )
            return findings
        if request.automation_domain in self.domains and request.automation_domain not in mapped_domains:
            findings.append(
                Finding(
                    severity=Severity.warning,
                    code="DOMAIN_DECLARATION_MISMATCH",
                    field="automation_domain",
                    message="Declared automation domain does not match the known domain of selected collections.",
                )
            )
        scope_domains = mapped_domains - {"general"} if len(mapped_domains) > 1 else mapped_domains
        if len(scope_domains) > self.guardrails.get("max_domains_without_warning", 1):
            severity = Severity.warning
            if not request.override_justification.broad_domain_scope:
                severity = Severity.blocker
            findings.append(
                Finding(
                    severity=severity,
                    code="DISCONNECTED_DOMAINS",
                    field="collections",
                    message=(
                        "This EE appears to combine multiple disconnected automation domains. "
                        "In enterprise environments, this can increase dependency conflict risk and reduce maintainability."
                    ),
                )
            )
        if len(request.collections) > self.guardrails.get("max_collections_without_warning", 4):
            findings.append(
                Finding(
                    severity=Severity.warning,
                    code="EXCESSIVE_EE_SCOPE",
                    field="collections",
                    message="This request contains many collections. Consider splitting into smaller purpose-driven EEs.",
                )
            )
        return findings
