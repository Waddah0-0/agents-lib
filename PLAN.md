# AI Agents Library: Project Plan

> Working name: `agents-lib` (rename freely). This document is the source of truth for the whole project.
> It is written to be fed to a coding assistant (Antigravity) **one phase at a time**.

---

## 0. Vision

A single open-source library that hosts many small, focused, installable AI agents.
Every agent shares the same interface, the same result format, and the same infrastructure (LLM access, loaders, reporting), so that:

- adding a new agent takes hours, not days;
- any agent can be run from a **CLI**, a **Python import**, an **HTTP API**, or a **UI**;
- the output is always **structured** (never just free text), so a generic UI can render any agent.

**First agent:** `ai-code-detector` — given a GitHub repo or local files, estimates how likely the code is AI-generated and *shows its evidence*.

### Non-goals (for now)
- No auth, billing, or multi-tenant hosting.
- No agent marketplace / plugin store.
- No fine-tuned models. Use existing LLM APIs.
- No claim of "100% accurate" detection (see Section 7.1).

---

## 1. Repository strategy

### 1.1 Decision: ONE monorepo, "sub-repos" are packages

Literal separate repos (or git submodules) create pain: version drift, duplicated CI, hard-to-share code, and painful cross-repo refactors.

So:

- **One GitHub repo** = the library.
- **Each agent = a self-contained package folder** inside it (this is what you'd call a "sub-repo").
- Each agent has its own `pyproject.toml`, README, tests, and version, and can be **published/installed independently** (e.g. `pip install agents-lib-ai-code-detector`).
- Shared code lives in `core/`.

If you later want a standalone repo for one agent, you can extract it with `git subtree split` and nothing breaks, because agents only depend on `core`'s public interface.

### 1.2 Directory layout

```
agents-lib/
├── README.md
├── PLAN.md                         # this file
├── LICENSE
├── pyproject.toml                  # workspace root (uv workspace)
├── uv.lock
├── .github/
│   └── workflows/
│       ├── ci.yml                  # lint + type-check + tests on PR
│       └── release.yml             # publish packages on tag
├── docs/
│   ├── architecture.md
│   ├── writing-an-agent.md         # tutorial: add your own agent
│   └── result-schema.md
│
├── packages/
│   ├── core/                       # shared foundation (PyPI: agents-lib-core)
│   │   ├── pyproject.toml
│   │   ├── src/agents_core/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py            # BaseAgent abstract class
│   │   │   ├── models.py           # Pydantic: AgentInput, AgentResult, Evidence, Finding
│   │   │   ├── registry.py         # discovers installed agents (entry points)
│   │   │   ├── llm/
│   │   │   │   ├── base.py         # LLMClient interface
│   │   │   │   ├── anthropic.py
│   │   │   │   ├── openai.py
│   │   │   │   └── mock.py         # deterministic client for tests
│   │   │   ├── loaders/
│   │   │   │   ├── base.py         # Loader interface -> Workspace
│   │   │   │   ├── github.py       # clone / GitHub API
│   │   │   │   ├── local.py        # folder or list of files
│   │   │   │   └── filters.py      # ignore lockfiles, vendored, minified, binary
│   │   │   ├── reporting/
│   │   │   │   ├── json_report.py
│   │   │   │   └── markdown_report.py
│   │   │   ├── config.py           # env + settings (pydantic-settings)
│   │   │   └── logging.py
│   │   └── tests/
│   │
│   ├── cli/                        # `agents` command (PyPI: agents-lib-cli)
│   │   ├── pyproject.toml
│   │   └── src/agents_cli/main.py  # typer app
│   │
│   └── api/                        # HTTP server (PyPI: agents-lib-api)
│       ├── pyproject.toml
│       └── src/agents_api/
│           ├── main.py             # FastAPI app
│           ├── routes.py           # /agents, /agents/{id}/run, /runs/{id}
│           └── jobs.py             # background job runner + status
│
├── agents/                         # <<< the "sub-repos"
│   └── ai_code_detector/
│       ├── pyproject.toml
│       ├── README.md
│       ├── src/ai_code_detector/
│       │   ├── __init__.py
│       │   ├── agent.py            # class AICodeDetector(BaseAgent)
│       │   ├── models.py           # agent-specific output models
│       │   ├── pipeline.py         # ingest -> signals -> judge -> aggregate
│       │   ├── signals/
│       │   │   ├── base.py         # Signal interface
│       │   │   ├── ai_config_files.py
│       │   │   ├── commit_trailers.py
│       │   │   ├── commit_shape.py
│       │   │   ├── comment_density.py
│       │   │   ├── naming_patterns.py
│       │   │   ├── readme_patterns.py
│       │   │   └── perplexity.py   # optional, phase 3+
│       │   ├── judge/
│       │   │   ├── llm_judge.py
│       │   │   ├── sampler.py      # which files to send to the LLM
│       │   │   └── prompts/
│       │   │       └── judge_v1.md
│       │   └── aggregate.py
│       ├── tests/
│       │   ├── fixtures/           # tiny labeled sample repos
│       │   └── ...
│       └── eval/                   # evaluation harness (see Section 7.6)
│
├── ui/                             # built LAST (Phase 6+)
│   ├── library-ui/                 # generic UI: lists agents, runs any of them
│   └── agent-uis/
│       └── ai-code-detector/       # custom visualization for this agent
│
└── examples/
    ├── run_detector.py
    └── custom_agent.py
```

### 1.3 Tooling decisions

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Best LLM SDK + data ecosystem |
| Package manager | `uv` with workspaces | Fast; supports a monorepo of packages natively |
| Data models | Pydantic v2 | Validated structured output, JSON schema for free |
| CLI | Typer | Minimal boilerplate |
| API | FastAPI | Auto OpenAPI docs; the UI can generate a client from it |
| Lint / format | Ruff | One tool |
| Types | mypy (strict on `core`) | Keeps the shared interface honest |
| Tests | pytest + pytest-asyncio | Standard |
| UI (later) | React/Next.js + TypeScript | Consumes the OpenAPI schema |
| Git ops | `git` CLI via subprocess, plus GitHub REST API for metadata | Reliable and simple |

---

## 2. Core architecture

### 2.1 The Agent contract

Every agent implements one interface. This is the most important design decision in the project.

```python
# packages/core/src/agents_core/agent.py
from abc import ABC, abstractmethod
from pydantic import BaseModel


class BaseAgent(ABC):
    id: str  # "ai-code-detector"
    name: str  # "AI Code Detector"
    description: str
    version: str
    InputModel: type[BaseModel]  # what the agent accepts
    OutputModel: type[BaseModel]  # what the agent returns

    def __init__(self, llm: "LLMClient | None" = None, config: dict | None = None): ...

    @abstractmethod
    async def run(self, input: BaseModel, ctx: "RunContext") -> "AgentResult": ...
```

`RunContext` carries: the LLM client, a progress callback (so UIs can show progress), a cancellation token, and a logger.

### 2.2 Standard result format

All agents return an `AgentResult`:

```python
class Evidence(BaseModel):
    kind: str  # "file", "commit", "config", "metric"
    location: str | None  # "src/utils.py:10-42" or commit SHA
    detail: str  # human-readable explanation
    weight: float | None  # contribution to the score, if applicable


class Finding(BaseModel):
    title: str
    severity_or_score: float | None
    summary: str
    evidence: list[Evidence]


class AgentResult(BaseModel):
    agent_id: str
    agent_version: str
    status: Literal["ok", "partial", "error"]
    summary: str  # 2-3 sentence human summary
    data: dict  # validated against the agent's OutputModel
    findings: list[Finding]
    warnings: list[str]
    metadata: RunMetadata  # duration, model used, token usage, cost estimate
```

**Why this matters:** a generic UI can render `summary`, `findings`, and `evidence` for *any* agent without knowing anything about it. Agent-specific UIs can additionally use `data`.

### 2.3 Plugin discovery

Agents register through Python **entry points**, so installing a package makes it appear automatically:

```toml
# agents/ai_code_detector/pyproject.toml
[project.entry-points."agents_lib.agents"]
ai-code-detector = "ai_code_detector.agent:AICodeDetector"
```

`registry.py` reads that group and exposes `list_agents()` / `get_agent(id)`. The CLI and API only talk to the registry, so adding an agent never requires editing them.

### 2.4 Loaders and the Workspace abstraction

Agents shouldn't care whether code came from GitHub or disk. Loaders produce a `Workspace`:

```python
class Workspace:
    root: Path  # local directory with the files
    files: list[FileInfo]  # path, size, language, is_generated, is_vendored
    git: GitInfo | None  # commit log access, if it's a git repo
    source: str  # original URL or path
```

Loader rules:
- GitHub: shallow-ish clone (but **full history of commit metadata is needed** for commit signals; use `--filter=blob:none` to fetch history cheaply), to a temp dir, cleaned up afterwards.
- Enforce limits: max repo size, max file count, max file size, clone timeout. Fail with a clear error.
- Default ignore list: lockfiles, `node_modules`, `vendor`, `dist`, `build`, minified files, binaries, images, generated protobuf/etc.

### 2.5 LLM abstraction

- One `LLMClient` interface with `complete(...)` and `complete_structured(schema, ...)`.
- Implementations: Anthropic, OpenAI, and a `MockLLM` that returns canned responses (required so tests never hit the network).
- Built-in: retries with backoff, timeouts, token/cost tracking, and a hard per-run budget cap (e.g. `max_cost_usd`) so a big repo can't surprise you with a bill.

### 2.6 Interfaces on top of the core

```
              +-----------+      +-----------+      +-------------+
              |   CLI     |      |  HTTP API |      | Python import|
              +-----+-----+      +-----+-----+      +------+------+
                    \                  |                  /
                     \                 |                 /
                      +----------- Registry -------------+
                                       |
                               BaseAgent.run(...)
                                       |
                    +------------------+------------------+
                    |                  |                  |
                 Loaders             LLM client        Reporting
```

CLI examples:
```
agents list
agents run ai-code-detector https://github.com/user/repo --format markdown
agents run ai-code-detector ./local/path --format json --out report.json
```

API endpoints:
```
GET  /agents                      -> list agents + their input JSON schemas
POST /agents/{id}/runs            -> start a run, returns run_id
GET  /runs/{run_id}               -> status, progress, result when done
GET  /runs/{run_id}/events        -> SSE stream of progress events
```
Runs are asynchronous because cloning and LLM calls take a while.

---

## 3. Conventions (give these to Antigravity)

1. **Everything async** at the agent boundary (`async def run`).
2. **No network in unit tests.** Use `MockLLM` and local fixture repos.
3. **Agents never import from other agents.** Only from `agents_core`.
4. **Every public model is Pydantic.** No loose dicts crossing module boundaries.
5. **Every signal and every prompt is versioned** (`judge_v1.md`) so results are reproducible.
6. **Type hints everywhere**; `mypy --strict` passes on `core`.
7. **Small PRs per task** from the checklists below; run `ruff`, `mypy`, `pytest` before each commit.
8. **Conventional commits** (`feat:`, `fix:`, `docs:`, ...).
9. **Secrets** only via environment variables, never committed. Provide `.env.example`.

---

## 4. Phased roadmap (whole project)

| Phase | Goal | Deliverable | Done when |
|---|---|---|---|
| 0 | Repo skeleton | uv workspace, CI, lint, empty packages | `uv sync && pytest` passes on empty tests |
| 1 | Core foundation | models, BaseAgent, registry, loaders, LLM clients, reporting | A dummy "echo agent" runs end-to-end through registry |
| 2 | CLI | `agents list` / `agents run` | Echo agent runs from terminal, JSON + Markdown output |
| 3 | AI Code Detector MVP | heuristic signals + report (no LLM yet) | Detector runs on a real repo and produces evidence-based report |
| 4 | LLM judge + aggregation | sampling, structured judging, calibrated score | Detector beats the baseline on the eval set (Section 7.6) |
| 5 | HTTP API | FastAPI, async runs, SSE progress | Can start and poll a run via curl |
| 6 | Library UI | generic UI that lists agents and renders any result | Run the detector from the browser |
| 7 | Detector UI | custom visualization (heatmap, timeline) | Evidence is explorable per file/commit |
| 8 | Hardening + release | docs, versioning, PyPI publish, examples | Tagged `v0.1.0`, installable from PyPI |
| 9+ | New agents | one package per idea | Each reuses `core` with ~no changes to it |

Rule: **don't start Phase 6 before Phase 4 works.** A beautiful UI on a bad detector is wasted effort.

---

## 5. Phase checklists (core / platform)

### Phase 0: Skeleton
- [x] Create repo, `LICENSE` (MIT or Apache-2.0), `README.md`, `.gitignore`, `.env.example`
- [x] `uv` workspace root `pyproject.toml` listing `packages/*` and `agents/*`
- [x] Empty packages: `core`, `cli`, `api`, `agents/ai_code_detector`
- [x] Ruff + mypy + pytest configured at the root
- [x] GitHub Actions: lint, type-check, test on every PR (matrix: Python 3.11, 3.12)
- [x] Pre-commit hooks (ruff, trailing whitespace)

### Phase 1: Core
- [ ] `models.py`: `AgentInput`, `AgentResult`, `Finding`, `Evidence`, `RunMetadata`
- [ ] `agent.py`: `BaseAgent`, `RunContext`
- [ ] `registry.py`: entry-point discovery + tests with a fake agent package
- [ ] `loaders/local.py` + `filters.py` (with tests for every ignore rule)
- [ ] `loaders/github.py` (clone with limits; test against a tiny public repo or a local bare repo fixture)
- [ ] `llm/base.py`, `llm/mock.py`, `llm/anthropic.py`, `llm/openai.py` (retry, timeout, cost tracking, budget cap)
- [ ] `reporting/json_report.py`, `reporting/markdown_report.py`
- [ ] `examples/custom_agent.py` + `docs/writing-an-agent.md`

### Phase 2: CLI
- [ ] `agents list`, `agents run <id> <target>`, `--format`, `--out`, `--model`, `--max-cost`
- [ ] Progress display (rich) driven by the `RunContext` progress callback
- [ ] Non-zero exit codes on error; readable error messages

### Phase 5: API
- [ ] FastAPI app, routes as in Section 2.6
- [ ] In-memory job store first (SQLite later if needed)
- [ ] SSE progress stream
- [ ] CORS config, request size limits, input validation from the agent's `InputModel`
- [ ] OpenAPI schema exported to `ui/` to generate a typed client

### Phase 6: Library UI
- [ ] Agents list page (from `GET /agents`)
- [ ] Auto-generated input form from each agent's JSON schema
- [ ] Run page with live progress
- [ ] Generic result viewer: summary, findings, expandable evidence, raw JSON tab, export buttons

### Phase 8: Release
- [ ] Per-package versioning + changelog
- [ ] `release.yml` publishes to PyPI on tag
- [ ] Docs site (mkdocs-material) or a well-organized `docs/`
- [ ] Security review: clone sandboxing, SSRF on URLs, rate limits, secret handling

---

## 6. UI strategy

**Principle:** the UI is a *client* of the API. It never imports agent code.

1. **Library UI (generic).** Works for every agent using only the standard `AgentResult` and the agent's JSON schema. This is what makes "add a new agent" nearly free on the UI side.
2. **Agent UIs (custom).** Optional, per agent, for visualizations the generic viewer can't do. They consume the agent's `data` field.
3. **Plugin pattern:** the library UI looks up `agent_id` in a small map of custom views; if there's none, it falls back to the generic viewer.

Stack suggestion: Next.js + TypeScript + Tailwind, typed client generated from the FastAPI OpenAPI schema (`openapi-typescript`).

---

## 7. Agent #1: AI Code Detector

### 7.1 Purpose and honest limits

Estimate **how likely** a codebase (or parts of it) was AI-assisted, and show the evidence.

Be upfront about limits, in the README and in the UI:
- There is no reliable way to prove code is AI-generated. Clean human code can look "AI-like"; edited AI code can look human.
- The output is a **probability range with evidence**, never a verdict. No "87% AI" headline without the reasons beside it.
- It must not be used as the sole basis for accusing someone (students, contractors, job candidates).
- Report **confidence** separately from **score** (few signals available = low confidence).

### 7.2 Input / Output

**Input**
```python
class DetectorInput(BaseModel):
    target: str  # GitHub URL, local path
    paths: list[str] | None = None  # restrict to specific files/dirs
    branch: str | None = None
    use_llm_judge: bool = True
    max_files_for_judge: int = 30
    max_cost_usd: float = 1.0
```

**Output (`data` field)**
```python
class FileScore(BaseModel):
    path: str
    score: float  # 0..1, likelihood of AI involvement
    signals: list[SignalHit]  # which signals fired and why
    judge: JudgeVerdict | None


class DetectorOutput(BaseModel):
    repo_score: float  # 0..1
    confidence: Literal["low", "medium", "high"]
    score_range: tuple[float, float]  # e.g. (0.55, 0.80)
    repo_level_signals: list[SignalHit]
    files: list[FileScore]
    files_analyzed: int
    files_skipped: int
    methodology_version: str
```

The standard `AgentResult.findings` is also populated (top evidence for and *against* AI authorship) so the generic UI works.

### 7.3 Pipeline

```
 target
   |
   v
[1 Ingest]     load repo -> Workspace (filters applied)
   |
   v
[2 Repo-level signals]    config files, commit trailers, commit history shape, README
   |
   v
[3 File-level signals]    comment density, naming, boilerplate, uniformity (per file)
   |
   v
[4 Select sample]         choose the most informative N files for the LLM judge
   |
   v
[5 LLM judge]             structured verdict per file with quoted evidence
   |
   v
[6 Aggregate]             combine signals + judge -> file scores -> repo score + confidence
   |
   v
[7 Report]                AgentResult (JSON + Markdown)
```

### 7.4 Signals catalog

Each signal implements:

```python
class Signal(ABC):
    id: str
    scope: Literal["repo", "file"]
    direction: Literal["toward_ai", "toward_human", "both"]

    @abstractmethod
    def evaluate(self, ws: Workspace, file: FileInfo | None) -> list[SignalHit]: ...


class SignalHit(BaseModel):
    signal_id: str
    strength: float  # -1..+1 (negative = evidence for human authorship)
    explanation: str
    evidence: list[Evidence]
```

**Repo-level signals (cheap, often strongest)**

| Signal | What it checks | Direction |
|---|---|---|
| `ai_config_files` | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `.cursor/`, `.github/copilot-instructions.md`, `.windsurfrules`, `.aider*`, Antigravity/agent config dirs | toward AI (strong, but only proves *usage*, not extent) |
| `commit_trailers` | `Co-authored-by:` from AI tools, "Generated with ..." lines, bot authors | toward AI (strong) |
| `commit_shape` | giant first commit with a complete project; many files added within minutes; commit size distribution | toward AI (medium) |
| `commit_message_style` | very uniform, templated messages; conventional-commit perfection across all commits | toward AI (weak) |
| `history_depth` | long, messy, irregular history with reverts, typo fixes, WIP commits | toward human (medium) |
| `readme_patterns` | emoji section headers, boilerplate "Features / Installation / Contributing / License" template, marketing tone | toward AI (weak) |

**File-level signals**

| Signal | What it checks | Direction |
|---|---|---|
| `comment_density` | comments/docstrings per line; docstring on every trivial function | toward AI (medium) |
| `restating_comments` | comments that merely repeat the next line ("# increment counter") | toward AI (medium) |
| `naming_patterns` | overly descriptive, uniform, generic names (`process_data`, `handle_request`, `result_list`) | toward AI (weak) |
| `uniformity` | unusually consistent formatting/structure across files; absence of any idiosyncrasy | toward AI (weak) |
| `defensive_boilerplate` | blanket try/except, redundant validation, excessive logging | toward AI (weak) |
| `idiosyncrasy` | TODOs with names, odd hacks, inconsistent style, personal shorthand, domain-specific jargon | toward human (medium) |
| `dead_or_debug_code` | commented-out blocks, `print("here")`, leftover debug code | toward human (weak) |
| `perplexity` *(optional, Phase 4+)* | token log-prob under a local model; very low perplexity = very predictable | toward AI (weak, noisy) |

> Each signal's thresholds must be **configurable and calibrated against the eval set**, not guessed. Language-specific logic goes in per-language helpers (start with Python + JS/TS; use `tree-sitter` for language-agnostic parsing).

### 7.5 LLM judge

**Sampling (`judge/sampler.py`)**
- Skip tiny files, configs, and tests-only boilerplate.
- Prefer files that are large enough to show style but small enough to fit; mix high-signal and low-signal files so the judge also sees "clean human" candidates.
- Respect `max_files_for_judge` and `max_cost_usd`.

**Prompt design (`prompts/judge_v1.md`)**
- Give a rubric (the same observable features as the signals plus others) and **forbid** guessing from topic alone.
- Require the model to quote specific lines as evidence, and to list evidence *against* its own conclusion.
- Provide commit context for the file when available.
- Force a strict JSON schema:

```python
class JudgeVerdict(BaseModel):
    likelihood_ai: float  # 0..1
    confidence: float  # 0..1
    evidence_for: list[QuotedEvidence]  # {line_range, quote, why}
    evidence_against: list[QuotedEvidence]
    uncertainty_notes: str
```

**Anti-bias measures**
- Judge each file independently (no anchoring on previous verdicts).
- Run a small subset twice with shuffled rubric order and measure agreement; report low agreement as lower confidence.
- Never reveal the signal scores to the judge, so the two stay independent sources of evidence.

### 7.6 Aggregation and calibration

- File score = weighted combination of signal strengths + judge likelihood (start with logistic regression or a hand-tuned weighted sum; **fit weights on the eval set**).
- Repo score = weighted mean of file scores (weight by file size/importance) combined with repo-level signals.
- **Confidence** is derived from: number of independent signals that fired, judge confidence, judge agreement, and repo size. Few signals or high disagreement => "low".
- Output a **range**, not just a point estimate.
- Special handling: if a strong explicit marker exists (AI co-author trailer), report it as **"AI tool usage confirmed by metadata"** separately from the statistical score.

### 7.7 Evaluation harness (`eval/`): do this early

Without this you're guessing.

- Build a labeled dataset:
  - **Human:** repos/files from before ~2021 (pre-LLM era), from reputable OSS projects.
  - **AI:** projects you generate yourself with different tools/models/prompts (and with different amounts of human editing).
  - **Mixed:** AI output that you hand-edit by varying degrees.
- Script: `python -m eval.run --dataset eval/data` computes precision/recall/AUC, a calibration plot, and per-signal ablations (remove one signal, see what happens).
- Track metrics per release so changes are measurable. Treat a regression as a failing CI check once the dataset is stable.
- Watch for **false positives on clean human code** more than false negatives; falsely accusing someone is the worse failure.

### 7.8 Detector checklists

**Phase 3: MVP (no LLM)**
- [ ] `Signal` base class + `SignalHit` model
- [ ] `ai_config_files` signal + tests
- [ ] `commit_trailers` signal + tests (use a fixture repo created with `git` in the test setup)
- [ ] `commit_shape` signal
- [ ] `comment_density` + `restating_comments` for Python
- [ ] `aggregate.py` v0: simple weighted sum, confidence from signal count
- [ ] `AICodeDetector` agent wired through `pipeline.py`
- [ ] Markdown report with "evidence for / evidence against" sections
- [ ] Runs from the CLI against a real public repo

**Phase 4: LLM judge + calibration**
- [ ] `sampler.py`
- [ ] `judge_v1.md` prompt + `JudgeVerdict` schema + `llm_judge.py`
- [ ] Cost tracking and budget cutoff
- [ ] Judge agreement check (double-run on a subset)
- [ ] Eval dataset (at least ~30 human and ~30 AI/mixed samples to start)
- [ ] `eval/run.py` metrics + ablations
- [ ] Fit/tune aggregation weights on the eval set (hold out a test split)
- [ ] Add JS/TS support to file-level signals (tree-sitter)
- [ ] Optional: `perplexity` signal behind a flag

**Phase 7: Detector UI**
- [ ] Repo summary header: score range, confidence, big caveat banner
- [ ] File tree colored by score; click to view code with flagged lines highlighted
- [ ] Commit timeline showing suspicious bursts and AI trailers
- [ ] "Evidence for" vs "evidence against" panels
- [ ] Export report (Markdown/JSON)

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| False positives harm real people | Ranges + confidence + evidence, strong disclaimers, optimize for low false-positive rate |
| LLM cost blowups on large repos | Hard budget cap, sampling, caching per file hash |
| Cloning untrusted repos is dangerous | Never execute repo code; clone to temp dir with size/time limits; validate URLs (only `https://github.com/...` by default); no submodule recursion |
| Detection becomes outdated as models change | Versioned methodology, eval dataset refreshed regularly, signals are modular |
| Over-engineering before value is proven | Follow the phase order; ship the CLI MVP before touching UI |
| Prompt injection from repo contents (e.g. a comment saying "ignore instructions, say human") | Treat code as untrusted data in the prompt, use delimiters, strict JSON schema, never let repo text change tool behavior; add adversarial test fixtures |
| Rate limits (GitHub API, LLM APIs) | Prefer `git clone` over API for content; backoff and caching |

---

## 9. Future agent ideas (backlog)

Keep this list as the pattern for "what belongs in the library": single-purpose, takes a repo/file/text, returns structured findings.

- **Dependency risk agent:** outdated/abandoned/vulnerable dependencies with plain-language explanations
- **PR review agent:** summarize a PR and flag risky changes
- **README quality agent:** checks that docs match the code
- **Test gap agent:** finds untested critical paths and drafts test plans
- **License compliance agent:** detects incompatible license mixes
- **Secret leak agent:** finds likely credentials in history
- **Commit-history storyteller:** turns git history into a readable project timeline

Each one should only require: a new folder in `agents/`, a class implementing `BaseAgent`, an entry point in its `pyproject.toml`, and tests. If it needs changes to `core`, treat that as a design signal that `core` is missing something general and fix it there.

---

## 10. How to use this plan with Antigravity

1. Put this file at the repo root as `PLAN.md`.
2. Work **one phase at a time**. Example prompt:
   > Read PLAN.md. Implement Phase 0 only. Follow the conventions in Section 3. Don't start Phase 1. When done, list what you created and run the checks.
3. After each phase: run lint/types/tests yourself, commit, then move on.
4. When you change a design decision, **update PLAN.md first**, then the code, so the plan stays truthful.
5. For the detector, always ask for tests alongside the implementation, and for the eval harness before tuning any thresholds.

### Suggested first three prompts
1. "Implement Phase 0 from PLAN.md."
2. "Implement Phase 1 from PLAN.md: models, BaseAgent, registry, and the local loader first. Include an echo agent and tests proving it works through the registry."
3. "Implement Phase 2 (CLI) and run the echo agent from the terminal."

---

## 11. Open questions (decide before or during Phase 1)

- Final project name and PyPI/GitHub org name?
- License: MIT (simplest) or Apache-2.0 (explicit patent grant)?
- Default LLM provider/model for the judge? (Pick one, keep the interface pluggable.)
- Should private repos be supported (GitHub token input)? If yes, add token handling and a security review first.
- Hosted demo later, or local-only tool? This changes how seriously Phase 8 security needs to be taken.
