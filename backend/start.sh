#!/bin/sh
set -eu
port="${PORT:-8000}"
case "$port" in ''|*[!0-9]*) echo "PORT must be numeric." >&2; exit 1;; esac
if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
  echo "PORT must be between 1 and 65535." >&2
  exit 1
fi
if [ "${TRACEINTEL_SKIP_MIGRATIONS:-false}" != "true" ]; then
  alembic upgrade head
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "$port" --workers 1 --timeout-graceful-shutdown 20
