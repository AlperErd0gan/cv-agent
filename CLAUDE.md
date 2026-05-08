# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Docker (primary dev path)
```bash
bash start_app.sh          # build + start both services
docker-compose up --build  # same
```

### Backend (local, no Docker)
```bash
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000
```

### Frontend (local, no Docker)
```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
cd frontend && npm run lint
```

### Tests
```bash
cd backend && pytest tests/test_main.py              # all tests
cd backend && pytest tests/test_main.py::test_read_root  # single test
```

Tests set `DB_PATH=./test.db` and `PDF_PATH=./test.pdf` via env vars before import so they don't need `/data/`.

### One-shot watcher (for cron)
```bash
docker-compose run --rm backend python watcher.py --once
```

## Architecture

Two services communicate via HTTP and WebSocket. Ollama runs on the **host machine** (not in Docker).

```
[Browser] ──REST──▶ [FastAPI :8000] ──▶ [Ollama :11434 on host]
         ◀─WS──────                  ◀──
                          │
                       [SQLite cv_agent.db]
```

### Backend (`backend/`)

**`watcher.py`** — core logic, no FastAPI dependency:
- `process_cv()`: hash check → PDF text extract (pypdf) → diff against last DB entry → LLM prompt → `save_analysis()`
- `analyze()`: builds prompt with full CV text + unified diff + previous feedback (memory loop)
- `chat_with_cv()`: single-turn Q&A against CV text
- `Handler(FileSystemEventHandler)`: watchdog handler, debounced 1s, calls `process_cv()` on change
- `ON_ANALYSIS_COMPLETE`: module-level callback; `main.py` sets this to broadcast over WebSocket

**`main.py`** — FastAPI app:
- Runs `Handler` in a background daemon thread via `lifespan`; bridges thread→asyncio with `asyncio.run_coroutine_threadsafe`
- `ConnectionManager` broadcasts LLM results to all connected WebSocket clients
- `/upload` writes the PDF to `PDF_PATH` (watcher picks it up via file event)
- `/history` returns last 10 rows from SQLite
- `/chat` calls `chat_with_cv()` with latest CV text from DB

**SQLite schema** (`history` table): `id, timestamp, cv_hash, diff_text, llm_response, full_text`

### Frontend (`frontend/src/App.jsx`)

Single-component React app:
- Connects to `ws://localhost:8000/ws` on mount; incoming WS messages update `analysis` state and trigger history refresh
- Upload → POST `/upload` → sets `isProcessing=true` → waits for WS message to clear it
- Chat → POST `/chat` with `{message}` → appends AI response to `chatMessages`
- History items are raw DB tuples; `item[4]` = `llm_response` (5th column, 0-indexed)
- API URLs are hardcoded to `http://localhost:8000` (ignores `VITE_API_URL` env var)

### Key env vars

| Var | Default | Notes |
|-----|---------|-------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | In Docker: `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | `llama3` | docker-compose overrides to `llama3.2` |
| `PDF_PATH` | `/data/cv.pdf` | Monitored file; upload writes here |
| `DB_PATH` | `/data/cv_agent.db` | SQLite persistence |

### Diff truncation

`process_cv()` truncates diffs >10 000 chars to 12 000 chars before sending to LLM to avoid slow/bad responses on large rewrites.
