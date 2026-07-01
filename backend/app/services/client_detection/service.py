from app.models.client import Client


def detect_client(sender: str, email_body: str, attachment_text: str, clients: list[Client]) -> Client | None:
    evidence = f"{sender} {email_body} {attachment_text}".lower()
    for client in clients:
        if client.email_domain.lower() in evidence or client.customer_number.lower() in evidence:
            return client
    return None
