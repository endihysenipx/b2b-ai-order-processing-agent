from __future__ import annotations

import imaplib
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings


class GmailConfigurationError(ValueError):
    pass


class GmailConnectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class GmailMessage:
    uid: str
    content: bytes


class GmailGateway(Protocol):
    def fetch_messages(self, limit: int) -> list[GmailMessage]: ...

    def mark_as_read(self, uid: str) -> None: ...

    def close(self) -> None: ...


class GmailImapGateway:
    """Small Gmail IMAP adapter. SMTP is intentionally not used for inbox retrieval."""

    def __init__(self, settings: Settings, *, client: imaplib.IMAP4_SSL | None = None) -> None:
        if not settings.gmail_username or not settings.gmail_app_password:
            raise GmailConfigurationError(
                "Set GMAIL_USERNAME and GMAIL_APP_PASSWORD before enabling Gmail ingestion."
            )
        self.folder = settings.gmail_imap_folder
        self.search_criteria = settings.gmail_search_criteria
        try:
            self.client = client or imaplib.IMAP4_SSL(settings.gmail_imap_host, settings.gmail_imap_port)
            status, _ = self.client.login(settings.gmail_username, settings.gmail_app_password)
            if status != "OK":
                raise GmailConnectionError("Gmail rejected the IMAP login.")
            status, _ = self.client.select(self.folder)
            if status != "OK":
                raise GmailConnectionError(f"Gmail could not open IMAP folder {self.folder!r}.")
        except (imaplib.IMAP4.error, OSError) as exc:
            raise GmailConnectionError(f"Gmail IMAP connection failed: {exc}") from exc

    def fetch_messages(self, limit: int) -> list[GmailMessage]:
        try:
            status, search_data = self.client.uid("search", None, self.search_criteria)
            if status != "OK":
                raise GmailConnectionError("Gmail IMAP search failed.")
            uids = search_data[0].split()[-limit:]
            messages: list[GmailMessage] = []
            for raw_uid in uids:
                uid = raw_uid.decode("ascii")
                status, fetch_data = self.client.uid("fetch", uid, "(BODY.PEEK[])")
                if status != "OK":
                    raise GmailConnectionError(f"Gmail could not fetch message UID {uid}.")
                content = next(
                    (part[1] for part in fetch_data if isinstance(part, tuple) and isinstance(part[1], bytes)),
                    None,
                )
                if content is None:
                    raise GmailConnectionError(f"Gmail returned no content for message UID {uid}.")
                messages.append(GmailMessage(uid=uid, content=content))
            return messages
        except imaplib.IMAP4.error as exc:
            raise GmailConnectionError(f"Gmail IMAP request failed: {exc}") from exc

    def mark_as_read(self, uid: str) -> None:
        try:
            status, _ = self.client.uid("store", uid, "+FLAGS", r"(\Seen)")
            if status != "OK":
                raise GmailConnectionError(f"Gmail could not mark message UID {uid} as read.")
        except imaplib.IMAP4.error as exc:
            raise GmailConnectionError(f"Gmail IMAP request failed: {exc}") from exc

    def close(self) -> None:
        try:
            self.client.close()
        except (imaplib.IMAP4.error, OSError):
            pass
        try:
            self.client.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
