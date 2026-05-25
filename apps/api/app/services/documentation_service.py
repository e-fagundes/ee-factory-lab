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

    def advisory(self, record: EERequestRecord) -> str:
        prompt = self._advisory_prompt(record)
        generated = self.ollama.generate(prompt)
        content = self._wrap_advisory(record, generated) if generated else self._fallback_advisory(record)
        path = self.store.write_text(record.id, "llm-advisory.md", content)
        record.generated_files["llm-advisory.md"] = str(path)
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

    def _advisory_prompt(self, record: EERequestRecord) -> str:
        collection_lines = "\n".join(
            f"- {collection.name}=={collection.version}" for collection in record.collections
        )
        python_lines = "\n".join(f"- {dependency}" for dependency in record.python_dependencies)
        system_lines = "\n".join(f"- {dependency}" for dependency in record.system_dependencies)
        finding_lines = "\n".join(
            f"- {finding.severity}: {finding.code}: {finding.message}"
            for finding in [*record.validation_findings, *record.compatibility_findings, *record.vulnerability_findings]
        )
        return f"""
You are helping a platform user understand an Ansible Execution Environment request.
You are not a policy engine. Do not approve, reject, waive, or downgrade any finding.
Do not say the request is safe. Do not ask the user to click a fake confirmation.
Do not restate a technical fact unless it appears exactly in the request data.
If the narrative conflicts with the request facts, the request facts are authoritative.
Write concise Markdown for a human review panel with these sections:

## What this EE is trying to do
## Review focus
## Dependency and scope notes
## Suggested split or keep-together guidance
## Questions for the requester
## Production adaptation notes

Use practical, calm language. Keep it under 350 words.

EE name: {record.ee_name}
Description: {record.description}
Purpose: {record.purpose}
Automation domain: {record.automation_domain}
Base image: {record.base_image}
ansible-core: {record.ansible_core_version}
ansible-runner: {record.ansible_runner_version}
Image: {record.registry_target}

Collections:
{collection_lines or "- None"}

Python dependencies:
{python_lines or "- None"}

System dependencies:
{system_lines or "- None"}

Deterministic findings:
{finding_lines or "- None"}
""".strip()

    def _wrap_advisory(self, record: EERequestRecord, generated: str) -> str:
        return "\n".join(
            [
                f"# Llama-assisted review notes for {record.ee_name}",
                "",
                "> Generated assistance from the optional local Ollama integration. This text is advisory only; deterministic guardrails, vulnerability scans, and human approval gates remain authoritative.",
                "",
                "## Request facts from the platform",
                "",
                f"- Automation domain: `{record.automation_domain}`",
                f"- Base image: `{record.base_image}`",
                f"- ansible-core: `{record.ansible_core_version}`",
                f"- ansible-runner: `{record.ansible_runner_version}`",
                f"- Image target: `{record.registry_target}`",
                "",
                "Collections:",
                *[f"- `{collection.name}` pinned to `{collection.version}`" for collection in record.collections],
                "",
                "Python dependencies:",
                *([f"- `{dependency}`" for dependency in record.python_dependencies] or ["- None declared"]),
                "",
                "System dependencies:",
                *([f"- `{dependency}`" for dependency in record.system_dependencies] or ["- None declared"]),
                "",
                "## Deterministic platform findings",
                "",
                *self._finding_lines(record),
                "",
                "## Llama narrative",
                "",
                generated,
                "",
            ]
        )

    def _finding_lines(self, record: EERequestRecord) -> list[str]:
        findings = [*record.validation_findings, *record.compatibility_findings, *record.vulnerability_findings]
        if not findings:
            return ["- No deterministic findings are currently recorded."]
        return [f"- `{finding.severity}` `{finding.code}`: {finding.message}" for finding in findings]

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

    def _fallback_advisory(self, record: EERequestRecord) -> str:
        findings = [*record.validation_findings, *record.compatibility_findings, *record.vulnerability_findings]
        lines = [
            f"# Deterministic review notes for {record.ee_name}",
            "",
            "> Ollama is disabled or unavailable. These notes were generated without LLM assistance.",
            "",
            "## What this EE is trying to do",
            "",
            f"`{record.ee_name}` targets the `{record.automation_domain}` automation domain.",
            "",
            "## Review focus",
            "",
        ]
        if findings:
            for finding in findings:
                lines.append(f"- `{finding.severity}` `{finding.code}`: {finding.message}")
        else:
            lines.append("- No deterministic findings are currently recorded.")
        lines.extend(
            [
                "",
                "## Production adaptation notes",
                "",
                "- Keep collection versions pinned.",
                "- Treat custom base images, broad scopes, and vulnerabilities as explicit review items.",
                "- Use the approval gates before build and registry publication.",
            ]
        )
        return "\n".join(lines) + "\n"
