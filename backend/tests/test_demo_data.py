from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.order import Order
from app.services.demo_data import STATUS_COUNTS, delete_demo_data


def test_admin_can_generate_and_remove_exact_demo_dataset(client, auth_headers):
    with SessionLocal() as db:
        delete_demo_data(db)
        non_demo_before = db.scalar(select(func.count(Order.id)).where(Order.is_demo.is_(False))) or 0

    try:
        response = client.post("/api/v1/demo-data", headers=auth_headers)
        assert response.status_code == 200, response.text
        generated = response.json()
        assert generated["generated"] is True
        assert generated["order_count"] == 1_000
        assert generated["client_count"] == 6
        assert generated["status_counts"] == STATUS_COUNTS
        assert generated["date_from"] == (datetime.now(UTC).date() - timedelta(days=29)).isoformat()
        assert generated["date_to"] == datetime.now(UTC).date().isoformat()

        repeat = client.post("/api/v1/demo-data", headers=auth_headers)
        assert repeat.status_code == 200
        assert repeat.json()["order_count"] == 1_000
        assert "no duplicates" in repeat.json()["message"]

        demo_orders = client.get("/api/v1/orders?is_demo=true&page_size=1", headers=auth_headers)
        assert demo_orders.status_code == 200
        assert demo_orders.json()["total"] == 1_000
        assert demo_orders.json()["items"][0]["is_demo"] is True

        non_demo_orders = client.get("/api/v1/orders?is_demo=false&page_size=1", headers=auth_headers)
        assert non_demo_orders.status_code == 200
        assert non_demo_orders.json()["total"] == non_demo_before

        invalid_delete = client.request(
            "DELETE",
            "/api/v1/demo-data",
            headers=auth_headers,
            json={"confirmation": "delete"},
        )
        assert invalid_delete.status_code == 422

        removed = client.request(
            "DELETE",
            "/api/v1/demo-data",
            headers=auth_headers,
            json={"confirmation": "DELETE DEMO DATA"},
        )
        assert removed.status_code == 200, removed.text
        assert removed.json()["order_count"] == 0

        with SessionLocal() as db:
            non_demo_after = db.scalar(select(func.count(Order.id)).where(Order.is_demo.is_(False))) or 0
        assert non_demo_after == non_demo_before
    finally:
        with SessionLocal() as db:
            delete_demo_data(db)
