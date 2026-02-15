# CV Analysis Agent (Local LLM)

This is an intelligent agent that monitors your CV PDF files for changes and provides instant, AI-powered feedback using a local LLM (Ollama).

## Features

- **100% Privacy**: Uses a local LLM via Ollama. Your personal data never leaves your computer.
- **Real-time Monitoring**: Automatically detects when you save your PDF and immediately analyzes changes.
- **Dockerized**: Runs in a sandboxed container for easy management.
- **Automation Ready**: Includes a "run-once" mode perfect for weekly scheduled checks.

## Prerequisites

1. Docker Desktop installed.
2. Ollama installed and running on your host machine.

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/AlperErd0gan/cv-agent.git
   cd cv-agent
   ```

2. Pull the required model:
   ```bash
   ollama pull llama3.2
   ```

3. Build and Start the Agent:
   ```bash
   docker-compose up --build
   ```

## Usage

### 1. Start the Application
Run the helper script to build and start both Backend and Frontend:
```bash
bash start_app.sh
```
*(Alternatively: `docker-compose up --build`)*

### 2. Access the Interface
Open your browser and verify the connection:
- **Web UI**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:8000](http://localhost:8000)

### 3. Trigger Analysis
Simply save your new cv `cv.pdf`.
- The interface will update automatically .
- Previous analyses are stored in "History".

## Weekly Scheduling (Cron)

If you want you can use cron to run this application weekly to get insights from your cv.
```bash
docker-compose run --rm backend python watcher.py --once
```
*(Cron config remains the same, just point to the backend service)*


## Running Tests

To run the backend unit tests:

1. Install test dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

2. Run tests using pytest:
   ```bash
   cd backend
   pytest tests/test_main.py
   ```


## Roadmap

1. **Add Memory (State)**: Implement a database to track feedback over time, allowing the agent to remember past critiques.
2. **Change Architecture to ReAct Loop**: Evolve the system from a simple trigger-action tool to an autonomous agent that can plan, search, and verify its own suggestions.
3. **Add Web Interface**: Create a web interface to interact with the agent. (React + FastAPI)

## Configuration

You can adjust settings in `docker-compose.yml`:
- `OLLAMA_MODEL`: Change to `llama3`, `gemma2`, or `mistral`.
- `CPUS` / `MEMORY`: Adjust resource limits (Default: 2 CPUs, 4GB RAM).

## License

MIT License.
