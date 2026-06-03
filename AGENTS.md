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
- Contribution workflow, branch model, and style summary: `CONTRIBUTING.md`.
- Architecture, DB-first route behavior, auth, sync, and data model:
  `docs/architecture.md`.
- Two-layer cache details: `docs/cache.md`.
- Environment variables and local secrets: `.env.example`.
- Ruff configuration and Python target: `pyproject.toml`.
- Security expectations: `SECURITY.md`.

External references for conventions:

- AGENTS.md format: https://agents.md/
- Codex AGENTS.md discovery and precedence:
  https://developers.openai.com/codex/guides/agents-md
- Google Python style: https://google.github.io/styleguide/pyguide.html
- Ruff: https://docs.astral.sh/ruff/
- Flask: https://flask.palletsprojects.com/
- Bootstrap: https://getbootstrap.com/docs/5.3/

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env
python run.py
ruff check --fix .
ruff format .
```

There is no test suite yet. Before finishing code changes, run:

```bash
ruff check .
ruff format --check .
```

## Project Rules

- Python is 3.11+. Use type annotations on function signatures and modern
  syntax such as `X | Y`.
- Follow Ruff and Google-style docstrings as configured in `pyproject.toml`.
- Keep imports ordered as stdlib, third-party, then local.
- User-facing text must be English.
- Frontend work uses Bootstrap 5.3 CDN and Jinja2 templates; there is no
  JavaScript build step.
- Do not commit secrets, `.env`, databases, or local agent state.

## Architecture Rules

- Preserve the DB-first, library-fallback route pattern described in
  `docs/architecture.md`.
- Watched clubs must be served from the SQLAlchemy DB only. Do not silently
  fall back to live `chessclub` calls for watched clubs.
- Keep `app/chess_service.py` as the auth source of truth.
- Keep `app/db_service.py` returning `chessclub` dataclass instances so
  templates remain data-source agnostic.
- When adding DB-backed data, update the ORM model, DB write/read functions,
  and sync persistence path together.

## Change Discipline

- Prefer small, scoped changes that match existing Flask, SQLAlchemy, and
  Jinja2 patterns.
- Update repository docs when behavior, setup, architecture, or security
  expectations change.
- Do not overwrite unrelated working-tree changes.
- Commit messages should be concise, imperative, and conventional in style.
