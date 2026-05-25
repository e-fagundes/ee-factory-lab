import json
from pathlib import Path

from app.compatibility.advisor import CompatibilityAdvisor
from app.guardrails.validator import GuardrailValidator
from app.models.ee_request import EERequestCreate, Severity


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    validator = GuardrailValidator()
    advisor = CompatibilityAdvisor()
    failures = 0
    required_files = {
        "request.json",
        "execution-environment.yml",
        "requirements.yml",
        "README.md",
        "compatibility-report.md",
    }
    for request_path in sorted((repo_root / "examples").glob("*/request.json")):
        missing_files = sorted(required_files - {path.name for path in request_path.parent.iterdir()})
        if missing_files:
            print(f"{request_path.parent.name}: missing files: {', '.join(missing_files)}")
            failures += len(missing_files)
        payload = EERequestCreate(**json.loads(request_path.read_text(encoding="utf-8")))
        findings = validator.validate(payload)
        report = advisor.analyze(request_path.parent.name, payload, findings)
        blockers = [finding for finding in findings if finding.severity == Severity.blocker]
        unpinned = [collection.name for collection in payload.collections if not collection.version]
        if unpinned:
            print(f"{request_path.parent.name}: unpinned collections: {', '.join(unpinned)}")
            failures += len(unpinned)
        print(
            f"{request_path.parent.name}: {len(blockers)} blocker(s), "
            f"{len(report.findings)} compatibility finding(s)"
        )
        failures += len(blockers)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
