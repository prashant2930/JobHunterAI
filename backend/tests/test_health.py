import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.database import engine, init_db
from app.models import SystemStatus

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Initialize database tables for testing."""
    init_db()

client = TestClient(app)

def test_health_endpoint():
    """Verify that the health check endpoint returns 200 and valid JSON data."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "jobhunter-ai"
    assert data["database"] == "connected"

def test_database_initialization():
    """Verify that the database initialized on startup contains the system_status table and a valid row."""
    with Session(engine) as session:
        status = session.exec(select(SystemStatus)).first()
        assert status is not None
        assert status.status == "ok"
        assert status.initialized_at is not None
