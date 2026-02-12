"""
Test customer onboarding flow.
"""

from app.models import Customer
from app.services.encryption import encrypt_value


def test_onboard_customer(client):
    """Test creating a new customer returns customer_id and api_token."""
    response = client.post(
        "/api/onboard",
        json={
            "company_name": "Test Restaurant",
            "email": "test@example.com",
            "bot_provider": "vapi",
            "vapi_api_key": "sk_test_demo",
            "bot_id": "asst_test123",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "customer_id" in data
    assert "api_token" in data
    assert data["api_token"].startswith("pk_")
    assert data["status"] == "analyzing"
    assert "message" in data


def test_get_dashboard_no_data(client, db_session):
    """Test dashboard with no calls returns mock data."""
    try:
        encrypted = encrypt_value("test")
    except Exception:
        encrypted = None
    customer = Customer(
        company_name="Test",
        email="testdashboard@test.com",
        bot_provider="vapi",
        vapi_api_key_encrypted=encrypted,
        bot_id="test",
        status="active",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    response = client.get(f"/api/dashboard/{customer.id}")

    assert response.status_code == 200
    data = response.json()
    assert "success_rate" in data
    assert "total_calls" in data
