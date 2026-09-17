FROM ghcr.io/astral-sh/uv:0.11.15 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
WORKDIR /app
RUN useradd --create-home --uid 10001 traceintel && chown traceintel:traceintel /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev
COPY --chown=10001:10001 backend ./backend
COPY --chown=10001:10001 alembic.ini ./
USER traceintel
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/api/v1/ready', timeout=3)" || exit 1
CMD ["sh", "/app/backend/start.sh"]
