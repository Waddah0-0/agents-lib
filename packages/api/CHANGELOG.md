# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-21

### Added
- Background runs with live progress (server-sent events), queue positions and cancellation.
- Model settings over HTTP: provider, models, keys (never returned), live model lists and a connection test.
- The web UI, bundled in the package and served from the same address.
- Answers only to `localhost` by default (protects against DNS rebinding).
