# CV Agent — Multi-Agent AI CV Analyzer

Local AI-powered CV analysis using a multi-agent pipeline. Four specialist agents analyze different aspects of your CV in parallel, then a synthesis agent combines their findings into a prioritized report. Runs 100% locally via Ollama — no data leaves your machine.

## Architecture

```
Upload CV (PDF)
      │
      ▼
  Watcher detects change
      │
      ├──────────────────────────────────────┐
      │  (parallel)                          │
      ▼                ▼                     ▼
ContentQualityAgent  ATSAgent          DiffAnalyzerAgent
  - weak phrases     - keyword scan    - parse added/removed lines
  - quantification   - missing skills  - intent detection
      │                │                     │
      └────────────────┴─────────────────────┘
                       │
                       ▼
             StrategicAdvisorAgent
               (sequential, uses all context + memory)
                       │
                       ▼
             Synthesizer (final LLM pass)
                       │
                  WebSocket broadcast → Browser
```

Each agent runs deterministic Python tools first (regex/hash/diff parsing), then passes structured results to the LLM. This produces more focused, grounded responses than a single monolithic prompt.

## Features

- **Multi-Agent Pipeline**: 4 specialist agents + synthesizer, each with their own tools and focus area
- **Real-time Streaming**: Agent cards appear in the UI as each agent completes
- **Memory Loop**: Previous analysis is passed to `StrategicAdvisorAgent` on each run
- **Chat with CV**: Q&A against the current CV content
- **History**: Last 10 analyses stored in SQLite, browsable in the sidebar
- **100% Local**: Ollama runs on the host machine — no external API calls

## Prerequisites

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. [Ollama](https://ollama.com) installed and running on the host machine

## Setup

```bash
git clone https://github.com/AlperErd0gan/cv-agent.git
cd cv-agent
ollama pull llama3.2
bash start_app.sh
```

Then open:
- **Web UI**: http://localhost:5173
- **Backend API**: http://localhost:8000

## Usage

1. Upload a CV PDF via the web UI or drop `cv.pdf` into the project root
2. The watcher detects the change and starts the multi-agent pipeline
3. Agent cards stream into the UI as each specialist finishes
4. A synthesized final report appears when all agents complete
5. Chat with your CV using the chat panel on the right

## Agents

| Agent | Tools Used | Focus |
|-------|-----------|-------|
| **Content Quality** | weak phrase detector, bullet quantification counter | Writing strength, verb quality, achievement metrics |
| **ATS Optimization** | tech keyword scanner (30+ keywords) | Keyword presence, missing skills, formatting issues |
| **Diff Analyzer** | unified diff parser (added/removed lines) | Change intent, regressions, consistency |
| **Strategic Advisor** | (memory from previous feedback) | Seniority targeting, highest-impact next step |
| **Synthesizer** | all agent reports | Final prioritized report with Top 3 fixes |

## Configuration

Set these in `docker-compose.yml`:

| Variable | Default | Notes |
|----------|---------|-------|
| `OLLAMA_MODEL` | `llama3.2` | Any Ollama model (e.g. `llama3`, `gemma2`, `mistral`) |
| `PDF_PATH` | `/host_data/cv.pdf` | Path the watcher monitors |
| `DB_PATH` | `/host_data/cv_agent.db` | SQLite database path |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama endpoint |

## Running Tests

```bash
pip install -r backend/requirements.txt
cd backend
pytest tests/test_main.py          # all tests
pytest tests/test_main.py::test_read_root  # single test
```

## One-Shot Mode (Cron)

```bash
docker-compose run --rm backend python watcher.py --once
```

## Stack

- **Backend**: FastAPI + LangChain Ollama + watchdog + SQLite
- **Frontend**: React 19 + Vite + react-markdown
- **LLM**: Ollama (local)
- **Containerization**: Docker Compose

## License

MIT
