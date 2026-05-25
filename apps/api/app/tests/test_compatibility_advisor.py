from app.compatibility.advisor import CompatibilityAdvisor
from app.models.ee_request import AnsibleCollection, EERequestCreate


def request_with_dependencies() -> EERequestCreate:
    return EERequestCreate(
        ee_name="ee-postgresql-admin",
        description="PostgreSQL automation",
        purpose="Manage PostgreSQL databases and users",
        automation_domain="database",
        base_image="quay.io/rockylinux/rockylinux:9",
        ansible_core_version="2.15.13",
        ansible_runner_version="2.4.0",
        collections=[AnsibleCollection(name="community.postgresql", version="3.14.0")],
        python_dependencies=["psycopg2-binary==2.9.10", "requests==2.31.0"],
        system_dependencies=[],
        image_tag="0.1.0",
        registry_namespace="example-platform",
        publish_target="quay.io",
    )


def test_detects_duplicate_python_packages_with_conflicting_exact_versions(monkeypatch):
    advisor = CompatibilityAdvisor()

    monkeypatch.setattr(
        advisor,
        "_resolve_collection_metadata",
        lambda request: {
            "enabled": True,
            "tool": "ansible-galaxy",
            "available": True,
            "python_requirements": ["requests==2.32.0"],
            "system_requirements": [],
            "findings": [],
        },
    )

    report = advisor.analyze("request-id", request_with_dependencies(), [])

    assert any(finding.code == "PYTHON_EXACT_VERSION_CONFLICT" for finding in report.findings)
