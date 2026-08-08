# Red Flag Agent

A production-ready FastAPI service that analyzes financial report chunks stored in ChromaDB and returns structured red-flag findings.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy [.env.example](.env.example) to .env and add your Gemini API key.
3. Run:
   ```bash
   uvicorn app.main:app --reload
   ```

## Environment Variables

Copy `.env.example` to `.env` and update as needed. Key variables:

- `GEMINI_API_KEY` — API key for Google Gemini (optional; offline fallback available)
- `MODEL_NAME` — LLM model name (default: `gemini-2.5-pro`)
- `EMBEDDING_MODEL` — Embedding model identifier
- `CHROMA_DB_PATH` — Local persistent ChromaDB directory
- `DEFAULT_COLLECTION_NAME` — Default collection used by ingestion/CLI
- `DEFAULT_TOP_K` — Default retrieval `top_k` value
- `REQUEST_TIMEOUT_SECONDS` — Request timeout for external calls
- `LOG_LEVEL` — Logging level (INFO/DEBUG)

Notes:
- If `GEMINI_API_KEY` is not provided or Gemini calls fail (quota/auth/network), the service uses a deterministic offline analyzer so the API continues to return structured results.
- The project expects a local ChromaDB persistence directory by default. For production, configure a managed vector DB or ensure proper persistence and backups.

## API

### Health

```bash
curl http://127.0.0.1:8000/health
```

### Analyze Red Flags

```bash
curl -X POST http://127.0.0.1:8000/redflag/analyze \
  -H "Content-Type: application/json" \
  -d '{"company":"Infosys","collection":"infosys_2024"}'
```

## Endpoints

- GET /health
- POST /redflag/analyze
- GET /docs

## Note on CrewAI integration

This project previously included `CrewAI` agent and task factories. For clarity and simplicity the current
implementation uses `GeminiService` directly to execute the red-flag analysis prompt. If you want to re-enable
full CrewAI orchestration (multi-agent workflows, task delegation), update `RedFlagCrew` in
`app/agents/crew.py` to call the CrewAI runtime and adapt `GeminiService` to act as a tool/connector rather than
the direct execution path.

Keeping the LLM execution path explicit reduces indirection and makes testing and error-handling simpler.
