import os

os.environ["AIRE_DATABASE_URL"] = "sqlite:///./test_aire.db"
os.environ["AIRE_LLM_PROVIDER"] = "offline"

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        os.remove("./test_aire.db")
    except OSError:
        pass


@pytest.fixture
def session():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()
