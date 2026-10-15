import io
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Campaign, ImportLog, ImportStatus, Lead


def test_import_preview_meta_ads(client: TestClient, admin_user):
    csv_content = """Campaign Name,Day,Amount spent (USD),Impressions,Clicks (all),Results
Summer Promo,2026-10-01,150.50,5000,120,6
Summer Promo,2026-10-02,200.00,6500,180,9
"""
    files = {"file": ("meta_ads.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post(
        "/api/v1/imports/preview?import_type=campaign_metrics",
        files=files,
        headers=admin_user["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "meta_ads.csv"
    assert data["total_rows"] == 2
    assert "Campaign Name" in data["detected_columns"]
    assert "Amount spent (USD)" in data["detected_columns"]
    assert len(data["sample_rows"]) == 2
    # Verify auto-detection of column mapping
    mapping = data["suggested_mapping"]
    assert "spend" in mapping.values()
    assert "date" in mapping.values()


def test_import_campaign_metrics_success_and_duplicate_prevention(
    client: TestClient, admin_user, test_campaign_a, db_session: Session
):
    csv_content = """Day,Amount spent (USD),Impressions,Clicks (all),Leads
2026-09-01,100.00,2000,80,5
2026-09-02,150.00,3000,120,7
"""
    files = {"file": ("daily_metrics.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post(
        f"/api/v1/imports/campaign-metrics?campaign_id={test_campaign_a.id}",
        files=files,
        headers=admin_user["headers"],
    )
    assert res.status_code == 201
    log = res.json()
    assert log["status"] == "completed"
    assert log["successful_rows"] == 2
    assert log["failed_rows"] == 0

    # Verify campaign totals updated
    db_session.refresh(test_campaign_a)
    assert test_campaign_a.total_spend == Decimal("250.00")
    assert test_campaign_a.impressions == 5000
    assert test_campaign_a.clicks == 200
    assert test_campaign_a.attributed_leads == 12

    # Second import with IDENTICAL content should be rejected with 409 Conflict
    files_dup = {"file": ("daily_metrics.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res_dup = client.post(
        f"/api/v1/imports/campaign-metrics?campaign_id={test_campaign_a.id}",
        files=files_dup,
        headers=admin_user["headers"],
    )
    assert res_dup.status_code == 409


def test_import_campaign_metrics_partial_failure(
    client: TestClient, admin_user, test_campaign_a
):
    # Row 2 has an invalid date
    csv_content = """Day,Amount spent (USD),Impressions,Clicks (all),Leads
2026-09-03,80.00,1500,60,4
INVALID_DATE,90.00,1600,70,3
"""
    files = {"file": ("partial.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post(
        f"/api/v1/imports/campaign-metrics?campaign_id={test_campaign_a.id}",
        files=files,
        headers=admin_user["headers"],
    )
    assert res.status_code == 201
    log = res.json()
    assert log["status"] == "partial"
    assert log["successful_rows"] == 1
    assert log["failed_rows"] == 1


def test_import_leads_and_error_download(
    client: TestClient, admin_user, test_client_a
):
    # 1 valid lead, 1 invalid email lead, 1 duplicate lead
    csv_content = """Name,Email,Phone,External ID,Source
Lead One,lead1@example.com,111222,ext_1,meta_ads
Lead Two,invalid-email-format,333444,ext_2,google_ads
Lead Three,lead3@example.com,555666,ext_3,organic
"""
    files = {"file": ("leads.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post(
        f"/api/v1/imports/leads?client_id={test_client_a.id}",
        files=files,
        headers=admin_user["headers"],
    )
    assert res.status_code == 201
    log = res.json()
    import_id = log["id"]
    assert log["total_rows"] == 3
    assert log["successful_rows"] == 2  # lead1 and lead3
    assert log["failed_rows"] == 1      # invalid-email-format

    # Download error report CSV
    err_res = client.get(
        f"/api/v1/imports/{import_id}/errors",
        headers=admin_user["headers"],
    )
    assert err_res.status_code == 200
    assert "text/csv" in err_res.headers["content-type"]
    err_csv = err_res.text
    assert "invalid-email-format" in err_csv or "Invalid email" in err_csv
