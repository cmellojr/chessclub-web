# AGENTS.md

Repository instructions for coding agents working on `chessclub-web`.

Keep this file short and operational. Put durable project documentation in the
files referenced below, then link to it from here instead of duplicating it.

## Authority

- This root `AGENTS.md` applies to the whole repository.
- Read `.agents/README.md` before using the local multi-agent orchestration
  kit. If `.agents/AGENTS.md` exists and conflicts with this file, this root
  `AGENTS.md` wins for this repository.
- User instructions in the current chat still override repository guidance.
- Treat `.agents/` as local agent state; it is intentionally ignored by Git.

## Read First

- Project overview and quick start: `README.md`.
- Contribution workflow, branching, and style: `CONTRIBUTING.md`.
- Architecture, DB-first routes, auth, sync, data model: `docs/architecture.md`.
- Two-layer cache details: `docs/cache.md`.
- Deployment, threading, error handling, session flow: `docs/`.
- Environment variables and local secrets: `.env.example`.
- Ruff configuration and Python target: `pyproject.toml`.
- Security expectations: `SECURITY.md`.

## Architecture Rules

- Preserve the DB-first, library-fallback pattern described in
  `docs/architecture.md`. Watched clubs **must** be served from the
  SQLAlchemy DB only — never silently fall back to live chessclub calls.
- Keep `app/chess_service.py` as the auth source of truth.
- Keep `app/db_service.py` returning `chessclub` dataclass instances so
  templates remain data-source agnostic.

## Change Discipline

- Prefer small, scoped changes that match existing Flask, SQLAlchemy, and
  Jinja2 patterns.
- Update repository docs when behavior, setup, architecture, or security
  expectations change.
- Do not overwrite unrelated working-tree changes.
- Commit messages should be concise, imperative, and conventional in style.
