from app.guardrails.validator import GuardrailValidator
from app.models.ee_request import AnsibleCollection, EERequestCreate, Severity


def make_request(**overrides):
    payload = {
        "ee_name": "ee-ansible-windows",
        "description": "Windows automation",
        "purpose": "Run Windows automation",
        "automation_domain": "windows",
        "base_image": "quay.io/rockylinux/rockylinux:9",
        "ansible_core_version": "2.15.13",
        "ansible_runner_version": "2.4.0",
        "collections": [
            AnsibleCollection(name="ansible.windows", version="2.5.0"),
            AnsibleCollection(name="community.windows", version="2.3.0"),
        ],
        "python_dependencies": ["pywinrm==0.5.0"],
        "system_dependencies": [],
        "image_tag": "0.1.0",
        "registry_namespace": "example-platform",
        "publish_target": "quay.io",
    }
    payload.update(overrides)
    return EERequestCreate(**payload)


def test_valid_windows_request_has_no_blockers():
    findings = GuardrailValidator().validate(make_request())
    assert not [finding for finding in findings if finding.severity == Severity.blocker]


def test_unpinned_collection_is_blocked():
    request = make_request(collections=[AnsibleCollection(name="ansible.windows")])
    findings = GuardrailValidator().validate(request)
    assert any(finding.code == "COLLECTION_VERSION_REQUIRED" for finding in findings)


def test_disconnected_domain_mixing_is_blocked_without_justification():
    request = make_request(
        collections=[
            AnsibleCollection(name="ansible.windows", version="2.5.0"),
            AnsibleCollection(name="community.vmware", version="5.7.2"),
        ]
    )
    findings = GuardrailValidator().validate(request)
    assert any(finding.code == "DISCONNECTED_DOMAINS" and finding.severity == Severity.blocker for finding in findings)


def test_multiple_disconnected_domains_are_blocked_without_justification():
    request = make_request(
        collections=[
            AnsibleCollection(name="ansible.windows", version="2.5.0"),
            AnsibleCollection(name="community.vmware", version="5.7.2"),
            AnsibleCollection(name="kubernetes.core", version="6.4.0"),
            AnsibleCollection(name="servicenow.itsm", version="2.10.0"),
        ]
    )
    findings = GuardrailValidator().validate(request)
    assert any(finding.code == "DISCONNECTED_DOMAINS" and finding.severity == Severity.blocker for finding in findings)


def test_postgresql_collection_maps_to_database_domain():
    request = make_request(
        ee_name="ee-postgresql-admin",
        automation_domain="database",
        collections=[AnsibleCollection(name="community.postgresql", version="3.14.0")],
        python_dependencies=["psycopg2-binary==2.9.10"],
    )
    findings = GuardrailValidator().validate(request)
    assert not any(finding.code in {"COLLECTION_DOMAIN_UNMAPPED", "UNKNOWN_COLLECTION_DOMAINS"} for finding in findings)


def test_general_collection_can_support_specific_domain_without_disconnected_blocker():
    request = make_request(
        ee_name="ee-postgresql-toolkit",
        automation_domain="database",
        collections=[
            AnsibleCollection(name="community.postgresql", version="3.14.0"),
            AnsibleCollection(name="community.general", version="11.4.0"),
        ],
        python_dependencies=["psycopg2-binary==2.9.10", "requests==2.31.0"],
        system_dependencies=["postgresql"],
    )
    findings = GuardrailValidator().validate(request)
    assert not any(finding.code == "DISCONNECTED_DOMAINS" for finding in findings)
    assert not any(finding.code == "SYSTEM_REQUIREMENT_NOT_ALLOWLISTED" for finding in findings)


def test_invalid_python_requirement_is_blocked():
    request = make_request(python_dependencies=["psycopg2-binary===not valid"])
    findings = GuardrailValidator().validate(request)
    assert any(finding.code == "PYTHON_REQUIREMENT_INVALID" and finding.severity == Severity.blocker for finding in findings)


def test_ansible_core_216_is_blocked_on_python39_rpm_base():
    request = make_request(ansible_core_version="2.16.14")
    findings = GuardrailValidator().validate(request)
    assert any(
        finding.code == "ANSIBLE_CORE_BASE_IMAGE_INCOMPATIBLE" and finding.severity == Severity.blocker
        for finding in findings
    )


def test_platform_managed_fedora_python_bootstrap_is_allowed():
    request = make_request(
        ee_name="ee-aap-config-as-code",
        automation_domain="aap-config-as-code",
        base_image="registry.fedoraproject.org/fedora:43",
        ansible_core_version="2.16.18",
        collections=[AnsibleCollection(name="infra.aap_configuration", version="4.5.0")],
        python_dependencies=["awxkit==24.6.1"],
        additional_build_steps={
            "prepend_base": ["RUN dnf install -y python3 python3-pip && dnf clean all"],
        },
    )
    request.override_justification.additional_build_steps = (
        "Platform-managed Fedora Python bootstrap required before ansible-builder can run pip_install."
    )

    findings = GuardrailValidator().validate(request)

    assert not any(finding.code == "ADDITIONAL_BUILD_STEPS_JUSTIFICATION_REQUIRED" for finding in findings)
    assert any(finding.code == "FEDORA_PYTHON_BOOTSTRAP_ADDED" for finding in findings)
