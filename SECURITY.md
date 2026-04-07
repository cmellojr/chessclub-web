# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue.
2. Send an email to **cmellojr@gmail.com** with:
   - A description of the vulnerability.
   - Steps to reproduce.
   - Potential impact.
3. You will receive an acknowledgment within 48 hours.

## Security Considerations

- **Server cookies** (`CHESSCOM_SERVER_ACCESS_TOKEN`, `CHESSCOM_SERVER_PHPSESSID`)
  are stored server-side in `.env` and are never exposed to clients.
- **OAuth tokens** are stored in Flask's signed session cookie.
- **Admin panel** is protected by `ADMIN_PASSWORD`. Disabled when the variable
  is empty.
- **`.env` and `*.db` files** are excluded from version control via `.gitignore`.

## Best Practices for Deployment

- Set a strong, unique `SECRET_KEY` in production.
- Set a strong `ADMIN_PASSWORD`.
- Serve the application behind a reverse proxy (e.g., Nginx) with HTTPS.
- Restrict access to the `/admin` endpoint at the network level if possible.
