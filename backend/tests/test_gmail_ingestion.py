from email.message import EmailMessage
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.attachment import Attachment
from app.models.email import Email
from app.models.order import Order
from app.models.order_item import OrderItem
from app.services.email.gmail import GmailMessage
from app.services.email.ingestion import GmailIngestionService


class FakeGmailGateway:
    def __init__(self, messages: list[GmailMessage]) -> None:
        self.messages = messages
        self.marked_as_read: list[str] = []
        self.closed = False

    def fetch_messages(self, limit: int) -> list[GmailMessage]:
        return self.messages[:limit]

    def mark_as_read(self, uid: str) -> None:
        self.marked_as_read.append(uid)

    def close(self) -> None:
        self.closed = True


def build_gmail_order(message_id: str = "<gmail-intake-test@example.com>") -> bytes:
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["From"] = "orders@lutz-test.example"
    message["To"] = "supplier@gmail.com"
    message["Subject"] = "Bestellung UH4Z6A von Lutz"
    message.set_content(
        """
        Filiale: D-36043 Fulda, Heidelsteinstrasse 18
        Anlieferung: Industriestr. 25, D-21493 Schwarzenbek
        Liefertermin: KW26/2026
        SARNES
        Komm: UH4Z6A-4
        2 x CQ9696TA-04617 (1) Schwebetuerenschrank
        Details zur Bestellung:
        """
    )
    message.add_attachment(b"planning-data", maintype="application", subtype="octet-stream", filename="plan.dhp")
    return message.as_bytes()


def test_gmail_poll_imports_order_and_prevents_duplicates(tmp_path):
    gateway = FakeGmailGateway([GmailMessage(uid="101", content=build_gmail_order())])
    settings = Settings(
        gmail_username="supplier@gmail.com",
        gmail_app_password="test-app-password",
        gmail_mark_as_read=True,
        storage_root=str(tmp_path),
    )
    service = GmailIngestionService(settings, SessionLocal, gateway_factory=lambda: gateway)

    first = service.poll_once()
    second = service.poll_once()

    assert first.model_dump(exclude={"errors"}) == {
        "fetched": 1,
        "imported": 1,
        "duplicates": 0,
        "orders_created": 1,
        "manual_review": 0,
        "failed": 0,
    }
    assert second.duplicates == 1
    assert gateway.marked_as_read == ["101", "101"]
    assert gateway.closed is True

    with SessionLocal() as db:
        stored_email = db.scalar(select(Email).where(Email.external_message_id == "<gmail-intake-test@example.com>"))
        assert stored_email is not None
        order = db.scalar(select(Order).where(Order.email_id == stored_email.id))
        assert order is not None
        assert order.ticket_number == "UH4Z6A"
        assert order.commission_number == "UH4Z6A-4"
        assert order.delivery_week == "KW26/2026"
        assert order.status == "OK"
        item = db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
        assert (item.model_number, item.article_number, item.quantity) == ("CQ9696TA", "04617", 2)
        attachment = db.scalar(select(Attachment).where(Attachment.email_id == stored_email.id))
        assert attachment is not None
        assert attachment.file_name == "plan.dhp"
        assert tmp_path in Path(attachment.file_path).parents


def test_gmail_status_endpoint_does_not_expose_password(client, auth_headers):
    response = client.get("/api/v1/emails/gmail/status", headers=auth_headers)

    assert response.status_code == 200
    assert "password" not in response.text.casefold()
    assert response.json()["folder"] == "INBOX"


def test_order_intelligence_upload_creates_explainable_idempotent_order(client, auth_headers):
    content = build_gmail_order("<order-intelligence-upload@example.com>")
    files = {"file": ("mentor-demo.eml", content, "message/rfc822")}

    response = client.post("/api/v1/emails/intelligence/import", files=files, headers=auth_headers)
    duplicate = client.post("/api/v1/emails/intelligence/import", files=files, headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["duplicate"] is False
    assert payload["classification"] == "order"
    assert payload["client_profile"] == "lutz"
    assert payload["client_confidence"] >= 0.65
    assert payload["requires_review"] is False
    assert payload["clarification_draft"] is None
    assert len(payload["orders"]) == 1
    assert payload["orders"][0]["status"] == "OK"
    assert payload["orders"][0]["item_count"] == 1
    assert [step["key"] for step in payload["timeline"]] == [
        "received",
        "classified",
        "client",
        "extracted",
        "validated",
        "review",
    ]
    assert all(step["status"] == "completed" for step in payload["timeline"])

    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["orders"][0]["id"] == payload["orders"][0]["id"]


def test_order_intelligence_upload_is_admin_only(client):
    response = client.post(
        "/api/v1/emails/intelligence/import",
        files={"file": ("order.eml", build_gmail_order("<unauthorized-upload@example.com>"), "message/rfc822")},
    )

    assert response.status_code == 401
