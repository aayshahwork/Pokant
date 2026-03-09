# CLAUDE.md — ComputerUse SDK

Developer reference for Claude Code (and human contributors). Covers architecture,
file responsibilities, key patterns, and commands needed to work on this codebase.

---

## Project Overview

ComputerUse is a Python SDK that lets you automate any web workflow with a single
`run_task()` call. It drives a Playwright browser via `browser-use` (an LLM agent
framework) and returns structured, typed output. It ships:

- **SDK** (`computeruse/`) — importable Python package, the primary deliverable
- **Backend** (`backend/`) — FastAPI cloud API + Celery workers for hosted execution
- **CLI** (`computeruse/cli/`) — `computeruse` terminal command
- **Examples** (`examples/`) — three runnable standalone scripts
- **Tests** (`tests/`) — pytest suite, 98 tests, no external services required

---

## Repository Layout

```
computeruse/
├── computeruse/               # Installable SDK package
│   ├── __init__.py            # Public API surface + __version__
│   ├── client.py              # ComputerUse — main entry point (sync wrapper)
│   ├── executor.py            # TaskExecutor — core async orchestration engine
│   ├── browser_manager.py     # BrowserManager — Playwright lifecycle + stealth mode
│   ├── session_manager.py     # SessionManager — cookies/localStorage persistence
│   ├── retry.py               # RetryHandler — exponential backoff + timeout
│   ├── validator.py           # OutputValidator — schema validation + LLM JSON parsing
│   ├── models.py              # Pydantic models: TaskConfig, TaskResult, StepData, SessionData
│   ├── exceptions.py          # Exception hierarchy rooted at ComputerUseError
│   ├── config.py              # Settings (pydantic-settings, loads from .env)
│   └── cli/
│       ├── __init__.py
│       └── main.py            # Click CLI: run / replay / sessions / version
│
├── backend/                   # Cloud API + async workers
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py            # FastAPI app: CORS, auth, CRUD task endpoints
│   ├── tasks.py               # Celery task: execute_task + upload_replay + webhooks
│   ├── db.py                  # asyncpg pool, DDL, task/api_key CRUD
│   ├── storage.py             # aioboto3 S3: upload/delete replays + screenshots
│   └── browser_provider.py    # BrowserbaseProvider — cloud browser REST + CDP
│
├── examples/
│   ├── example_login.py           # Login automation with session caching demo
│   ├── example_data_extraction.py # Structured data extraction with output_schema
│   └── example_form_submission.py # Form fill + submit + confirmation capture
│
├── tests/
│   ├── conftest.py            # sys.modules stubs for heavy deps; asyncio config
│   ├── test_retry.py          # RetryHandler — 31 tests
│   ├── test_validator.py      # OutputValidator — 38 tests
│   ├── test_session_manager.py # SessionManager — 29 tests
│   ├── test_executor.py       # (stub, ready for expansion)
│   └── __init__.py
│
├── Dockerfile                 # Multi-stage: builder → runtime (Chromium included)
├── docker-compose.yml         # app + celery + celery-beat + redis + postgres
├── .dockerignore
├── .env.example               # All supported env vars with placeholder values
├── .gitignore
├── pyproject.toml             # Poetry deps + pytest config
├── setup.py                   # setuptools fallback; entry_point for CLI
├── MANIFEST.in
├── README.md
└── LICENSE                    # MIT
```

---

## Architecture & Data Flow

### Local execution (default)

```
User calls cu.run_task(url, task, ...)
    │
    ▼
ComputerUse.run_task()          client.py       sync entry point
    │  asyncio.run() →
    ▼
ComputerUse._run_task_async()                   wraps in RetryHandler
    │
    ▼
TaskExecutor.execute()          executor.py     owns the run lifecycle
    ├── BrowserManager / browser_use.Browser    launch local Chromium
    ├── SessionManager.load_session()           restore cookies if credentials given
    ├── page.goto(url)
    ├── _execute_with_agent()                   runs browser-use Agent
    │       └── _on_agent_step() callback       captures StepData per action
    ├── _extract_output()                       LLM call to extract structured data
    ├── OutputValidator.validate_output()       type-coerce against output_schema
    ├── SessionManager.save_session()           persist cookies for next run
    └── _generate_replay()                      write replays/<task_id>.json
    │
    ▼
TaskResult returned to caller
    │
ComputerUse._cache_result()     client.py       write .tasks/<task_id>.json
```

### Cloud execution (local=False)

