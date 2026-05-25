from pathlib import Path
from subprocess import STDOUT, CalledProcessError, run


class AnsibleBuilderService:
    def create_context(self, workspace: Path, log_path: Path) -> Path:
        context_dir = workspace / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        command = [
            "ansible-builder",
            "create",
            "--file",
            "execution-environment.yml",
            "--context",
            "context",
            "--output-filename",
            "Containerfile",
        ]
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write("Creating build context with ansible-builder\n")
            log_file.write(f"Command: {' '.join(command)}\n")
            try:
                run(command, cwd=workspace, check=True, stdout=log_file, stderr=STDOUT)
            except CalledProcessError as exc:
                log_file.write(f"ansible-builder failed with exit code {exc.returncode}\n")
                raise
        self._normalize_containerfile(context_dir / "Containerfile", log_path)
        return context_dir

    def _normalize_containerfile(self, containerfile: Path, log_path: Path) -> None:
        if not containerfile.exists():
            return
        content = containerfile.read_text(encoding="utf-8")
        normalized = content.replace("\\", "/")
        if normalized == content:
            return
        containerfile.write_text(normalized, encoding="utf-8")
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write("Normalized Windows path separators in generated Containerfile for Linux builders.\n")
