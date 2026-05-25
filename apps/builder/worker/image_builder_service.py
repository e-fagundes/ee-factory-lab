from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from subprocess import STDOUT, CalledProcessError, run


class ImageBuilderService:
    def build_oci_archive(self, workspace: Path, image_ref: str, log_path: Path) -> dict[str, str | None]:
        archive_path = workspace / "image.tar"
        if self._prefer_buildkit():
            self._run_buildkit(workspace, image_ref, archive_path, log_path, push=False)
            digest = self._extract_digest(log_path)
            return self._write_metadata(workspace, image_ref, "oci-archive", str(archive_path), digest)

        self._run_buildah(workspace, image_ref, log_path, push=False, archive_path=archive_path)
        digest = self._extract_digest(log_path)
        return self._write_metadata(workspace, image_ref, "buildah-oci-archive", str(archive_path), digest)

    def publish_image(self, workspace: Path, image_ref: str, log_path: Path) -> dict[str, str | None]:
        if self._prefer_buildkit():
            self._run_buildkit(workspace, image_ref, None, log_path, push=True)
            digest = self._extract_digest(log_path)
            return self._write_metadata(workspace, image_ref, "registry", image_ref, digest)

        self._run_buildah(workspace, image_ref, log_path, push=True, archive_path=None)
        digest = self._extract_digest(log_path)
        return self._write_metadata(workspace, image_ref, "buildah-registry", image_ref, digest)

    def _run_buildkit(
        self,
        workspace: Path,
        image_ref: str,
        archive_path: Path | None,
        log_path: Path,
        push: bool,
    ) -> None:
        context = workspace / "context"
        output = f"type=image,name={image_ref},push=true" if push else f"type=oci,dest={archive_path}"
        command = [
            "buildctl-daemonless.sh",
            "build",
            "--frontend",
            "dockerfile.v0",
            "--local",
            f"context={context}",
            "--local",
            f"dockerfile={context}",
            "--opt",
            "filename=Containerfile",
            "--output",
            output,
        ]
        env = os.environ.copy()
        env.setdefault("BUILDKITD_FLAGS", "--oci-worker-no-process-sandbox")
        runtime_dir = Path("/tmp/ee-factory-buildkit")
        runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        env.setdefault("XDG_RUNTIME_DIR", str(runtime_dir))
        self._run_logged(command, workspace, log_path, env)

    def _run_buildah(
        self,
        workspace: Path,
        image_ref: str,
        log_path: Path,
        push: bool,
        archive_path: Path | None,
    ) -> None:
        context = workspace / "context"
        build_command = [
            "buildah",
            "bud",
            "--storage-driver",
            "vfs",
            "--isolation",
            "chroot",
            "-f",
            str(context / "Containerfile"),
            "-t",
            image_ref,
            str(context),
        ]
        self._run_logged(build_command, workspace, log_path, os.environ.copy())
        if push:
            push_command = ["buildah", "push", image_ref, f"docker://{image_ref}"]
        else:
            push_command = ["buildah", "push", image_ref, f"oci-archive:{archive_path}:{image_ref}"]
        self._run_logged(push_command, workspace, log_path, os.environ.copy())

    def _prefer_buildkit(self) -> bool:
        return os.getenv("EE_IMAGE_BUILDER", "buildah").lower() == "buildkit" and bool(which("buildctl-daemonless.sh"))

    def _run_logged(self, command: list[str], workspace: Path, log_path: Path, env: dict[str, str]) -> None:
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write("\nRunning controlled build command\n")
            log_file.write(f"Command: {' '.join(command)}\n")
            try:
                run(command, cwd=workspace, check=True, stdout=log_file, stderr=STDOUT, env=env)
            except CalledProcessError as exc:
                log_file.write(f"Build command failed with exit code {exc.returncode}\n")
                raise

    def _write_metadata(
        self,
        workspace: Path,
        image_ref: str,
        output_type: str,
        output_ref: str,
        digest: str | None,
    ) -> dict[str, str | None]:
        metadata = {
            "image_ref": image_ref,
            "output_type": output_type,
            "output_ref": output_ref,
            "digest": digest,
            "built_at": datetime.now(timezone.utc).isoformat(),
        }
        (workspace / "image-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return metadata

    def _extract_digest(self, log_path: Path) -> str | None:
        if not log_path.exists():
            return None
        content = log_path.read_text(encoding="utf-8", errors="ignore")
        digest_matches = re.findall(r"sha256:[a-f0-9]{64}", content)
        if digest_matches:
            return digest_matches[-1]
        image_id_matches = re.findall(r"(?m)^[a-f0-9]{64}$", content)
        if image_id_matches:
            return f"sha256:{image_id_matches[-1]}"
        return None