```
ComputerUse._call_cloud_api()   client.py
    │  POST /api/v1/tasks
    ▼
backend/api/main.py             FastAPI         validate, authenticate, enqueue
    │  celery .delay()
    ▼
backend/tasks.py                Celery worker   asyncio.run(executor.execute(...))
    ├── backend/db.py                           update status in Postgres
    ├── backend/storage.py                      upload replay to S3
    └── _fire_webhook()                         POST result to webhook_url
    │
client.py polls GET /api/v1/tasks/{id} until status ∈ {completed, failed}
```

---

## Module Reference

### `computeruse/models.py`
Four Pydantic v2 models. No internal imports.

| Model | Purpose |
|-------|---------|
| `TaskConfig` | Input: url, task, credentials, output_schema, limits |
| `TaskResult` | Output: status, success, result, error, replay paths, timing |
| `StepData` | One browser action: action_type, screenshot_path, timestamp |
| `SessionData` | Persisted session: cookies, localStorage, sessionStorage, expiry |

### `computeruse/exceptions.py`
All exceptions inherit from `ComputerUseError`. Every class overrides
`to_dict()` for JSON serialisation. `RetryExhaustedError` carries `last_error`.
`APIError` carries `status_code` and `response`.

| Exception | Retryable |
|-----------|-----------|
| `TimeoutError` | Yes |
| `BrowserError` | Yes (keyword-matched) |
| `APIError` (429/5xx) | Yes |
| `ValidationError` | **No** |
| `AuthenticationError` | **No** |
| `RetryExhaustedError` | — (terminal) |

### `computeruse/config.py`
`Settings` extends `pydantic_settings.BaseSettings`.
- `ANTHROPIC_API_KEY` is required; a placeholder-value validator rejects `"your_key_here"`.
- A singleton `settings` is exported — import this everywhere instead of instantiating `Settings` directly.
- `case_sensitive=True` — env var names must match exactly.

### `computeruse/retry.py`
`RetryHandler(max_attempts, base_delay, max_delay, backoff_factor)`

- `execute_with_retry(func, *args)` — non-retryable errors (`ValidationError`, `AuthenticationError`) are re-raised immediately without sleeping.
- `execute_with_timeout(func, timeout_seconds)` — wraps `asyncio.wait_for`, converts `asyncio.TimeoutError` → SDK `TimeoutError`.
- Delay formula: `min(base_delay * backoff_factor ** attempt, max_delay)`

### `computeruse/validator.py`
`OutputValidator` — stateless, instantiate once or use as a singleton.

- `validate_output(output, schema)` — coerces types, preserves unknown keys.
- `parse_llm_json(text)` — tries fenced code block first, then bare `{…}` scan.
- `validate_type(value, type_str)` — supports `str`, `int`, `float`, `bool`, `list`, `dict`, `list[T]`, `dict[str, T]`.
- **`bool` coercion is strict**: only `0`/`1` and `"true"`/`"false"` (and variants). Integer `42` raises.
- **`int` from `float`**: `1.0 → 1` allowed; `1.5 → int` raises.

### `computeruse/session_manager.py`
`SessionManager(storage_dir="./sessions")`

- Atomic writes: writes `.tmp` then renames (POSIX rename is atomic).
- `list_sessions()` reads the `"domain"` key from file contents, not the filename (lossless round-trip).
- Domain sanitisation: strips scheme, replaces non-alphanumeric chars with `_`, collapses runs.

### `computeruse/browser_manager.py`
`BrowserManager(headless, browserbase_api_key)`

- `setup_browser(use_cloud)` — cloud path calls `create_browserbase_session()` then `connect_over_cdp`.
- `configure_stealth_mode(context)` — registers an init script per context that patches `navigator.webdriver`, `navigator.plugins`, `navigator.languages`, `window.chrome`, `Notification.permission`.
- Owns `_playwright`; `close_browser()` stops it.

### `computeruse/executor.py`
`TaskExecutor(model, headless, browserbase_api_key)`

Key design points:
- Uses `browser_use.Browser` / `BrowserConfig` (not raw Playwright) as required by the `browser-use` library.
- `_execute_with_agent` registers `agent.register_action("*", self._on_agent_step)` as a wildcard step hook.
- `_extract_output` truncates page text to **8 000 chars** before the LLM extraction call.
- `_save_screenshot` zero-pads to 4 digits: `step_0001.png`.
- `_generate_replay` writes JSON; contains a `# TODO` stub for HTML renderer integration.
- A fresh `TaskExecutor` is created per `run_task` call — no shared mutable state between concurrent calls.

