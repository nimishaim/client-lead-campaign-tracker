import uuid
from fastapi.testclient import TestClient

from app.models import Client, ClientMembership


def test_client_crud_admin(client: TestClient, admin_user):
    # Create client
    client_data = {
        "name": "New Horizons Marketing",
        "company": "New Horizons LLC",
        "email": "info@newhorizons.com",
        "phone": "+15552345678",
        "website": "https://newhorizons.com",
        "industry": "Marketing",
    }
    create_res = client.post(
        "/api/v1/clients/", json=client_data, headers=admin_user["headers"]
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["name"] == "New Horizons Marketing"
    client_id = created["id"]

    # Read client
    get_res = client.get(
        f"/api/v1/clients/{client_id}", headers=admin_user["headers"]
    )
    assert get_res.status_code == 200
    assert get_res.json()["company"] == "New Horizons LLC"

    # Update client
    update_res = client.patch(
        f"/api/v1/clients/{client_id}",
        json={"company": "New Horizons Global Inc"},
        headers=admin_user["headers"],
    )
    assert update_res.status_code == 200
    assert update_res.json()["company"] == "New Horizons Global Inc"


def test_client_isolation_role_based(
    client: TestClient,
    admin_user,
    client_user,
    test_client_a,
    test_client_b,
    client_user_membership_a,
):
    # Admin sees both clients
    admin_res = client.get("/api/v1/clients/", headers=admin_user["headers"])
    assert admin_res.status_code == 200
    admin_client_ids = [c["id"] for c in admin_res.json()]
    assert str(test_client_a.id) in admin_client_ids
    assert str(test_client_b.id) in admin_client_ids

    # Client-role user only sees Client A (their assigned membership)
    client_res = client.get("/api/v1/clients/", headers=client_user["headers"])
    assert client_res.status_code == 200
    client_accessible_ids = [c["id"] for c in client_res.json()]
    assert str(test_client_a.id) in client_accessible_ids
    assert str(test_client_b.id) not in client_accessible_ids

    # Client user can access Client A details
    allowed_res = client.get(
        f"/api/v1/clients/{test_client_a.id}", headers=client_user["headers"]
    )
    assert allowed_res.status_code == 200

    # Client user CANNOT access Client B details (403 Forbidden)
    forbidden_res = client.get(
        f"/api/v1/clients/{test_client_b.id}", headers=client_user["headers"]
    )
    assert forbidden_res.status_code == 403


def test_client_forbidden_actions_for_client_role(
    client: TestClient, client_user, test_client_a
):
    # Client cannot create client
    create_res = client.post(
        "/api/v1/clients/",
        json={"name": "Hacker Corp"},
        headers=client_user["headers"],
    )
    assert create_res.status_code == 403

    # Client cannot update client
    update_res = client.patch(
        f"/api/v1/clients/{test_client_a.id}",
        json={"name": "Hacked Name"},
        headers=client_user["headers"],
    )
    assert update_res.status_code == 403


def test_client_membership_management(
    client: TestClient, admin_user, client_user, test_client_b
):
    # Admin adds client_user to test_client_b
    add_res = client.post(
        f"/api/v1/clients/{test_client_b.id}/members/{client_user['user'].id}?can_update_leads=true",
        headers=admin_user["headers"],
    )
    assert add_res.status_code == 201

    # Adding again should return 400
    dup_res = client.post(
        f"/api/v1/clients/{test_client_b.id}/members/{client_user['user'].id}",
        headers=admin_user["headers"],
    )
    assert dup_res.status_code == 400

    # Non-admin cannot add member (403)
    forbidden_add = client.post(
        f"/api/v1/clients/{test_client_b.id}/members/{client_user['user'].id}",
        headers=client_user["headers"],
    )
    assert forbidden_add.status_code == 403

    # Admin removes member
    remove_res = client.delete(
        f"/api/v1/clients/{test_client_b.id}/members/{client_user['user'].id}",
        headers=admin_user["headers"],
    )
    assert remove_res.status_code == 204
