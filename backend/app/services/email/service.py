from dataclasses import dataclass


@dataclass
class MockEmail:
    subject: str
    body: str
    sender_email: str
    attachments: list[str]


class EmailService:
    def fetch_new_emails(self) -> list[MockEmail]:
        raise NotImplementedError

    def download_attachments(self, email: MockEmail) -> list[str]:
        raise NotImplementedError

    def send_clarification_email(self, order_id: str, recipient: str, body: str) -> dict:
        raise NotImplementedError


class MockEmailService(EmailService):
    def fetch_new_emails(self) -> list[MockEmail]:
        return []

    def download_attachments(self, email: MockEmail) -> list[str]:
        return email.attachments

    def send_clarification_email(self, order_id: str, recipient: str, body: str) -> dict:
        return {
            "order_id": order_id,
            "recipient": recipient,
            "status": "simulated",
            "message": "Clarification email prepared and simulated; no Outlook message was sent.",
        }
