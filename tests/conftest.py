import pytest

from app.database import init_db


@pytest.fixture
def db_conn():
    conn = init_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def api_client(tmp_path):
    from fastapi.testclient import TestClient

    from app.api.deps import get_db
    from app.api.main import app

    db_path = str(tmp_path / "api_test.sqlite3")
    setup_conn = init_db(db_path)

    def override_get_db():
        conn = init_db(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, setup_conn
    app.dependency_overrides.clear()
    setup_conn.close()
