from app.models.ee_request import AnsibleCollection, EERequestRecord, Finding, Severity
from app.services.documentation_service import DocumentationService


class MemoryStore:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.saved_records: list[EERequestRecord] = []

    def write_text(self, request_id: str, relative_path: str, content: str):
        self.files[relative_path] = content
        return f"/tmp/{request_id}/{relative_path}"

    def save_record(self, record: EERequestRecord) -> None:
        self.saved_records.append(record)


class FakeOllama:
    def __init__(self, response: str | None) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str | None:
        self.prompts.append(prompt)
        return self.response


def make_record() -> EERequestRecord:
    return EERequestRecord(
        id="llm-test",
        ee_name="ee-postgresql-admin",
        description="PostgreSQL administration EE",
        purpose="Manage PostgreSQL users, databases, and maintenance workflows.",
        automation_domain="database",
        base_image="quay.io/rockylinux/rockylinux:9",
        ansible_core_version="2.15.13",
        ansible_runner_version="2.4.0",
        collections=[AnsibleCollection(name="community.postgresql", version="3.14.0")],
        python_dependencies=["psycopg2-binary==2.9.10"],
        system_dependencies=["postgresql"],
        image_tag="0.1.0",
        registry_namespace="example-platform",
        publish_target="quay.io",
        registry_target="quay.io/example-platform/ee-postgresql-admin:0.1.0",
        compatibility_findings=[
            Finding(
                severity=Severity.warning,
                code="SYSTEM_REQUIREMENT_REVIEW",
                message="System dependency 'postgresql' should be reviewed.",
                field="system_dependencies",
            )
        ],
        created_at="2026-05-25T00:00:00Z",
        updated_at="2026-05-25T00:00:00Z",
    )


def test_llm_advisory_is_marked_as_advisory_only():
    store = MemoryStore()
    ollama = FakeOllama("## Review focus\n- Confirm the database scope and package need.")
    record = make_record()

    content = DocumentationService(store, ollama).advisory(record)

    assert "advisory only" in content
    assert "deterministic guardrails" in content
    assert "Request facts from the platform" in content
    assert "Base image: `quay.io/rockylinux/rockylinux:9`" in content
    assert "`community.postgresql` pinned to `3.14.0`" in content
    assert "llm-advisory.md" in store.files
    assert "llm-advisory.md" in record.generated_files
    assert "Do not approve, reject, waive, or downgrade any finding." in ollama.prompts[0]


def test_llm_advisory_falls_back_when_ollama_unavailable():
    store = MemoryStore()
    record = make_record()

    content = DocumentationService(store, FakeOllama(None)).advisory(record)

    assert "Ollama is disabled or unavailable" in content
    assert "SYSTEM_REQUIREMENT_REVIEW" in content
    assert "approval gates" in content
