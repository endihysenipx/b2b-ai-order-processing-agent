def classify_email(subject: str, body: str, attachments: list[str]) -> str:
    text = f"{subject} {body}".lower()
    if "spam" in text:
        return "spam"
    if "order" in text or "purchase" in text or attachments:
        return "order"
    return "unknown"
