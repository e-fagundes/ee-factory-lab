from app.llm.ollama_client import OllamaClient
from app.models.ee_request import EERequestRecord
from app.repositories.local_store import LocalStore


class DocumentationService:
    def __init__(self, store: LocalStore, ollama: OllamaClient | None = None) -> None:
        self.store = store
        self.ollama = ollama or OllamaClient()

    def generate(self, record: EERequestRecord) -> str:
        prompt = self._prompt(record)
        generated = self.ollama.generate(prompt)
        if generated:
            content = "\n".join(
                [
                    f"# {record.ee_name}",
                    "",
                    "> Generated assistance from the optional local Ollama integration. Review and edit before enterprise use.",
                    "",
                    generated,
                    "",
                ]
            )
        else:
            content = self._fallback(record)

        path = self.store.write_text(record.id, "generated-readme.md", content)
        record.generated_documentation_path = str(path)
        if record.generated_files:
            record.generated_files["generated-readme.md"] = str(path)
        self.store.save_record(record)
        return content

    def _prompt(self, record: EERequestRecord) -> str:
        collection_lines = "\n".join(
            f"- {collection.name}=={collection.version}" for collection in record.collections
        )
        finding_lines = "\n".join(
            f"- {finding.severity}: {finding.code}: {finding.message}"
            for finding in [*record.validation_findings, *record.compatibility_findings, *record.vulnerability_findings]
        )
        return f"""
Create concise user-facing documentation for an Ansible Execution Environment.
Do not make security or approval decisions. Mark risky items as things a human reviewer must confirm.

EE name: {record.ee_name}
Description: {record.description}
Purpose: {record.purpose}
Automation domain: {record.automation_domain}
Base image: {record.base_image}
Image tag: {record.image_tag}
Registry target: {record.registry_target}

Collections:
{collection_lines}

Known findings:
{finding_lines or "- None"}
""".strip()

    def _fallback(self, record: EERequestRecord) -> str:
        lines = [
            f"# {record.ee_name}",
            "",
            record.description,
            "",
            "## Purpose",
            "",
            record.purpose,
            "",
            "## Generated Assistance",
            "",
            "Ollama is disabled or unavailable. This README was produced by deterministic templates and is editable.",
            "",
            "## Image",
            "",
            f"- Registry target: `{record.registry_target}`",
            f"- Tag: `{record.image_tag}`",
            "",
            "## Collections",
            "",
        ]
        for collection in record.collections:
            lines.append(f"- `{collection.name}` pinned to `{collection.version}`")
        return "\n".join(lines) + "\n"
