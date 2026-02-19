# Agent Fishbowl — Technical Conventions

> This document is maintained by the Tech Lead agent. All agents should follow these conventions.
> For project-wide context, see `CLAUDE.md`.

## Status

This is a living document. The tech lead reviews and updates it regularly based on codebase patterns, reviewer feedback, and upcoming roadmap needs.

Last updated: 2026-02-19

---

## Pre-commit Checks

Run `scripts/run-checks.sh` before opening any PR. This runs ruff (format + lint), TypeScript type-checking, ESLint, and convention lint.

Common failures and fixes:

| Failure | Fix |
|---------|-----|
| `ruff format` | `ruff format .` from repo root |
| `ruff check` | `ruff check --fix .` (auto-fixable) or fix manually |
| Branch name | Use `scripts/create-branch.sh <issue_number> [feat\|fix]` |
| PR body missing issue ref | Add `Closes #N` to the PR description |

If `node_modules` is not installed (common in CI runner), tsc and eslint checks will be skipped. CI will validate those separately.

## Backend (Python)

### HTTP Client Reuse

Use the shared HTTP client from `api/services/http_client.py` for all outbound requests. Do not create new `httpx.AsyncClient` instances per request or per function call.

```python
# Good
from api.services.http_client import get_shared_client

async def fetch_data(url: str) -> dict:
    client = get_shared_client()
    response = await client.get(url)
    response.raise_for_status()
    return response.json()

# Bad — creates a new client per call (no connection pooling)
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

For GitHub API calls, use `github_headers()` from the same module to get correctly-formed headers including auth.

### Async Patterns

Use `asyncio.gather()` when fetching from multiple independent sources. Sequential loops waste time when requests don't depend on each other.

```python
# Good — parallel fetching of independent sources
results = await asyncio.gather(
    *[fetch_source(s) for s in sources],
    return_exceptions=True
)
for result in results:
    if isinstance(result, Exception):
        logger.warning("Source failed: %s", result)
        continue
    all_items.extend(result)

# Bad — sequential when sources are independent
for source in sources:
    items = await fetch_source(source)
    all_items.extend(items)
```

Use sequential `await` when:
- Operations have dependencies (result of A needed for B)
- Rate limiting is required (e.g., ingestion throttling between API calls)
- Order matters for correctness

Always pass `return_exceptions=True` to `asyncio.gather()` so one failure doesn't cancel the others.

### Error Handling

Services should catch exceptions and return safe defaults (empty lists, `None`) rather than propagating exceptions to the router layer. Log the error with context.

```python
# Service layer — catch and return safe default
async def get_items() -> list[Item]:
    try:
        return await _fetch_items()
    except Exception as e:
        logger.error("Failed to fetch items: %s", e)
        return []
```

Routers should raise `HTTPException` only for client-facing error conditions (404 for missing resources, 429 for rate limits). Don't raise 500 — let FastAPI's default handler deal with unhandled exceptions.

### Naming: Public vs Private

Functions imported by other modules are **public API** — name them without a leading underscore. Reserve `_underscore` prefixes for functions that are truly internal to a single module.

```python
# Public — imported by other modules or tests
def parse_events(raw_events: list[dict]) -> list[dict]: ...

# Private — only called within this file
def _build_thread_key(event: dict) -> str: ...
```

If a function starts as private but later gains external callers, rename it to drop the underscore.

### Imports and Module Structure

- Use `from __future__ import annotations` only if needed for forward references
- Prefer `str | None` over `Optional[str]` (Python 3.12+ union syntax)
- Group imports: stdlib, third-party, local (`api.`) — ruff enforces this
- Logger: always `logger = logging.getLogger(__name__)`

### Logging

Every service file must define and use a logger. Services that make external calls (HTTP, blob storage, GitHub API) should log:
- Errors and exceptions (always)
- Warnings for degraded states (e.g., cache misses, retries, fallbacks)

```python
import logging

logger = logging.getLogger(__name__)
```

Don't log success paths at INFO level in hot paths — it creates noise. Use DEBUG for those.

### Dead Code

Remove unused functions, imports, and variables. Don't keep code "for later" — version control is the backup. If a utility function exists but no caller imports it, delete it.

### Module Splitting

When a backend service file approaches 300 lines, split it into focused submodules. Use a thin aggregator module at the original path to maintain the public API surface — callers shouldn't need to change their imports.

Pattern (based on the `goals.py` refactoring):

```
services/
  goals.py              ← thin aggregator: re-exports types, owns shared cache, delegates to submodules
  goals_parser.py       ← file I/O + markdown parsing
  goals_roadmap.py      ← gh CLI interaction
  goals_metrics.py      ← GitHub API metrics
