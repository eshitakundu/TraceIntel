import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> Iterator[None]:
    with tempfile.TemporaryDirectory(prefix="traceintel-tests-") as directory:
        key = "TRACEINTEL_DATABASE_URL"
        previous = os.environ.get(key)
        os.environ[key] = f"sqlite+aiosqlite:///{Path(directory) / 'api.db'}"
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        yield
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
