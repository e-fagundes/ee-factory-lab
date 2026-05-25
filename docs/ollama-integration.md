# Ollama Integration

Ollama is optional and disabled by default.

## Configuration

```env
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1
```

## Allowed Uses

- Generate user-facing README content.
- Summarize compatibility findings.
- Explain selected collections.
- Suggest EE split recommendations.
- Draft pull request summaries.

## Not Allowed

The local LLM must not:

- Approve generated files.
- Approve publish.
- Override deterministic guardrails.
- Decide whether vulnerabilities are acceptable.
- Inject secrets into generated files.

## Output Marking

LLM-assisted README content is marked as generated assistance and should be reviewed and edited before enterprise use.

The platform continues to work when Ollama is disabled or unavailable.
