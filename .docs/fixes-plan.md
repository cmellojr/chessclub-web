# Detailed Fix Plan — chessclub-web Runtime & Data-Persistence Issues

> Status: **draft plan** — no code changes applied yet.
> Scope: fixes identified during a full project health review (August 2026).
> Target branch: `develop`.

This document describes the inconsistencies found in the current codebase that
affect either the ability to run the project or the correctness/persistence of
its data, and specifies exactly how each one should be fixed.

---

## 1. Context

The project was reviewed end-to-end: application modules, templates, tests,
Compose/Docker files, and the `chessclub` library (both the local checkout at
`../chessclub` and the published GitHub `main` branch used by the Docker build).

Verified as **consistent** and **not** part of this plan:

- All Python modules parse (AST check, 20 files).
- Every `chessclub` import/symbol used by the app exists on the published
  GitHub `main` (commit `98d929a`): `core.models`, `core.exceptions`,
  `auth`, `providers.chesscom`, `services.*`.
- `docker compose config` validates. Port 5000 is free; no container conflicts.
- Templates, route endpoints, and test assertions match.
- The old "page inaccessible" bug (Flask bound to `127.0.0.1`, visible in the
  logs of the retired `chessclub-web-web-1` container) was already fixed in
  commit `555a02f`; `run.py` now binds `0.0.0.0`.
- The APScheduler reloader guard in `app/__init__.py` and the `portalocker.Lock`
  usage in `app/sync.py` are correct.

---

## 2. Findings Requiring Fixes

### 2.1 Bug — tournament results are never persisted

**File:** `app/sync.py` (`sync_club`, ~line 208)

**Symptom:** Watched-club leaderboard, attendance, and rating-history pages stay
empty (or only show library-fallback data) even after a successful Phase 1 sync.

**Root cause:** The sync loop passes the whole `Tournament` dataclass instead of
its ID:

```python
for t in tournaments_data:
    results = club_svc.get_tournament_results(t)
```

But the library signature is:

```python
def get_tournament_results(
    self,
    tournament_id: str,
    tournament_type: str = "arena",
    tournament_url: str | None = None,
) -> list[TournamentResult]
```

Passing a `Tournament` object makes the library build URLs like
`…/callback/live/tournament/Tournament(id='…', …)/leaderboard`. Every URL probe
returns HTTP 404, the library returns an empty list, the `if results:` guard
skips `db_service.upsert_results(...)`, and the step is incorrectly marked `ok`
— so the failure is silent.

**Fix:**

```python
for t in tournaments_data:
    results = club_svc.get_tournament_results(
        t.id,
        tournament_type=t.tournament_type,
        tournament_url=t.url,
    )
    if results:
        db_service.upsert_results(results)
```

**Verification:**
- Unit/integration test: mock `ClubService.get_tournament_results` and assert it
  is called with `t.id`, `tournament_type`, and `tournament_url`.
- Manual: run Phase 1 sync for a watched club, confirm
  `sync_status.clubs[slug].steps["tournament_results"] == "ok"` and that
  `tournament_results` rows exist in the DB (leaderboard/attendance pages show
  data).

---

### 2.2 Deployment bug — SQLite database is written outside the declared volume

**Files:** `config.py`, `docker-compose.yml`, docs (`docs/cache.md`,
`docs/architecture.md`, `docs/deployment.md`)

**Symptom (prod):** Database file is lost on every `docker compose` recreate;
the `db-data` volume stays empty. In dev, the DB silently lands inside the
bind-mounted host `app/` tree instead of the documented location.

**Root cause:** `config.py` defaults to a *relative* SQLite URI:

```python
SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI", "sqlite:///chessclub.db")
```

Flask-SQLAlchemy resolves relative SQLite paths against
`app.instance_path`, which for `Flask("app")` (the package in
`app/__init__.py`) is `<package_root>/instance` — i.e. **`/app/app/instance`
inside the container**. However:

- `docker-compose.yml` mounts the `db-data` volume at **`/app/instance`**.
- `docs/*` document the DB at `/app/instance/chessclub.db` and
  `instance/chessclub.db`.

So the volume is mounted at the wrong path and never actually holds the DB.

**Fix (chosen option): absolute URI in Compose.**

1. In `docker-compose.yml`, pass the absolute container path:

   ```yaml
   environment:
     - DATABASE_URI=sqlite:////app/instance/chessclub.db
   ```

   (Four slashes: `sqlite:///` + absolute path `/app/instance/…`.)
   The `db-data` volume remains mounted at `/app/instance`.

