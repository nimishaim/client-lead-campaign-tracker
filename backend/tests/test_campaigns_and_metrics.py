import uuid
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Campaign, CampaignDailyMetric, CampaignPlatform, CampaignStatus, Lead, LeadSource, LeadStatus
from app.services.campaign_service import calculate_metrics, upsert_daily_metric
from app.services.dashboard_service import get_dashboard_metrics


def test_calculate_metrics_zero_denominator_safety():
    # Case 1: Zero leads (CPL zero denominator)
    c_zero_leads = Campaign(
        name="Zero Leads Camp",
        budget=Decimal("1000.00"),
        total_spend=Decimal("250.00"),
        attributed_leads=0,
    )
    metrics1 = calculate_metrics(c_zero_leads)
    assert metrics1["cpl"] is None  # Handled safely, not division by zero
    assert metrics1["budget_utilisation"] == Decimal("25.00")

    # Case 2: Zero budget (Budget utilisation zero denominator)
    c_zero_budget = Campaign(
        name="Zero Budget Camp",
        budget=Decimal("0.00"),
        total_spend=Decimal("150.00"),
        attributed_leads=15,
    )
    metrics2 = calculate_metrics(c_zero_budget)
    assert metrics2["cpl"] == Decimal("10.00")
    assert metrics2["budget_utilisation"] is None  # Handled safely

    # Case 3: None budget and None spend
    c_none = Campaign(
        name="None Camp",
        budget=None,
        total_spend=Decimal("0.00"),
        attributed_leads=0,
    )
    metrics3 = calculate_metrics(c_none)
    assert metrics3["cpl"] is None
    assert metrics3["budget_utilisation"] is None

    # Case 4: Standard valid campaign
    c_valid = Campaign(
        name="Valid Camp",
        budget=Decimal("5000.00"),
        total_spend=Decimal("2000.00"),
        attributed_leads=100,
    )
    metrics4 = calculate_metrics(c_valid)
    assert metrics4["cpl"] == Decimal("20.00")
    assert metrics4["budget_utilisation"] == Decimal("40.00")


def test_campaign_crud_and_computed_metrics(
    client: TestClient, admin_user, test_client_a
):
    campaign_data = {
        "client_id": str(test_client_a.id),
        "name": "Retargeting Meta Ads",
        "platform": "meta_ads",
        "budget": 2500.00,
    }
    # Create campaign
    create_res = client.post(
        "/api/v1/campaigns/", json=campaign_data, headers=admin_user["headers"]
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["name"] == "Retargeting Meta Ads"
    campaign_id = created["id"]

    # Read campaign - verify computed metrics returned
    get_res = client.get(
        f"/api/v1/campaigns/{campaign_id}", headers=admin_user["headers"]
    )
    assert get_res.status_code == 200
    camp = get_res.json()
    assert "cpl" in camp
    assert "budget_utilisation" in camp
    assert camp["cpl"] is None  # 0 leads initially
    assert float(camp["budget_utilisation"]) == 0.0

    # Update campaign
    patch_res = client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={"budget": 3000.00},
        headers=admin_user["headers"],
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["budget"] == "3000.00"


def test_campaign_daily_metrics(
    client: TestClient, admin_user, test_campaign_a, db_session: Session
):
    # Upsert daily metrics via service
    d1 = date(2026, 10, 1)
    d2 = date(2026, 10, 2)
    upsert_daily_metric(
        db_session,
        test_campaign_a.id,
        d1,
        Decimal("100.00"),
        1500,
        50,
        5,
    )
    upsert_daily_metric(
        db_session,
        test_campaign_a.id,
        d2,
        Decimal("150.00"),
        2000,
        75,
        8,
    )

    # Fetch daily metrics via API
    res = client.get(
        f"/api/v1/campaigns/{test_campaign_a.id}/metrics",
        headers=admin_user["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    dates = [row["date"] for row in data]
    assert "2026-10-01" in dates
    assert "2026-10-02" in dates


def test_dashboard_metrics_and_zero_conversion_safety(
    client: TestClient,
    admin_user,
    test_client_a,
    test_campaign_a,
    db_session: Session,
):
    # Scenario A: Only 'new' leads -> eligible = total - new - lost = 0 -> conversion_rate is None
    lead_new = Lead(
        client_id=test_client_a.id,
        campaign_id=test_campaign_a.id,
        name="New Lead Only",
        status=LeadStatus.new,
    )
    db_session.add(lead_new)
    db_session.commit()

    res_a = client.get("/api/v1/dashboard/metrics", headers=admin_user["headers"])
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total_leads"] == 1
    assert data_a["new_leads"] == 1
    assert data_a["conversion_rate"] is None  # Handled safely (no division by zero)

    # Scenario B: Add 1 contacted and 1 converted lead
    # eligible = 3 total - 1 new - 0 lost = 2 eligible
    # converted = 1 -> conversion_rate = (1 / 2) * 100 = 50.00%
    lead_contacted = Lead(
        client_id=test_client_a.id,
        campaign_id=test_campaign_a.id,
        name="Contacted Lead",
        status=LeadStatus.contacted,
    )
    lead_converted = Lead(
        client_id=test_client_a.id,
        campaign_id=test_campaign_a.id,
        name="Converted Lead",
        status=LeadStatus.converted,
    )
    db_session.add_all([lead_contacted, lead_converted])
    db_session.commit()

    res_b = client.get("/api/v1/dashboard/metrics", headers=admin_user["headers"])
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total_leads"] == 3
    assert data_b["converted_leads"] == 1
    assert data_b["conversion_rate"] == 50.0

    # Pipeline distribution endpoint
    res_pipeline = client.get(
        "/api/v1/dashboard/pipeline", headers=admin_user["headers"]
    )
    assert res_pipeline.status_code == 200
    pipeline_data = res_pipeline.json()
    assert len(pipeline_data) > 0
    statuses = [p["status"] for p in pipeline_data]
    assert "new" in statuses
    assert "contacted" in statuses
    assert "converted" in statuses

    # Time-series endpoint
    res_ts = client.get(
        "/api/v1/dashboard/time-series?days=14", headers=admin_user["headers"]
    )
    assert res_ts.status_code == 200
    ts_data = res_ts.json()
    assert len(ts_data) == 14  # Continuous 14-day data points
