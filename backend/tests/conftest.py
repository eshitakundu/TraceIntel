import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> Iterator[None]:
    provider_keys = (
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "TRACEINTEL_OPENROUTER_API_KEY",
        "TRACEINTEL_OPENROUTER_MODEL",
    )
    provider_values = {key: os.environ.get(key) for key in provider_keys}
    for key in provider_keys:
        os.environ[key] = ""
    with tempfile.TemporaryDirectory(prefix="traceintel-tests-") as directory:
        key = "TRACEINTEL_DATABASE_URL"
        previous = os.environ.get(key)
        os.environ[key] = os.environ.get(
            "TRACEINTEL_TEST_DATABASE_URL", f"sqlite+aiosqlite:///{Path(directory) / 'api.db'}"
        )
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        yield
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
    for key, value in provider_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
