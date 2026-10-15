import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Campaign, Lead, LeadSource, LeadStatus
from app.utils.validators import is_valid_email, is_valid_phone, sanitize_string


def test_validators():
    assert is_valid_email("valid.user@example.com") is True
    assert is_valid_email("invalid-email") is False
    assert is_valid_email("@no-user.com") is False

    assert is_valid_phone("+1-555-123-4567") is True
    assert is_valid_phone("1234567") is True
    assert is_valid_phone("short") is False

    assert sanitize_string("  hello world  ") == "hello world"
    assert sanitize_string(None) is None
    assert sanitize_string("a" * 300, max_length=10) == "a" * 10


def test_reports_export_leads(
    client: TestClient, admin_user, test_client_a, db_session: Session
):
    lead = Lead(
        client_id=test_client_a.id,
        name="Exportable Lead",
        email="export@example.com",
        phone="+15559998888",
        source=LeadSource.meta_ads,
        status=LeadStatus.contacted,
    )
    db_session.add(lead)
    db_session.commit()

    res = client.get(
        f"/api/v1/reports/leads/export?client_id={test_client_a.id}",
        headers=admin_user["headers"],
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    csv_text = res.text
    assert "Exportable Lead" in csv_text
    assert "export@example.com" in csv_text


def test_reports_export_campaigns(
    client: TestClient, admin_user, test_client_a, test_campaign_a
):
    res = client.get(
        f"/api/v1/reports/campaigns/export?client_id={test_client_a.id}",
        headers=admin_user["headers"],
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    csv_text = res.text
    assert test_campaign_a.name in csv_text


def test_campaign_list_and_archive(
    client: TestClient, admin_user, test_campaign_a
):
    # List campaigns
    list_res = client.get("/api/v1/campaigns/", headers=admin_user["headers"])
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) >= 1
    assert any(c["id"] == str(test_campaign_a.id) for c in items)

    # Archive campaign
    del_res = client.delete(
        f"/api/v1/campaigns/{test_campaign_a.id}", headers=admin_user["headers"]
    )
    assert del_res.status_code == 204

    # Now verify archived campaign is not in active list
    list_after = client.get(
        "/api/v1/campaigns/", headers=admin_user["headers"]
    ).json()["items"]
    assert not any(c["id"] == str(test_campaign_a.id) for c in list_after)
