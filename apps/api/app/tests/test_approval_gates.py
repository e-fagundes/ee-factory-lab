import pytest
from fastapi import HTTPException

from app.models.ee_request import AnsibleCollection, BuildMode, BuildRequest, EERequestRecord
from app.services.request_service import EERequestService


class FakeStore:
    def __init__(self, record: EERequestRecord, build_result_exists: bool = False) -> None:
        self.record = record
        self.build_result_exists = build_result_exists
        self.saved_records: list[EERequestRecord] = []

    def get_request(self, request_id: str) -> EERequestRecord:
        if request_id != self.record.id:
            raise FileNotFoundError(request_id)
        return self.record

    def exists(self, request_id: str, relative_path: str) -> bool:
        return relative_path == "build-result.json" and self.build_result_exists

    def read_json(self, request_id: str, relative_path: str) -> object:
        return {"status": "BUILT", "metadata": {"digest": "sha256:" + "1" * 64}}

    def write_json(self, request_id: str, relative_path: str, payload: object) -> None:
        return None

    def save_record(self, record: EERequestRecord) -> None:
        self.record = record
        self.saved_records.append(record)


class FakeBuildOrchestrator:
    def submit_job(self, record: EERequestRecord, mode: BuildMode) -> dict[str, object]:
        return {
            "submitted": True,
            "job_name": f"ee-builder-{record.id[:8]}",
            "manifest": {"kind": "Job"},
            "message": "Kubernetes build job created.",
        }


def make_record(**overrides) -> EERequestRecord:
    payload = {
        "id": "abc12345-0000-0000-0000-000000000000",
        "ee_name": "ee-postgresql-admin",
        "description": "PostgreSQL automation",
        "purpose": "Manage PostgreSQL databases and users",
        "automation_domain": "database",
        "base_image": "quay.io/rockylinux/rockylinux:9",
        "ansible_core_version": "2.15.13",
        "ansible_runner_version": "2.4.0",
        "collections": [AnsibleCollection(name="community.postgresql", version="3.14.0")],
        "python_dependencies": ["psycopg2-binary==2.9.10"],
        "system_dependencies": [],
        "image_tag": "0.1.0",
        "registry_namespace": "example-platform",
        "publish_target": "quay.io",
        "registry_target": "quay.io/example-platform/ee-postgresql-admin:0.1.0",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    }
    payload.update(overrides)
    return EERequestRecord(**payload)


def service_for(record: EERequestRecord, build_result_exists: bool = False) -> EERequestService:
    service = EERequestService.__new__(EERequestService)
    service.store = FakeStore(record, build_result_exists)
    service.build_orchestrator = FakeBuildOrchestrator()
    return service


def test_build_is_blocked_until_generated_files_are_approved():
    service = service_for(make_record(generated_files={"execution-environment.yml": "/tmp/file"}))

    with pytest.raises(HTTPException) as exc:
        service.build("abc12345-0000-0000-0000-000000000000", BuildRequest(mode=BuildMode.stage_for_approval))

    assert exc.value.status_code == 409
    assert exc.value.detail == "Approve generated files before building"


def test_build_is_blocked_when_files_were_not_generated():
    service = service_for(make_record(approval_status="GENERATED_FILES_APPROVED"))

    with pytest.raises(HTTPException) as exc:
        service.build("abc12345-0000-0000-0000-000000000000", BuildRequest(mode=BuildMode.stage_for_approval))

    assert exc.value.status_code == 409
    assert exc.value.detail == "Generate files before building"


def test_publish_is_blocked_until_publish_approval():
    service = service_for(
        make_record(
            approval_status="GENERATED_FILES_APPROVED",
            generated_files={"execution-environment.yml": "/tmp/file"},
            build_status="BUILT",
            status="BUILT",
        )
    )

    with pytest.raises(HTTPException) as exc:
        service.publish("abc12345-0000-0000-0000-000000000000")

    assert exc.value.status_code == 409
    assert exc.value.detail == "Approve publish before pushing to registry"


def test_build_result_is_not_requeued_for_existing_request():
    service = service_for(
        make_record(
            approval_status="GENERATED_FILES_APPROVED",
            generated_files={"execution-environment.yml": "/tmp/file"},
        ),
        build_result_exists=True,
    )

    response = service.build(
        "abc12345-0000-0000-0000-000000000000",
        BuildRequest(mode=BuildMode.stage_for_approval),
    )

    assert response["already_exists"] is True
    assert response["status"] == "BUILT"
