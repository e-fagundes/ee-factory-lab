import httpx

from app.core.config import get_settings


class OllamaClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate(self, prompt: str) -> str | None:
        if not self.settings.ollama_enabled:
            return None
        payload = {
            "model": self.settings.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(f"{self.settings.ollama_base_url}/api/generate", json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, httpx.TimeoutException):
            return None
        generated = body.get("response")
        return str(generated).strip() if generated else None
