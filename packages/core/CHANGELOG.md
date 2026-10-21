# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-10-21

### Security
- A repository's own git config could make git run a program while margin read its history,
  for example through `core.fsmonitor`. Every git command now overrides the repository's
  config, turns hooks off and skips Git LFS downloads. This mattered most in Docker, where
  git's own ownership check is turned off for the shared folder.
- Cancelling a run while a repository was being cloned could leave a half-written clone in
  the temp folder. git now runs as a child process that is stopped before the folder is
  deleted.

## [0.1.0] - 2026-10-21

### Added
- The agent contract (`BaseAgent`, `RunContext`), structured results with findings and evidence, and the agent registry (entry-point group `margin.agents`).
- Model clients: local OpenAI-compatible servers (Ollama by default), Anthropic and OpenAI, with retries, token and cost tracking, per-run budgets, and a mock for tests.
- A model catalogue: list a provider's models, test a connection.
- Settings from environment variables, saved settings, `.env` and defaults, in that order.
- Code loaders: local folders and GitHub repositories, with filters, size limits, a pre-clone size check and git history.
- JSON and Markdown reports.
