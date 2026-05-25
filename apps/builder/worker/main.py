import json
import os
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CalledProcessError

from worker.ansible_builder_service import AnsibleBuilderService
from worker.image_builder_service import ImageBuilderService
from worker.publisher_service import PublisherService


def main() -> None:
    request_id = require_env("EE_REQUEST_ID")
    data_dir = Path(os.getenv("DATA_DIR", "/data")).resolve()
    mode = os.getenv("BUILD_MODE", "build_only")
    push_image = os.getenv("PUSH_IMAGE", "false").lower() == "true"
    workspace = (data_dir / "builds" / request_id).resolve()

    if not workspace.is_relative_to(data_dir):
        raise RuntimeError("Refusing to operate outside DATA_DIR")
    if not workspace.exists():
        raise FileNotFoundError(f"Build workspace not found: {workspace}")

    log_dir = workspace / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    build_log = log_dir / "build.log"
    publish_log = log_dir / "publish.log"

    manifest = read_manifest(workspace)
    image_ref = os.getenv("IMAGE_REF") or manifest.get("image")
    if not isinstance(image_ref, str) or not image_ref:
        raise RuntimeError("IMAGE_REF or manifest.image is required")

    write_log(build_log, f"Builder worker started for request {request_id} in mode {mode}")
    write_log(build_log, f"Workspace: {workspace}")
    write_log(build_log, f"Image: {image_ref}")

    try:
        context_path = AnsibleBuilderService().create_context(workspace, build_log)
        write_log(build_log, f"Build context created at {context_path}")

        image_builder = ImageBuilderService()
        if push_image or mode == "publish_after_approval":
            write_log(publish_log, f"Publishing approved image {image_ref}")
            metadata = PublisherService(image_builder).publish(workspace, image_ref, publish_log)
            status = "PUBLISHED"
        else:
            metadata = image_builder.build_oci_archive(workspace, image_ref, build_log)
            status = "BUILT"

        result = {
            "request_id": request_id,
            "status": status,
            "image_ref": image_ref,
            "metadata": metadata,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        (workspace / "build-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        write_log(build_log, f"Builder worker completed with status {status}")
    except CalledProcessError as exc:
        write_failure(workspace, request_id, image_ref, exc.returncode)
        raise


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def read_manifest(workspace: Path) -> dict[str, object]:
    manifest_path = workspace / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {workspace}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")


def write_failure(workspace: Path, request_id: str, image_ref: str, exit_code: int) -> None:
    result = {
        "request_id": request_id,
        "status": "FAILED",
        "image_ref": image_ref,
        "exit_code": exit_code,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    (workspace / "build-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