2. Keep the relative default in `config.py` for native development, but update
   the docstrings/comments to clarify that the default resolves to
   `<package>/instance/`.

3. Update documentation:
   - `docs/deployment.md`: correct the persistent-path table (DB lives in the
     `db-data` volume at `/app/instance/chessclub.db` inside the container).
   - `docs/cache.md` and `docs/architecture.md`: adjust the DB location
     references accordingly.

**Verification:**
- `docker compose up` (dev), confirm the DB file is created at
  `/app/instance/chessclub.db` inside the container, and NOT in
  `/app/app/instance/`.
- `docker compose down && docker compose up` — data must survive the recreate
  (volume persistence).
- Repeat with the prod override
  (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`).

**Note on tests:** `tests/conftest.py` overrides the URI to
`sqlite:///:memory:` *after* `create_app()`, so `create_app()`'s
`db.create_all()` still touches the default relative path. Consider setting
`DATABASE_URI` to an in-memory or temp value before `create_app()` in the
fixture, so running the suite never writes `app/instance/chessclub.db`.

---

### 2.3 Native run is not possible out of the box

**Symptom:** `python run.py` fails immediately with
`ModuleNotFoundError: No module named 'flask'`.

**Root cause:** `.venv/` is empty and the system interpreter (Python 3.13.5)
only has `requests` installed. `requirements.txt` dependencies are missing.
Additionally, `instance/` and `.venv/` are root-owned on this machine, which
can cause permission errors for non-root users.

**Fix (documentation + environment, not code):**
- Document in `docs/deployment.md` / `README.md` that a local install requires:
  `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
- Advise fixing ownership if needed: `sudo chown -R "$USER":"$USER" .venv instance`.
- This is an environment setup concern, not an application bug; the primary
  supported path remains Docker.

---

### 2.4 Expired server cookies cause silent sync failure

**Symptom:** Phase 1/2 syncs fail at startup and from the admin dashboard with
401; watched clubs show empty DB data.

**Root cause:** `CHESSCOM_SERVER_ACCESS_TOKEN` / `CHESSCOM_SERVER_PHPSESSID` in
`.env` were issued ~24h+ ago and Chess.com session cookies expire (see
`docs/architecture.md`). The JWT in `.env` (`iat` ≈ 2026-08-08, `exp` ≈
2026-08-10) is already expired as of this review.

**Fix (operational, no code change):**
- Refresh the cookies via the Cookie Helper extension or DevTools and update
  `.env`, then restart the container.
- Document a cookie-refresh reminder on the admin dashboard (out of scope here;
  can be a follow-up improvement).

---

## 3. Minor / Documentation Drift

| # | Item | Action |
|---|------|--------|
| 3.1 | `docs/deployment.md` documents a `healthcheck` as a "docker-compose.yml snippet", but `docker-compose.yml` has no healthcheck. | Either add the healthcheck to `docker-compose.yml` or adjust the doc wording to say "example snippet". |
| 3.2 | `config.py` reads `CHESSCOM_OAUTH_CLIENT_SECRET`, but `.env.example` does not define it. | Add the variable to `.env.example` with an explanatory comment. |
| 3.3 | `SECRET_KEY=secret123` in `.env` is weak. | Document a strong key (`secrets.token_hex(32)`) in `docs/deployment.md`; generate a real key for non-local environments. |
| 3.4 | `tests/conftest.py` sets the test DB URI after `create_app()`. | Reorder so the URI is configured before app creation (see 2.2 note). |

---

## 4. Implementation Order & Checklist

1. **Fix 2.1** — `app/sync.py`: correct `get_tournament_results` call. *(highest
   priority: data correctness)*
2. **Fix 2.2** — `docker-compose.yml`: set absolute `DATABASE_URI`; update
   `docs/cache.md`, `docs/architecture.md`, `docs/deployment.md`.
3. **Minor items 3.1–3.4** — healthcheck/doc adjustments, `.env.example`
   addition, test fixture ordering.
4. **Docs 2.3** — native-run setup instructions.
5. **Verification:**
   - `ruff check .` and `ruff format --check .` pass.
   - `pytest` passes (`tests/`).
   - `docker compose up` boots; `/` and `/health` return 200.
   - Phase 1 sync persists `tournament_results`; leaderboard shows data.
   - DB survives `docker compose down && up` (volume persistence).

---

## 5. Out of Scope (follow-ups)

- Cookie auto-refresh / expiry warning on the admin dashboard.
- Adding a real Docker `healthcheck` to the service.
- Database migrations (schema changes are additive only).