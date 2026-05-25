import json

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    examples_dir = settings.repo_root / "examples"
    output_path = settings.repo_root / "docs" / "generated-example-catalog.md"
    lines = [
        "# Generated Example Catalog",
        "",
        "This file is generated from `examples/*/request.json`.",
        "",
    ]
    for request_path in sorted(examples_dir.glob("*/request.json")):
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        lines.extend(
            [
                f"## {payload['ee_name']}",
                "",
                payload["description"],
                "",
                f"- Domain: `{payload['automation_domain']}`",
                f"- Base image: `{payload['base_image']}`",
                f"- Image tag: `{payload['image_tag']}`",
                f"- Registry namespace: `{payload['registry_namespace']}`",
                "",
                "Collections:",
                "",
            ]
        )
        for collection in payload["collections"]:
            lines.append(f"- `{collection['name']}` pinned to `{collection['version']}`")
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
