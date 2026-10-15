import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ClientMembership, Lead, LeadSource, LeadStatus


def test_lead_creation_and_history(
    client: TestClient, admin_user, test_client_a
):
    lead_payload = {
        "client_id": str(test_client_a.id),
        "name": "Jane Doe",
        "email": "jane.doe@example.com",
        "phone": "+15554567890",
        "source": "meta_ads",
        "status": "new",
        "external_id": "meta_lead_12345",
        "notes": "Interested in marketing package",
    }
    response = client.post(
        "/api/v1/leads/", json=lead_payload, headers=admin_user["headers"]
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["status"] == "new"
    assert data["external_id"] == "meta_lead_12345"
    assert len(data["status_history"]) == 1
    assert data["status_history"][0]["to_status"] == "new"
    assert data["status_history"][0]["from_status"] is None


def test_lead_validation_invalid_email(
    client: TestClient, admin_user, test_client_a
):
    invalid_payload = {
        "client_id": str(test_client_a.id),
        "name": "Bad Email User",
        "email": "not-a-valid-email",
    }
    response = client.post(
        "/api/v1/leads/", json=invalid_payload, headers=admin_user["headers"]
    )
    assert response.status_code == 422


def test_lead_duplicate_detection(
    client: TestClient, admin_user, test_client_a, test_client_b
):
    lead_data = {
        "client_id": str(test_client_a.id),
        "name": "Duplicate Tester",
        "email": "unique.person@example.com",
        "external_id": "ext_id_999",
    }
    # First creation succeeds
    res1 = client.post(
        "/api/v1/leads/", json=lead_data, headers=admin_user["headers"]
    )
    assert res1.status_code == 201

    # Duplicate by external_id in same client -> 409 Conflict
    dup_ext = {
        "client_id": str(test_client_a.id),
        "name": "Other Name",
        "email": "different@example.com",
        "external_id": "ext_id_999",
    }
    res_dup_ext = client.post(
        "/api/v1/leads/", json=dup_ext, headers=admin_user["headers"]
    )
    assert res_dup_ext.status_code == 409

    # Duplicate by email in same client -> 409 Conflict
    dup_email = {
        "client_id": str(test_client_a.id),
        "name": "Another Name",
        "email": "unique.person@example.com",
        "external_id": "different_ext_id",
    }
    res_dup_email = client.post(
        "/api/v1/leads/", json=dup_email, headers=admin_user["headers"]
    )
    assert res_dup_email.status_code == 409

    # Same email and external_id for DIFFERENT client is allowed
    diff_client_lead = {
        "client_id": str(test_client_b.id),
        "name": "Same Person Different Org",
        "email": "unique.person@example.com",
        "external_id": "ext_id_999",
    }
    res_diff_client = client.post(
        "/api/v1/leads/", json=diff_client_lead, headers=admin_user["headers"]
    )
    assert res_diff_client.status_code == 201


def test_lead_stage_transitions(client: TestClient, admin_user, test_client_a):
    # Create lead
    create_res = client.post(
        "/api/v1/leads/",
        json={
            "client_id": str(test_client_a.id),
            "name": "Pipeline Lead",
            "email": "pipeline@example.com",
            "status": "new",
        },
        headers=admin_user["headers"],
    )
    lead_id = create_res.json()["id"]

    # Transition to contacted
    res_contacted = client.patch(
        f"/api/v1/leads/{lead_id}/status",
        json={"status": "contacted", "notes": "Called lead via phone"},
        headers=admin_user["headers"],
    )
    assert res_contacted.status_code == 200
    data_contacted = res_contacted.json()
    assert data_contacted["status"] == "contacted"
    assert data_contacted["contacted_at"] is not None
    assert data_contacted["converted_at"] is None

    # Transition to converted
    res_converted = client.patch(
        f"/api/v1/leads/{lead_id}/status",
        json={"status": "converted", "notes": "Signed $10k annual retainer"},
        headers=admin_user["headers"],
    )
    assert res_converted.status_code == 200
    data_converted = res_converted.json()
    assert data_converted["status"] == "converted"
    assert data_converted["converted_at"] is not None

    # Verify history chain: new -> contacted -> converted
    lead_full = client.get(
        f"/api/v1/leads/{lead_id}", headers=admin_user["headers"]
    ).json()
    history = lead_full["status_history"]
    assert len(history) == 3
    assert history[0]["to_status"] == "new"
    assert history[1]["to_status"] == "contacted"
    assert history[2]["to_status"] == "converted"


def test_lead_permissions_and_client_isolation(
    client: TestClient,
    admin_user,
    client_user,
    test_client_a,
    test_client_b,
    client_user_membership_a,
    db_session: Session,
):
    # Create lead under Client A
    res_a = client.post(
        "/api/v1/leads/",
        json={"client_id": str(test_client_a.id), "name": "Lead A", "email": "a@example.com"},
        headers=admin_user["headers"],
    )
    lead_a_id = res_a.json()["id"]

    # Create lead under Client B
    res_b = client.post(
        "/api/v1/leads/",
        json={"client_id": str(test_client_b.id), "name": "Lead B", "email": "b@example.com"},
        headers=admin_user["headers"],
    )
    lead_b_id = res_b.json()["id"]

    # Client user (assigned to Client A) can view Lead A
    res_view_a = client.get(
        f"/api/v1/leads/{lead_a_id}", headers=client_user["headers"]
    )
    assert res_view_a.status_code == 200

    # Client user CANNOT view Lead B (404 / scoped out)
    res_view_b = client.get(
        f"/api/v1/leads/{lead_b_id}", headers=client_user["headers"]
    )
    assert res_view_b.status_code == 404

    # Client user with can_update_leads=True can update status of Lead A
    res_update_status = client.patch(
        f"/api/v1/leads/{lead_a_id}/status",
        json={"status": "contacted"},
        headers=client_user["headers"],
    )
    assert res_update_status.status_code == 200

    # Now revoke can_update_leads permission
    membership = (
        db_session.query(ClientMembership)
        .filter(ClientMembership.user_id == client_user["user"].id)
        .first()
    )
    membership.can_update_leads = False
    db_session.commit()

    # Client user now gets 403 when updating status
    res_denied_status = client.patch(
        f"/api/v1/leads/{lead_a_id}/status",
        json={"status": "converted"},
        headers=client_user["headers"],
    )
    assert res_denied_status.status_code == 403

    # Only admin can delete/archive lead; client user gets 403
    del_client_res = client.delete(
        f"/api/v1/leads/{lead_a_id}", headers=client_user["headers"]
    )
    assert del_client_res.status_code == 403

    del_admin_res = client.delete(
        f"/api/v1/leads/{lead_a_id}", headers=admin_user["headers"]
    )
    assert del_admin_res.status_code == 204


def test_lead_search_filtering_pagination(
    client: TestClient, admin_user, test_client_a
):
    # Seed 3 distinct leads
    leads_to_create = [
        {"name": "Alice Johnson", "email": "alice@alpha.com", "phone": "111", "status": "new", "source": "meta_ads"},
        {"name": "Bob Smith", "email": "bob@beta.com", "phone": "222", "status": "contacted", "source": "google_ads"},
        {"name": "Charlie Brown", "email": "charlie@gamma.com", "phone": "333", "status": "converted", "source": "referral"},
    ]
    for item in leads_to_create:
        payload = {"client_id": str(test_client_a.id), **item}
        client.post("/api/v1/leads/", json=payload, headers=admin_user["headers"])

    # Filter by status=contacted
    res_status = client.get(
        "/api/v1/leads/?status=contacted", headers=admin_user["headers"]
    )
    assert res_status.status_code == 200
    items = res_status.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Bob Smith"

    # Filter by search term 'charlie'
    res_search = client.get(
        "/api/v1/leads/?search=charlie", headers=admin_user["headers"]
    )
    assert res_search.status_code == 200
    assert len(res_search.json()["items"]) == 1
    assert res_search.json()["items"][0]["email"] == "charlie@gamma.com"

    # Pagination: per_page=2, page=1
    res_page1 = client.get(
        "/api/v1/leads/?per_page=2&page=1", headers=admin_user["headers"]
    )
    assert res_page1.status_code == 200
    data1 = res_page1.json()
    assert len(data1["items"]) == 2
    assert data1["total"] == 3
    assert data1["pages"] == 2
