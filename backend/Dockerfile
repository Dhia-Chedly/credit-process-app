# syntax=docker/dockerfile:1.7

FROM python:3.13-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

WORKDIR /app

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app

COPY pyproject.toml uv.lock ./

FROM base AS development

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group dev

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS production

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

COPY --chown=app:app . .

RUN DJANGO_SETTINGS_MODULE=config.settings.local \
    DJANGO_SECRET_KEY=build-only \
    python manage.py collectstatic --noinput \
    && mkdir -p /app/media \
    && chown app:app /app/media

USER app

EXPOSE 8000

CMD ["gunicorn", "--config", "/app/gunicorn.conf.py", "config.wsgi:application"]
