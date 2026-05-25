from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.config_loader import load_yaml
from app.llm.ollama_client import OllamaClient
from app.models.ee_request import BuildRequest, EERequestCreate, EERequestRecord, GeneratedFile, GeneratedFilesResponse, NewVersionRequest
from app.services.request_service import EERequestService

router = APIRouter()


def service() -> EERequestService:
    return EERequestService()


@router.get("/settings")
def settings() -> dict[str, object]:
    current = get_settings()
    return {
        "app_env": current.app_env,
        "default_publish_target": current.default_publish_target,
        "vulnerability_scan_enabled": current.vulnerability_scan_enabled,
        "vulnerability_scan_required": current.vulnerability_scan_required,
        "ollama_enabled": current.ollama_enabled,
        "ollama_model": current.ollama_model,
        "ollama_status": OllamaClient().status(),
    }


@router.get("/domains")
def domains() -> dict[str, object]:
    current = get_settings()
    return load_yaml(current.config_dir / "domain-taxonomy.yml")


@router.get("/base-images")
def base_images() -> dict[str, object]:
    current = get_settings()
    return load_yaml(current.config_dir / "allowed-base-images.yml")


@router.post("/ee-requests", response_model=EERequestRecord)
def create_ee_request(payload: EERequestCreate) -> EERequestRecord:
    return service().create(payload)


@router.get("/ee-requests", response_model=list[EERequestRecord])
def list_ee_requests() -> list[EERequestRecord]:
    return service().list_requests()


@router.get("/ee-requests/{request_id}", response_model=EERequestRecord)
def get_ee_request(request_id: str) -> EERequestRecord:
    return service().get(request_id)


@router.post("/ee-requests/{request_id}/new-version", response_model=EERequestRecord)
def create_new_version(request_id: str, payload: NewVersionRequest) -> EERequestRecord:
    return service().create_new_version(request_id, payload)


@router.post("/ee-requests/{request_id}/validate")
def validate_ee_request(request_id: str) -> dict[str, object]:
    return {"request_id": request_id, "findings": service().validate(request_id)}


@router.get("/ee-requests/{request_id}/compatibility-report")
def compatibility_report(request_id: str) -> dict[str, object]:
    return service().compatibility_report(request_id).model_dump()


@router.post("/ee-requests/{request_id}/vulnerability-scan")
def vulnerability_scan(request_id: str) -> dict[str, object]:
    return service().vulnerability_report(request_id).model_dump()


@router.get("/ee-requests/{request_id}/vulnerability-report")
def vulnerability_report(request_id: str) -> dict[str, object]:
    return service().vulnerability_report(request_id).model_dump()


@router.post("/ee-requests/{request_id}/generate")
def generate_files(request_id: str) -> GeneratedFilesResponse:
    files = service().generate(request_id)
    return GeneratedFilesResponse(
        request_id=request_id,
        files=[GeneratedFile(name=name, content=content) for name, content in files.items()],
    )


@router.get("/ee-requests/{request_id}/generated-files")
def generated_files(request_id: str) -> GeneratedFilesResponse:
    files = service().generated_files(request_id)
    return GeneratedFilesResponse(
        request_id=request_id,
        files=[GeneratedFile(name=name, content=content) for name, content in files.items()],
    )


@router.post("/ee-requests/{request_id}/approve-generated-files")
def approve_generated_files(request_id: str) -> dict[str, str]:
    record = service().get(request_id)
    if not record.generated_files:
        raise HTTPException(status_code=409, detail="Generate files before approval")
    record.status = "GENERATED_FILES_APPROVED"
    record.approval_status = "GENERATED_FILES_APPROVED"
    service().store.save_record(record)
    return {"request_id": request_id, "status": record.status}


@router.post("/ee-requests/{request_id}/build")
def build(request_id: str, payload: BuildRequest | None = None) -> dict[str, object]:
    return service().build(request_id, payload or BuildRequest())


@router.get("/ee-requests/{request_id}/build-status")
def build_status(request_id: str) -> dict[str, object]:
    return service().build_status(request_id)


@router.get("/ee-requests/{request_id}/logs")
def logs(request_id: str) -> dict[str, str]:
    service().get(request_id)
    store = service().store
    return {
        "request_id": request_id,
        "validation_log": store.read_text(request_id, "logs/validation.log"),
        "build_log": store.read_text(request_id, "logs/build.log"),
        "publish_log": store.read_text(request_id, "logs/publish.log"),
    }


@router.post("/ee-requests/{request_id}/approve-publish")
def approve_publish(request_id: str) -> dict[str, str]:
    record = service().approve_publish(request_id)
    return {"request_id": request_id, "status": record.status}


@router.post("/ee-requests/{request_id}/publish")
def publish(request_id: str) -> dict[str, object]:
    return service().publish(request_id)


@router.post("/ee-requests/{request_id}/generate-docs")
def generate_docs(request_id: str) -> dict[str, str]:
    content = service().generate_docs(request_id)
    return {"request_id": request_id, "status": "GENERATED", "content": content}


@router.post("/ee-requests/{request_id}/llm-advisory")
def generate_llm_advisory(request_id: str) -> dict[str, str]:
    content = service().generate_llm_advisory(request_id)
    return {"request_id": request_id, "status": "GENERATED", "content": content}
