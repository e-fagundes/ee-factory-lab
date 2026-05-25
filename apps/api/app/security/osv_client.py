import httpx

from app.core.config import get_settings


class OSVClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def query_batch(self, packages: list[dict[str, str]]) -> list[dict[str, object]]:
        if not packages:
            return []
        payload = {
            "queries": [
                {
                    "package": {
                        "ecosystem": package["ecosystem"],
                        "name": package["name"],
                    },
                    "version": package["version"],
                }
                for package in packages
            ]
        }
        with httpx.Client(timeout=20.0) as client:
            response = client.post(f"{self.settings.osv_api_base_url}/v1/querybatch", json=payload)
            response.raise_for_status()
            return response.json().get("results", [])

    def get_vulnerability(self, vulnerability_id: str) -> dict[str, object]:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(f"{self.settings.osv_api_base_url}/v1/vulns/{vulnerability_id}")
            response.raise_for_status()
            return response.json()
