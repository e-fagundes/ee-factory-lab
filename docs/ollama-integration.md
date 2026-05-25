# Ollama Integration

Ollama is optional and disabled by default in static manifests, then enabled explicitly for local labs that have a model installed.

## Configuration

```env
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://host.minikube.internal:11434
OLLAMA_MODEL=llama3.2:1b
```

Local development can use:

```env
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:1b
```

Minikube deployment with Ollama enabled:

```powershell
ollama pull llama3.2:1b
.\scripts\deploy-minikube.ps1 -EnableOllama
.\scripts\port-forward.ps1 -StopExisting
```

The API exposes Ollama status through `GET /api/v1/settings`, and the portal shows it in Settings.

## Allowed Uses

- Generate user-facing README content.
- Summarize compatibility findings.
- Explain selected collections.
- Suggest EE split recommendations.
- Generate `llm-advisory.md` review notes for the portal.
- Draft pull request summaries.

## Not Allowed

The local LLM must not:

- Approve generated files.
- Approve publish.
- Override deterministic guardrails.
- Decide whether vulnerabilities are acceptable.
- Inject secrets into generated files.

## Output Marking

LLM-assisted README and advisory content is marked as generated assistance and should be reviewed and edited before enterprise use.

The platform continues to work when Ollama is disabled or unavailable.
