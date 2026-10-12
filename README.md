# `agents-lib`

A modular open-source library that hosts focused, installable AI agents. Every agent shares the same interface, standard result format, and common infrastructure (LLM access, loaders, reporting).

## 🚀 Vision

- **Plug-and-play agents:** Adding a new agent takes hours, not days.
- **Multiple interfaces:** Run any agent via CLI, Python import, HTTP API, or generic/custom UI.
- **Structured output:** Results are strictly typed Pydantic models with human summaries and verifiable evidence.
- **Agent #1: `ai-code-detector`:** Analyzes repositories and codebases to estimate AI authorship likelihood and present concrete evidence.

---

## 📂 Repository Structure

This repository is structured as a `uv` workspace monorepo:

```text
agents-lib/
├── packages/
│   ├── core/                  # Shared base: BaseAgent, models, loaders, LLM clients, registry
│   ├── cli/                   # `agents` command-line interface
│   └── api/                   # FastAPI backend with async runs & SSE events
├── agents/
│   └── ai_code_detector/      # Agent #1: Heuristics + LLM judge for AI code detection
├── docs/                      # Architectural docs & developer guides
└── tests/                     # Workspace-level test suites & integration tests
```

---

## 🛠️ Getting Started

### Prerequisites

- Python `>= 3.11`
- [`uv`](https://github.com/astral-sh/uv) (fast Python package and project manager)

### Installation & Setup

1. Clone the repository and enter the directory:
   ```bash
   git clone https://github.com/your-org/agents-lib.git
   cd agents-lib
   ```

2. Sync workspace dependencies:
   ```bash
   uv sync
   ```

3. Copy environment configuration:
   ```bash
   cp .env.example .env
   ```

---

## 🧪 Development & Quality Checks

Run all checks locally before committing:

- **Lint & Format check:**
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
- **Type Checking:**
  ```bash
  uv run mypy
  ```
- **Run Tests:**
  ```bash
  uv run pytest
  ```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
