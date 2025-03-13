import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from app import app, get_db
from models import Base, Contract, DailyMetrics, Alert

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Test client
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard de Análise de Contratos" in response.text

def test_metrics_empty_db(db_session):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "status_counts" in data
    assert "avg_resolution_times" in data
    assert "timestamp" in data

def test_metrics_with_data(db_session):
    # Add test data
    contract = Contract(
        contract_number="TEST001",
        collaborator="Test User",
        status="pending",
        resolution_time=2.5,
        created_at=datetime.utcnow()
    )
    db_session.add(contract)
    
    metrics = DailyMetrics(
        contract_id=1,
        date=datetime.utcnow().date(),
        productivity=0.8,
        efficiency=0.9,
        resolution_rate=0.85
    )
    db_session.add(metrics)
    db_session.commit()

    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["status_counts"]["pending"] == 1
    assert "avg_resolution_times" in data

def test_alerts_empty_db(db_session):
    response = client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert "alerts" in data
    assert len(data["alerts"]) == 0

def test_alerts_with_data(db_session):
    # Add test data
    contract = Contract(
        contract_number="TEST002",
        collaborator="Test User",
        status="analyzing",
        created_at=datetime.utcnow()
    )
    db_session.add(contract)
    db_session.commit()

    alert = Alert(
        contract_id=1,
        type="warning",
        message="Test alert",
        created_at=datetime.utcnow()
    )
    db_session.add(alert)
    db_session.commit()

    response = client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["type"] == "warning"
    assert data["alerts"][0]["message"] == "Test alert"

def test_websocket_connection():
    with client.websocket_connect("/ws/metrics") as websocket:
        data = {"test": "message"}
        websocket.send_json(data)
        response = websocket.receive_json()
        assert "message" in response
        assert "You wrote:" in response["message"]

def test_metrics_calculation(db_session):
    # Add test data with various statuses
    statuses = ["pending", "completed", "analyzing"]
    for i, status in enumerate(statuses):
        contract = Contract(
            contract_number=f"TEST{i+1}",
            collaborator="Test User",
            status=status,
            resolution_time=float(i+1),
            created_at=datetime.utcnow() - timedelta(days=i)
        )
        db_session.add(contract)
    db_session.commit()

    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    
    # Check status counts
    assert sum(data["status_counts"].values()) == 3
    assert all(status in data["status_counts"] for status in statuses)
    
    # Check resolution times
    assert all(status in data["avg_resolution_times"] for status in statuses)
    assert all(isinstance(time, (int, float)) for time in data["avg_resolution_times"].values())

def test_alert_lifecycle(db_session):
    # Create contract
    contract = Contract(
        contract_number="TEST003",
        collaborator="Test User",
        status="pending",
        created_at=datetime.utcnow()
    )
    db_session.add(contract)
    db_session.commit()

    # Create alert
    alert = Alert(
        contract_id=1,
        type="warning",
        message="Test alert",
        created_at=datetime.utcnow()
    )
    db_session.add(alert)
    db_session.commit()

    # Check active alert
    response = client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data["alerts"]) == 1

    # Resolve alert
    alert.resolved_at = datetime.utcnow()
    db_session.commit()

    # Check no active alerts
    response = client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data["alerts"]) == 0

if __name__ == "__main__":
    pytest.main(["-v"]) 