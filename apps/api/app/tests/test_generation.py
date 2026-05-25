from app.compatibility.advisor import CompatibilityAdvisor
from app.models.ee_request import AnsibleCollection, EERequestRecord
from app.services.generator import EEFileGenerator


class MemoryStore:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}

    def write_text(self, request_id: str, relative_path: str, content: str):
        self.files[relative_path] = content
        return f"/tmp/{request_id}/{relative_path}"

    def save_record(self, record: EERequestRecord) -> None:
        return None


def test_generator_creates_execution_environment(tmp_path, monkeypatch):
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    record = EERequestRecord(
        id="test-id",
        ee_name="ee-ansible-windows",
        description="Windows automation",
        purpose="Run Windows automation",
        automation_domain="windows",
        base_image="quay.io/rockylinux/rockylinux:9",
        ansible_core_version="2.15.13",
        ansible_runner_version="2.4.0",
        collections=[AnsibleCollection(name="ansible.windows", version="2.5.0")],
        python_dependencies=["pywinrm==0.5.0"],
        system_dependencies=[],
        image_tag="0.1.0",
        registry_namespace="example-platform",
        publish_target="quay.io",
        created_at="2026-05-24T00:00:00Z",
        updated_at="2026-05-24T00:00:00Z",
    )
    report = CompatibilityAdvisor().analyze(record.id, record, [])
    files = EEFileGenerator().generate(record, report)
    assert "version: 3" in files["execution-environment.yml"]
    assert "ansible.windows" in files["requirements.yml"]
    assert "pywinrm==0.5.0" in files["requirements.txt"]


def test_generator_preserves_multiple_collections_and_dependencies():
    record = EERequestRecord(
        id="test-id",
        ee_name="ee-database-observability",
        description="Database and observability automation",
        purpose="Exercise multi-dependency rendering for review",
        automation_domain="database",
        base_image="quay.io/rockylinux/rockylinux:9",
        ansible_core_version="2.15.13",
        ansible_runner_version="2.4.0",
        collections=[
            AnsibleCollection(name="community.postgresql", version="3.14.0"),
            AnsibleCollection(name="community.general", version="11.4.0"),
        ],
        python_dependencies=["psycopg2-binary==2.9.10", "requests==2.31.0"],
        system_dependencies=["postgresql"],
        image_tag="0.1.0",
        registry_namespace="example-platform",
        publish_target="quay.io",
        created_at="2026-05-24T00:00:00Z",
        updated_at="2026-05-24T00:00:00Z",
    )
    report = CompatibilityAdvisor().analyze(record.id, record, [])
    files = EEFileGenerator(MemoryStore()).generate(record, report)

    assert "community.postgresql" in files["requirements.yml"]
    assert "community.general" in files["requirements.yml"]
    assert "psycopg2-binary==2.9.10" in files["requirements.txt"]
    assert "requests==2.31.0" in files["requirements.txt"]
    assert "postgresql" in files["bindep.txt"]


def test_generator_adds_fedora_python_bootstrap_for_ansible_core_216():
    record = EERequestRecord(
        id="test-id",
        ee_name="ee-aap-config-as-code",
        description="AAP CaC automation",
        purpose="Configure AAP as code",
        automation_domain="aap-config-as-code",
        base_image="registry.fedoraproject.org/fedora:43",
        ansible_core_version="2.16.18",
        ansible_runner_version="2.4.0",
        collections=[AnsibleCollection(name="infra.aap_configuration", version="4.5.0")],
        python_dependencies=["awxkit==24.6.1"],
        system_dependencies=[],
        image_tag="0.1.0",
        registry_namespace="example-platform",
        publish_target="quay.io",
        created_at="2026-05-24T00:00:00Z",
        updated_at="2026-05-24T00:00:00Z",
    )
    report = CompatibilityAdvisor().analyze(record.id, record, [])
    files = EEFileGenerator(MemoryStore()).generate(record, report)

    assert "additional_build_steps:" in files["execution-environment.yml"]
    assert "prepend_base:" in files["execution-environment.yml"]
    assert "dnf install -y python3 python3-pip" in files["execution-environment.yml"]
    assert "FEDORA_PYTHON_BOOTSTRAP_ADDED" in files["compatibility-report.md"]
