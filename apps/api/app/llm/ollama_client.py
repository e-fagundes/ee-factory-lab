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

    def status(self) -> dict[str, object]:
        if not self.settings.ollama_enabled:
            return {
                "enabled": False,
                "available": False,
                "model": self.settings.ollama_model,
                "message": "Ollama is disabled.",
            }
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.settings.ollama_base_url}/api/tags")
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, httpx.TimeoutException):
            return {
                "enabled": True,
                "available": False,
                "model": self.settings.ollama_model,
                "message": "Ollama is enabled but the local endpoint is unavailable.",
            }
        models = [item.get("name") for item in body.get("models", []) if isinstance(item, dict)]
        return {
            "enabled": True,
            "available": self.settings.ollama_model in models,
            "model": self.settings.ollama_model,
            "models": models,
            "message": "Ollama is available." if self.settings.ollama_model in models else "Configured model is not installed.",
        }