### `computeruse/client.py`
`ComputerUse(api_key, local, model, headless, browserbase_api_key)`

- `run_task()` is synchronous. Uses `_run_sync()` which handles both "no event loop" (calls `asyncio.run`) and "loop already running" (Jupyter: spawns a `ThreadPoolExecutor` worker).
- Local task results are cached to `.tasks/<task_id>.json` automatically.
- `list_tasks()` sorts by file `mtime` (newest first) — no separate index file.
- Cloud polling: `_POLL_INTERVAL = 2.0s`, `_CLOUD_POLL_TIMEOUT = 600s`.

### `computeruse/cli/main.py`
Click group `cli` with four commands.

| Command | Key behaviour |
|---------|---------------|
| `run` | `--no-headless` flag, `--schema` as JSON string, exits non-zero on failure |
| `replay` | `.json` → Rich table in terminal; `.html` → `webbrowser.open` |
| `sessions` | `--delete DOMAIN` for targeted removal |
| `version` | prints `__version__` |

Writes to `stderr` via a separate `err_console` so `stdout` stays clean for pipes.

### `backend/api/main.py`
FastAPI app with:
- CORS origins: `localhost:3000`, `localhost:8080`, `app.computeruse.dev`
- `verify_api_key` dependency: key must start with `"cu-"` and be ≥ 16 chars.
- In-memory `_task_store` dict (replace with `backend/db.py` calls in production).
- `POST /api/v1/tasks` returns **202 Accepted** (not 201 — the task hasn't run yet).
- `DELETE` marks `status="failed"` before removing so polling clients see a terminal state.

### `backend/tasks.py`
Celery app (`broker=redis`, `backend=redis`, `task_serializer="json"`).

- `task_acks_late=True` + `worker_prefetch_multiplier=1` — prevents task loss on worker crash; one browser process per worker slot.
- `soft_time_limit=600`, `time_limit=660` — SIGTERM then SIGKILL; both shorter than `_CLOUD_POLL_TIMEOUT`.
- Webhook delivery: linear retry (3 attempts, `2**attempt` sleep); failures are always swallowed.

### `backend/db.py`
asyncpg pool. Tables: `tasks` (JSONB request/result), `api_keys`.

- `_set_json_codec` registers Python `json` for both `json` and `jsonb` column types — asyncpg returns dicts directly.
- `update_task` builds a dynamic `SET` clause from a dict — no fixed-column update functions needed.
- `verify_api_key` uses `UPDATE … RETURNING` to check + update `last_used_at` in one round-trip.

### `backend/storage.py`
aioboto3 async S3 operations.

- Module-level `aioboto3.Session` — credentials resolved once at import time.
- `upload_replay` preserves extension (`.json` or `.html`).
- `delete_replay` deletes both variants since the format isn't tracked.
- `_list_keys` handles S3 pagination via continuation token loop.
- `_public_url` checks `AWS_CDN_BASE_URL` env var first; falls back to `s3.amazonaws.com`.

### `backend/browser_provider.py`
`BrowserbaseProvider(api_key)`

- Shared `_playwright` instance started on first `get_browser()` call.
- `close_session` treats 404 as non-fatal (session already expired).
- `list_sessions` normalises both `{"sessions": [...]}` and bare list API response shapes.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | — | Anthropic API key |
| `BROWSERBASE_API_KEY` | No | — | Cloud browser sessions |
| `OPENAI_API_KEY` | No | — | Optional model fallback |
| `DATABASE_URL` | No | `postgresql://localhost/computeruse` | Postgres DSN |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis for Celery |
| `AWS_ACCESS_KEY_ID` | No | — | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | No | — | S3 credentials |
| `AWS_BUCKET_NAME` | No | `computeruse-replays` | S3 bucket |
| `AWS_REGION` | No | `us-east-1` | S3 region |
| `AWS_CDN_BASE_URL` | No | — | CloudFront base URL |
| `DEFAULT_MODEL` | No | `claude-sonnet-4-5` | Anthropic model ID |
| `DEFAULT_TIMEOUT` | No | `300` | Task timeout (seconds) |
| `DEFAULT_MAX_STEPS` | No | `50` | Max browser actions |
| `SESSION_DIR` | No | `./sessions` | Local session store |
| `REPLAY_DIR` | No | `./replays` | Local replay store |

---

## Commands

### Development

```bash
# Install (Poetry)
poetry install

# Install Playwright browser
poetry run playwright install chromium

# Copy env template
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY

# Run all tests (no API key or browser required)
poetry run pytest

# Run specific test file verbosely
poetry run pytest tests/test_retry.py -v

# Run a single test
poetry run pytest tests/test_validator.py::TestParseLLMJson::test_markdown_json_block -v

# Format
poetry run black computeruse/ tests/

# Type check
poetry run mypy computeruse/
```

### CLI

```bash
# Basic task
computeruse run --url https://news.ycombinator.com --task "Get top 5 titles" \
  --schema '{"titles":"list[str]"}'

# Visible browser (debugging)
computeruse run --url https://example.com --task "…" --no-headless

# Authenticated task
computeruse run --url https://github.com/login --task "Star repo X" \
  --username alice --password hunter2

# Inspect a replay
computeruse replay replays/abc123.json

# List + delete sessions
computeruse sessions
computeruse sessions --delete github.com

# Version
computeruse version
```

### Docker

```bash
# Start all services
docker-compose up --build

# API only (no workers)
docker-compose up app redis postgres

# With Celery Beat scheduler
docker-compose --profile scheduler up

# Start worker separately (scale to 3)
docker-compose up --scale celery=3

# View logs
docker-compose logs -f celery

# Tear down (keep volumes)
docker-compose down

# Tear down + wipe all data
docker-compose down -v
```

### API server (without Docker)

```bash
# Start FastAPI
uvicorn backend.api.main:app --reload --port 8000

# Start Celery worker
celery -A backend.tasks worker --loglevel=info --concurrency=2

# Celery dashboard (Flower)
celery -A backend.tasks flower --port=5555
```

---

## Testing Architecture

The test suite runs with **no external services** (no Playwright, no Anthropic API,
no S3, no Postgres).

`tests/conftest.py` stubs seven packages in `sys.modules` before collection:
`anthropic`, `browser_use`, `playwright`, `langchain_anthropic`, `aiohttp`,
`httpx`, `pydantic_settings`. The stub approach (vs mocking at the function level)
is necessary because these packages are imported at module scope in SDK files.

`asyncio_mode = "auto"` is set in `pyproject.toml` — every `async def test_*`
runs as an asyncio coroutine automatically without `@pytest.mark.asyncio`.

```
tests/
├── conftest.py          sys.modules stubs + pytest asyncio config
├── test_retry.py        RetryHandler: backoff math, retryable classification,
│                        timeout wrapping, constructor validation
├── test_validator.py    OutputValidator: type coercion, bool strictness,
│                        JSON parsing, nested types, schema formatting
└── test_session_manager.py  SessionManager: round-trip save/load, atomic writes,
                             sanitisation helpers, list/delete operations
```

---

## Key Patterns

**Async from sync** — `client.py:_run_sync()` handles both "no loop" and "loop
already running" (Jupyter) cases. New code that needs to call async from sync
should use this helper rather than calling `asyncio.run()` directly.

**Exception hierarchy** — always raise SDK exceptions (`ComputerUseError` subtypes),
never raw `ValueError` or `RuntimeError`, so callers can catch by type. Wrap
third-party exceptions at the boundary with `raise SDKError(…) from exc`.

**Per-call executor** — `TaskExecutor` is instantiated fresh per `run_task` call
in `client.py:_local_execute`. Never store it on `self` or share it across calls.

**Atomic file writes** — `session_manager.py` and any other code that writes JSON
state files must use the write-to-`.tmp`-then-rename pattern to prevent corrupt
files on process crash.

**JSONB columns** — `backend/db.py` registers a custom asyncpg codec. Pass Python
dicts/lists directly; do **not** call `json.dumps` before passing to asyncpg queries
for `jsonb` columns (the codec handles it).

**S3 ACL** — uploads use `ACL="public-read"`. If the AWS account has Block Public
Access enabled, uploads will fail. Either disable BPA on the bucket or switch to
pre-signed URLs and update `_public_url()`.

---

## Adding a New Feature

1. **New model field** → edit `computeruse/models.py`. Pydantic v2 — use `Field(...)`.
2. **New exception** → inherit from `ComputerUseError`, override `to_dict()` if it
   carries extra fields, add to `computeruse/__init__.py` exports.
3. **New config variable** → add to `Settings` in `config.py`, add to `.env.example`,
   document in the table above.
4. **New CLI command** → add `@cli.command()` in `computeruse/cli/main.py`.
5. **New API endpoint** → add to `backend/api/main.py`. Follow the 202/200/404/403
   status code conventions already established.
6. **New test** → import directly from the submodule (`from computeruse.retry import …`),
   not from the package root, and add heavy deps to the stubs in `conftest.py` if needed.