```

**Rules:**
- Each submodule should be under 200 lines and own a single concern
- The aggregator re-exports types via `__all__` so router imports don't change
- Shared state (caches, clients) stays in the aggregator and is passed to submodules via parameters — no cross-submodule imports for state
- Update `conftest.py` singleton resets to reference the correct module globals after splitting

Don't split preemptively. Split when a file crosses ~300 lines and has clearly separable concerns.

## Frontend (TypeScript/React)

### Utility Reuse

Utility functions belong in `src/lib/`. Import them — don't redefine them locally in pages or components.

Existing utilities:
- `src/lib/timeUtils.ts` — `timeAgo()`, `isFresh()` for relative timestamps
- `src/lib/formatTokens.ts` — token count formatting
- `src/lib/assetPath.ts` — base path helper
- `src/lib/agents.ts` — agent config lookup, avatar/color mapping
- `src/lib/api.ts` — API fetch functions and shared types
- `src/lib/navigation.ts` — shared nav items (Header, Footer)

### Type Organization

Keep types co-located with the code that uses them. For shared types used across many components, define them in `src/lib/api.ts` alongside the fetch functions that return them. If `api.ts` exceeds 300 lines, split types into `src/lib/types.ts` and re-export from `api.ts` for backwards compatibility.

### Component Patterns

- **Server Components** (default): No `"use client"` needed for components that only receive props and render. Use for presentational cards, layout wrappers, and static content.
- **Client Components**: Add `"use client"` only when the component uses hooks (`useState`, `useEffect`, `useCallback`, `usePathname`, etc.) or browser APIs.
- Keep components under 200 lines. Split complex state logic into custom hooks if a component grows beyond this.

### Error and Loading States

Use the established patterns for error and loading UI:

```tsx
// Error fallback — red border, user-friendly message, retry button
if (error) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6 dark:border-red-900 dark:bg-red-950">
      <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      <button onClick={retry}>Retry</button>
    </div>
  );
}

// Loading skeleton — animate-pulse with zinc background
if (loading) {
  return (
    <div className="h-64 animate-pulse rounded-xl border border-zinc-200 bg-zinc-100
                    dark:border-zinc-800 dark:bg-zinc-900" />
  );
}
```

### Constants and Magic Numbers

Define numeric constants (poll intervals, page sizes, debounce delays, thresholds) as named constants at the top of the file that uses them. Don't scatter raw numbers in component bodies.

```tsx
// Good — named constant with clear intent
const POLL_INTERVAL_MS = 30_000;
const PAGE_SIZE = 20;

useEffect(() => {
  const interval = setInterval(loadData, POLL_INTERVAL_MS);
  return () => clearInterval(interval);
}, [loadData]);

// Bad — magic number buried in logic
useEffect(() => {
  const interval = setInterval(loadData, 30000);
  return () => clearInterval(interval);
}, [loadData]);
```

When two or more files share the same constant value for the same purpose, extract it to a shared module in `src/lib/` rather than defining it in each file independently.

### Tailwind Styling

- Use Tailwind's standard scale for text sizes (`text-xs`, `text-sm`, `text-base`, etc.) for body text. For badges, timestamps, and metadata labels where `text-xs` (12px) is too large, `text-[10px]` is acceptable. Avoid all other arbitrary text sizes.
- Always include dark mode variants: every `bg-zinc-*` needs a `dark:bg-zinc-*` counterpart.
- Use the zinc palette for neutrals, consistent with the existing design system.
- Standard card pattern: `rounded-xl border border-zinc-200 dark:border-zinc-800`.
- Standard button padding: `px-3 py-1.5` for small, `px-4 py-2` for default.

## Testing

### Backend Tests

- Place tests in `api/tests/`.
- Use `pytest` with `pytest-asyncio` for async tests.
- Use `mocker` (pytest-mock) with `AsyncMock` for patching services and mocking HTTP calls.
- Reset global state in `conftest.py` fixtures — module-level singletons (caches, clients) need cleanup between tests. See the singleton reset section below.

### Singleton Reset in conftest.py

Every module-level singleton **must** have a corresponding reset in `api/tests/conftest.py`'s `_reset_global_state()` fixture. When you add or change a singleton, update conftest in the **same PR**.

**Why**: Module-level state persists across tests within a session. Without resets, test A's cached data leaks into test B, causing flaky passes or failures depending on test order.

**Singleton types and how to reset each:**

| Type | Pattern | Reset |
|------|---------|-------|
| TTLCache | `_cache = TTLCache(ttl=300, max_size=10)` | `mod._cache = TTLCache(ttl=300, max_size=10)` |
| Lazy client | `_client: Client \| None = None` | `mod._client = None` |
| File cache + mtime | `_file_cache = None` / `_file_mtime = 0.0` | `mod._file_cache = None` / `mod._file_mtime = 0.0` |
| Dict state | `_state: dict[str, Any] = {}` | `mod._state.clear()` |
| Counter | `_counter: int = 0` | `mod._counter = 0` |
| LRU cache | `@lru_cache` on `get_settings()` | `get_settings.cache_clear()` |

**For TTLCache resets**: Reconstruct with the same `ttl` and `max_size` as the source module. Import `TTLCache` from `api.services.cache` — don't hardcode magic numbers that could drift from the source.

**Checklist for any PR that touches singletons:**
1. New singleton added → add a reset block to conftest
2. Singleton parameters changed (TTL, max_size) → update the conftest reset to match
3. Singleton removed → remove the conftest reset block

### Test File Naming

- Test files: `test_{module_name}.py`
- Test functions: `test_{behavior_description}`
- Group related tests in the same file. One test file per logical module, not per function.
