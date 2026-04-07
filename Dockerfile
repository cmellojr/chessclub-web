# ============================================================
# Base stage — shared by dev and prod
# ============================================================
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# git is required to pip-install chessclub from GitHub
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the instance directory exists for SQLite
RUN mkdir -p instance

# Non-root user for production
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --no-create-home appuser \
    && chown -R appuser:appuser /app

EXPOSE 5000

# ============================================================
# Development stage — Flask dev server with hot reload
# ============================================================
FROM base AS dev

ENV FLASK_DEBUG=1

CMD ["python", "run.py"]

# ============================================================
# Production stage — gunicorn WSGI server
# ============================================================
FROM base AS prod

ENV FLASK_DEBUG=0

USER appuser

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app:create_app()"]
