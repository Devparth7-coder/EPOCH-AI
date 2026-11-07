import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Isolated DB + deterministic mode for the entire test session.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["TAVILY_API_KEY"] = ""
os.environ["BIFROST_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _schema():
    init_db()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
