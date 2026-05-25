import json
import os

from app.core.config import get_settings
from app.models.ee_request import EERequestCreate, Severity
from app.security.vulnerability_advisor import VulnerabilityAdvisor


def main() -> None:
    settings = get_settings()
    examples_dir = settings.repo_root / "examples"
    advisor = VulnerabilityAdvisor()
    blockers: list[str] = []
    update_reports = os.getenv("UPDATE_EXAMPLE_VULN_REPORTS", "false").lower() == "true"
    for request_path in sorted(examples_dir.glob("*/request.json")):
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        request = EERequestCreate.model_validate(payload)
        report = advisor.analyze(request_path.parent.name, request)
        if update_reports:
            output_path = request_path.parent / "vulnerability-report.md"
            output_path.write_text(report.markdown, encoding="utf-8")
        if any(finding.severity == Severity.blocker for finding in report.findings):
            blockers.append(str(request_path))
        print(f"{request_path.parent.name}: {len(report.findings)} finding(s)")
    if blockers:
        joined = "\n".join(blockers)
        raise SystemExit(f"Vulnerability blockers found in examples:\n{joined}")


if __name__ == "__main__":
    main()
