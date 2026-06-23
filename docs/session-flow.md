# Session Flow

This document describes how Flask sessions are used across chessclub-web
for authentication state, OAuth tokens, and admin access.

---

## Session Architecture

```mermaid
flowchart LR
    subgraph Browser
        COOKIE[Session Cookie<br/>signed + encrypted]
    end

    subgraph Flask Application
        SESSION[Flask Session Object]
        CFG[app.config<br/>SECRET_KEY]
    end

    COOKIE -- HTTP Request --> SESSION
    SESSION -- HTTP Response --> COOKIE
    CFG -- signs/encrypts --> COOKIE

    style Browser fill:#1a1a2e,color:#fff
    style Flask Application fill:#16213e,color:#fff
```

Flask uses a **client-side session** by default. Session data is serialized
to JSON, signed with `itsdangerous` using `SECRET_KEY`, and stored in a
signed cookie (`session`). The client never sees raw values — the cookie is
signed and optionally encrypted.

**Implications:**

- Session data is limited to ~4 KB (Cookie size limit).
- No server-side session store is required.
- Modifying `SECRET_KEY` invalidates all existing sessions.
- Session data persists across restarts (until the cookie expires).

---

## Session Keys

| Key | Type | Set By | Cleared By | Purpose |
|-----|------|--------|------------|---------|
| `oauth_code_verifier` | `str` | `auth.login()` | `auth.callback()` | PKCE code verifier for OAuth flow (one-time use). |
| `oauth_next` | `str` | `auth.login()` | `auth.callback()` | Redirect target after OAuth completes. |
| `oauth_token` | `dict` | `auth.callback()` | `auth.logout()` | OAuth 2.0 token: `{access_token, refresh_token, expires_at}`. |
| `chess_username` | `str` | `auth.callback()` | `auth.logout()` | Chess.com username from OAuth token response. |
| `admin_authenticated` | `bool` | `admin.login()` | `admin.logout()` | Admin panel session flag. |

---

## Auth Flow (OAuth 2.0 PKCE)

```mermaid
sequenceDiagram
    participant User as Browser
    participant App as Flask App
    participant Chess as Chess.com OAuth

    User->>App: GET /auth/login?next=/club/foo/tournaments
    Note over App: Generate code_verifier<br/>Store in session
    App->>Chess: 302 Redirect (authorize URL)
    User->>Chess: Authorize application
    Chess->>App: GET /auth/callback?code=XYZ
    Note over App: Read code_verifier from session<br/>Pop oauth_code_verifier
    App->>Chess: POST /token (code + verifier)
    Chess-->>App: {access_token, expires_in, username}
    Note over App: Store in session:[br/>oauth_token[access_token, expires_at]<br/>chess_username
    App->>User: 302 Redirect to /club/foo/tournaments
```

**Key detail:** The `oauth_code_verifier` is consumed on first use
(`session.pop()`). If the user reloads `/callback`, the verifier is gone
and the route returns an error flash. This prevents replay attacks.

### OAuth Token Lifetime

```python
# app/auth.py:119-126
session["oauth_token"] = {
    "access_token": token_data["access_token"],
    "refresh_token": token_data.get("refresh_token"),
    "expires_at": time.time() + token_data.get("expires_in", 3600),
}
```

The `_SessionOAuthProvider` in `chess_service.py` checks expiry with a
60-second safety buffer:

```python
# app/chess_service.py:38-41
def is_authenticated(self) -> bool:
    token = self._token_data
    expires_at = token.get("expires_at", 0)
    return bool(token.get("access_token")) and expires_at > time.time() + 60
```

---

## Admin Auth Flow

```mermaid
sequenceDiagram
    participant User as Browser
    participant App as Flask App

    User->>App: GET /admin/
    Note over App: Check admin_authenticated<br/>Missing → 302
    App->>User: 302 Redirect to /admin/login
    User->>App: POST /admin/login (password)
    Note over App: Compare with ADMIN_PASSWORD
    App->>User: 302 /admin/ (on success)
    Note over App: Set session:[br/>admin_authenticated = True
    User->>App: GET /admin/ (cookie attached)
    Note over App: _require_admin checks session
    App-->>User: Admin dashboard HTML
```

The `_require_admin` decorator in `admin.py` implements the gate:

```python
def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        password = current_app.config.get("ADMIN_PASSWORD", "")
        if not password:                          # Admin disabled
            return redirect(url_for("club.index"))
        if not session.get("admin_authenticated"): # Not logged in
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated
```

---

## Credential Resolution

`chess_service.make_client(session)` resolves credentials in priority order:

```mermaid
flowchart TD
    SESSION[Flask session dict] --> HAS_COOKIES{Server cookies<br/>configured?}
    HAS_COOKIES -- Yes --> HAS_OAUTH{OAuth token<br/>in session?}
    HAS_COOKIES -- No --> OAUTH_ONLY{OAuth token<br/>in session?}
    HAS_OAUTH -- Yes --> BOTH[CookieAuth + Bearer]
    HAS_OAUTH -- No --> COOKIE_ONLY[CookieAuth only]
    OAUTH_ONLY -- Yes --> OAUTH_BEARER[Bearer only]
    OAUTH_ONLY -- No --> UNAUTH[No credentials<br/>public API only]

    style SESSION fill:#2d2d44,color:#fff
    style BOTH fill:#1a3a2e,color:#fff
    style COOKIE_ONLY fill:#1a3a2e,color:#fff
    style OAUTH_BEARER fill:#3a2a1a,color:#fff
    style UNAUTH fill:#3a1a1a,color:#fff
```

---

## Session Expiry and Security

| Key | Lifespan | Notes |
|-----|----------|-------|
| Flask session cookie | Configurable (`PERMANENT_SESSION_LIFETIME`, default 31 days) | Uses `SESSION_COOKIE_HTTPONLY` and `SESSION_COOKIE_SAMESITE` defaults. |
| `oauth_token` | Depends on Chess.com's `expires_in` (typically 1 hour) | No refresh token flow implemented — user re-logs in when expired. |
| `admin_authenticated` | 30 minutes of inactivity (configurable via `ADMIN_SESSION_TIMEOUT_MINUTES`) | Cleared automatically on timeout; log out explicitly via `/admin/logout`. |
| `chess_username` | Same as `oauth_token` | Cleared on logout alongside the token. |

**Security notes:**

- OAuth tokens are stored in the signed cookie, never on the server
  filesystem.
- The admin check relies on the session flag plus CSRF token validation
  on all admin POST routes via the `_csrf_required` decorator.
- The `oauth_code_verifier` is a single-use 64-byte URL-safe token
  (`secrets.token_urlsafe(64)`).
- Server cookie credentials (`ACCESS_TOKEN`, `PHPSESSID`) are never
  written to the session — they remain in server-side config only.

---

## Session Lifecycle Per Request

```mermaid
flowchart LR
    REQ[Incoming HTTP Request] --> WSGI[WSGI Server]
    WSGI --> FLASK[Flask]
    FLASK --> DECRYPT[Decrypt session cookie<br/>using SECRET_KEY]
    DECRYPT --> HANDLER[Route handler<br/>reads/writes session]
    HANDLER --> ENCRYPT[Encrypt updated session<br/>set-cookie header]
    ENCRYPT --> RESP[HTTP Response]

    style REQ fill:#2d2d44,color:#fff
    style RESP fill:#1a3a2e,color:#fff
```

The session object behaves as a standard Python dictionary within a request.
All modifications are collected and serialized at the end of the request.
The `SessionMixin` in Werkzeug handles the `session.sid` (if used) and
cookie management automatically.
