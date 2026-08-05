import pyotp
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.user import User


def enroll(client, email: str, password: str) -> tuple[dict[str, str], list[str]]:
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    challenge = login.json()["challenge_token"]
    setup = client.post("/api/v1/auth/2fa/setup", json={"challenge_token": challenge})
    assert setup.status_code == 200, setup.text
    enabled = client.post(
        "/api/v1/auth/2fa/enable",
        json={"challenge_token": challenge, "code": pyotp.TOTP(setup.json()["secret"]).now()},
    )
    assert enabled.status_code == 200, enabled.text
    return (
        {"Authorization": f"Bearer {enabled.json()['access_token']}"},
        enabled.json()["recovery_codes"],
    )


def test_password_login_does_not_issue_an_access_token(client):
    response = client.post("/api/v1/auth/login", json={"email": "operator@example.com", "password": "Operator123!"})

    assert response.status_code == 200
    assert response.json()["access_token"] is None
    assert response.json()["requires_2fa_setup"] is True


def test_operator_access_is_limited_to_assigned_clients(client, auth_headers):
    operator_headers, _ = enroll(client, "operator@example.com", "Operator123!")
    operator_orders = client.get("/api/v1/orders", headers=operator_headers)
    admin_clients = client.get("/api/v1/clients", headers=auth_headers).json()
    contoso = next(item for item in admin_clients if item["client_name"].startswith("Contoso"))
    contoso_order = client.get(f"/api/v1/orders?client_id={contoso['id']}", headers=auth_headers).json()["items"][0]

    assert operator_orders.status_code == 200
    assert operator_orders.json()["items"]
    assert all(item["client"]["client_name"].startswith("Northwind") for item in operator_orders.json()["items"])
    assert client.get(f"/api/v1/orders/{contoso_order['id']}", headers=operator_headers).status_code == 404
    assert client.post(f"/api/v1/orders/{operator_orders.json()['items'][0]['id']}/generate-xml", headers=operator_headers).status_code == 403


def test_recovery_code_is_single_use(client):
    with SessionLocal() as db:
        user = User(
            full_name="Recovery Test",
            email="recovery-test@example.com",
            password_hash=hash_password("RecoveryTest123!"),
            role="operator",
        )
        user.clients = [db.scalar(select(Client).order_by(Client.client_name))]
        db.add(user)
        db.commit()

    _, recovery_codes = enroll(client, "recovery-test@example.com", "RecoveryTest123!")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "recovery-test@example.com", "password": "RecoveryTest123!"},
    ).json()
    first = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": login["challenge_token"], "code": recovery_codes[0]},
    )
    second = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": login["challenge_token"], "code": recovery_codes[0]},
    )

    assert first.status_code == 200
    assert second.status_code == 401


def test_admin_can_change_operator_client_grants(client, auth_headers):
    users = client.get("/api/v1/users", headers=auth_headers).json()
    operator = next(user for user in users if user["email"] == "operator@example.com")
    clients = client.get("/api/v1/clients", headers=auth_headers).json()
    response = client.patch(
        f"/api/v1/users/{operator['id']}",
        headers=auth_headers,
        json={"role": "operator", "is_active": True, "client_ids": [clients[0]["id"]]},
    )

    assert response.status_code == 200
    assert response.json()["client_ids"] == [clients[0]["id"]]
