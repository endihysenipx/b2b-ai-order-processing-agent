from pathlib import Path


def test_login_works_with_seed_user(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "Admin123!"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["user"]["role"] == "admin"


def test_orders_list_returns_seeded_orders(client):
    response = client.get("/api/v1/orders")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 5
    assert {"OK", "Human in the Loop", "Waiting for Reply", "Failed", "ERP Ready"}.issubset(
        {item["status"] for item in data["items"]}
    )


def test_order_details_returns_items(client):
    orders = client.get("/api/v1/orders").json()["items"]
    response = client.get(f"/api/v1/orders/{orders[0]['id']}")

    assert response.status_code == 200
    assert response.json()["items"]
    assert response.json()["email"]["classification_status"] == "order"


def test_xml_generation_creates_two_files(client):
    orders = client.get("/api/v1/orders?status=OK").json()["items"]
    order_id = orders[0]["id"]
    response = client.post(f"/api/v1/orders/{order_id}/generate-xml")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ERP Ready"
    assert len(data["files"]) == 2
    for file_path in data["files"]:
        assert Path(file_path).exists()


def test_approve_then_send_xml_are_separate_actions(client, auth_headers):
    order = client.get("/api/v1/orders?status=Human%20in%20the%20Loop").json()["items"][0]
    approve_response = client.post(f"/api/v1/orders/{order['id']}/approve", headers=auth_headers)

    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "Approved"

    generate_response = client.post(f"/api/v1/orders/{order['id']}/generate-xml")
    assert generate_response.status_code == 200
    assert generate_response.json()["status"] == "ERP Ready"

    send_response = client.post(f"/api/v1/orders/{order['id']}/send-xml")
    assert send_response.status_code == 200
    assert send_response.json()["status"] == "XMLs Sent"
