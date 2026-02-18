# Agent Fishbowl — Technical Conventions

> This document is maintained by the Tech Lead agent. All agents should follow these conventions.
> For project-wide context, see `CLAUDE.md`.

## Status

This is a living document. The tech lead reviews and updates it regularly based on codebase patterns, reviewer feedback, and upcoming roadmap needs.

---

## 1. Pre-commit Quality Checks

Run `scripts/run-checks.sh` before opening any PR. The script runs four checks in sequence:

1. **`ruff check api/`** — Python linting (PEP 8, unused imports, naming)
2. **`ruff format --check api/`** — Python formatting
3. **`npx tsc --noEmit`** — TypeScript type checking (in `frontend/`)
4. **`npx eslint .`** — Frontend linting (in `frontend/`)

All four must pass before a PR can be opened.

### Fixing common failures

```bash
# Auto-fix Python formatting
ruff format api/

# Auto-fix Python lint issues (where possible)
ruff check --fix api/

# Auto-fix ESLint issues (where possible)
cd frontend && npx eslint . --fix
```

TypeScript errors (`tsc --noEmit`) must be fixed manually — read the error output for the file, line, and expected type.

## 2. Async HTTP Client Reuse

Use the shared HTTP client from `api/services/http_client.py` for requests within the FastAPI application. Creating a new `httpx.AsyncClient` per request wastes connections and bypasses connection pooling.

### Good — reuse the shared client

```python
from api.services.http_client import get_shared_client

async def fetch_data(url: str) -> dict:
    client = get_shared_client()
    response = await client.get(url)
    return response.json()
```

### Bad — new client per request

```python
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:  # new connection pool every call
        response = await client.get(url)
        return response.json()
```

**Exception:** One-off scripts or standalone functions that run outside the FastAPI process (e.g., `scripts/ingest.py`) may use `async with httpx.AsyncClient()` since there's no long-lived process to share a client with.

For retries with exponential backoff, use `fetch_with_retry` from the same module:

```python
from api.services.http_client import get_shared_client, fetch_with_retry

client = get_shared_client()
response = await fetch_with_retry(client, "GET", url)
```

## 3. Parallel Async Operations with `asyncio.gather()`

When making multiple independent async calls, use `asyncio.gather()` to run them concurrently instead of awaiting them sequentially.

### Good — parallel execution

```python
issues, prs, events = await asyncio.gather(
    client.get(f"{base}/issues", headers=headers),
    client.get(f"{base}/pulls", headers=headers),
    client.get(f"{base}/events", headers=headers),
)
```

### Bad — sequential execution of independent calls

```python
issues = await client.get(f"{base}/issues", headers=headers)
prs = await client.get(f"{base}/pulls", headers=headers)
events = await client.get(f"{base}/events", headers=headers)
```

### When to use `asyncio.gather()`

- The calls are **independent** — none needs the result of another.
- You need **all results** before proceeding.

### When NOT to use it

- Calls depend on each other (e.g., the second call uses the first call's result).
- You're hitting a rate-limited API and need to space requests out — use sequential calls with `await asyncio.sleep()` between them.
