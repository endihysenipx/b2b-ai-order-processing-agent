from __future__ import annotations

import html
import re
from decimal import Decimal, InvalidOperation
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

from pydantic import BaseModel, Field


class LutzOrderItem(BaseModel):
    model_number: str
    article_number: str
    quantity: int = Field(gt=0)
    position: str


class LutzOrder(BaseModel):
    store_address: str | None = None
    delivery_address: str | None = None
    preferred_delivery_week: str | None = None
    commission_name: str | None = None
    commission_number: str
    items: list[LutzOrderItem]


class ParsedLutzEmail(BaseModel):
    subject: str
    sender_email: str | None = None
    attachment_names: list[str]
    orders: list[LutzOrder]


class LutzEmailParseError(ValueError):
    """Raised when an email does not include a Lutz commission block."""


class LutzEmailParser:
    """Extract structured order data from Lutz purchase-order emails."""

    _store_pattern = re.compile(r"^\s*Filiale\s*:\s*(?P<value>.+?)\s*$", re.IGNORECASE)
    _delivery_pattern = re.compile(r"^\s*Anlieferung\s*:\s*(?P<value>.+?)\s*$", re.IGNORECASE)
    _delivery_week_pattern = re.compile(r"^\s*Liefertermin\s*:\s*(?P<value>.+?)\s*$", re.IGNORECASE)
    _week_pattern = re.compile(r"\bKW\s*(?P<week>\d{1,2})\s*/\s*(?P<year>\d{4})\b", re.IGNORECASE)
    _commission_pattern = re.compile(r"^\s*Komm\s*:\s*(?P<number>[A-Z0-9]+-\d+)\b", re.IGNORECASE)
    _item_pattern = re.compile(
        r"^\s*(?P<quantity>\d+(?:[.,]\d+)?)\s*x\s+"
        r"(?P<item_code>[A-Z0-9]+(?:-[A-Z0-9]+)+)\s+\((?P<position>[^)]*)\)",
        re.IGNORECASE,
    )

    def parse_bytes(self, message_bytes: bytes) -> ParsedLutzEmail:
        message = BytesParser(policy=policy.default).parsebytes(message_bytes)
        return self._parse_message(message)

    def parse_file(self, path: str | Path) -> ParsedLutzEmail:
        return self.parse_bytes(Path(path).read_bytes())

    def _parse_message(self, message: EmailMessage) -> ParsedLutzEmail:
        lines = self._normalise_lines(self._get_message_body(message))
        commission_indexes = [index for index, line in enumerate(lines) if self._commission_pattern.match(line)]
        if not commission_indexes:
            raise LutzEmailParseError("No Lutz commission block was found in this email.")

        orders = [
            self._parse_order_block(lines, commission_index, next_index)
            for commission_index, next_index in zip(commission_indexes, commission_indexes[1:] + [len(lines)], strict=True)
        ]
        return ParsedLutzEmail(
            subject=str(message.get("Subject", "")),
            sender_email=parseaddr(str(message.get("From", "")))[1] or None,
            attachment_names=[part.get_filename() or "unnamed-attachment" for part in message.iter_attachments()],
            orders=orders,
        )

    def _parse_order_block(self, lines: list[str], commission_index: int, next_commission_index: int) -> LutzOrder:
        commission_match = self._commission_pattern.match(lines[commission_index])
        if commission_match is None:
            raise LutzEmailParseError("Invalid Lutz commission block.")

        details_index = next(
            (
                index
                for index in range(commission_index + 1, next_commission_index)
                if lines[index].casefold().startswith("details zur bestellung")
            ),
            next_commission_index,
        )
        items = self._extract_items(lines[commission_index + 1 : details_index])
        delivery_week = self._find_last_value_before(lines, commission_index, self._delivery_week_pattern)

        return LutzOrder(
            store_address=self._find_last_value_before(lines, commission_index, self._store_pattern),
            delivery_address=self._find_last_value_before(lines, commission_index, self._delivery_pattern),
            preferred_delivery_week=self._normalise_delivery_week(delivery_week),
            commission_name=self._find_commission_name(lines, commission_index),
            commission_number=commission_match.group("number").upper(),
            items=items,
        )

    @staticmethod
    def _get_message_body(message: EmailMessage) -> str:
        body = message.get_body(preferencelist=("plain", "html"))
        if body is None:
            return ""
        content = body.get_content()
        if body.get_content_type() == "text/html":
            content = re.sub(r"(?i)<br\s*/?>", "\n", content)
            content = re.sub(r"(?i)</p\s*>", "\n", content)
            content = re.sub(r"<[^>]+>", " ", content)
            content = html.unescape(content)
        return content

    @staticmethod
    def _normalise_lines(text: str) -> list[str]:
        return [re.sub(r"\s+", " ", line).strip() for line in text.replace("\r", "").split("\n")]

    @staticmethod
    def _find_last_value_before(lines: list[str], index: int, pattern: re.Pattern[str]) -> str | None:
        for line in reversed(lines[:index]):
            match = pattern.match(line)
            if match:
                return match.group("value").strip()
        return None

    @staticmethod
    def _find_commission_name(lines: list[str], commission_index: int) -> str | None:
        for line in reversed(lines[max(0, commission_index - 3) : commission_index]):
            if not line or line.casefold().startswith("liefertermin"):
                continue
            return line
        return None

    def _normalise_delivery_week(self, value: str | None) -> str | None:
        if value is None:
            return None
        match = self._week_pattern.search(value)
        if match is None:
            return None
        return f"KW{int(match.group('week')):02d}/{match.group('year')}"

    def _extract_items(self, lines: list[str]) -> list[LutzOrderItem]:
        items: list[LutzOrderItem] = []
        for line in lines:
            match = self._item_pattern.match(line)
            if match is None or match.group("position").casefold().startswith("fpos:"):
                continue
            quantity = self._parse_quantity(match.group("quantity"))
            if quantity is None:
                continue
            model_number, article_number = match.group("item_code").upper().rsplit("-", maxsplit=1)
            items.append(
                LutzOrderItem(
                    model_number=model_number,
                    article_number=article_number,
                    quantity=quantity,
                    position=match.group("position").strip(),
                )
            )
        return items

    @staticmethod
    def _parse_quantity(value: str) -> int | None:
        try:
            quantity = Decimal(value.replace(",", "."))
        except InvalidOperation:
            return None
        if quantity <= 0 or quantity != quantity.to_integral_value():
            return None
        return int(quantity)


def parse_lutz_email(message_bytes: bytes) -> ParsedLutzEmail:
    """Parse a raw ``.eml`` message without saving it to the database."""

    return LutzEmailParser().parse_bytes(message_bytes)
