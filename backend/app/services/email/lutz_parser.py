from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

from pydantic import BaseModel, Field


class LutzOrderItem(BaseModel):
    model_number: str | None = None
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
    _commission_pattern = re.compile(
        r"^\s*(?:Komm|Lagerbestellung)\s*:\s*(?P<number>[A-Z0-9]+-\d+)\b", re.IGNORECASE
    )
    _item_pattern = re.compile(
        r"^\s*(?P<quantity>\d+(?:[.,]\d+)?)\s*x\s+"
        r"(?P<item_code>[A-Z0-9]+(?:-[A-Z0-9]+)+)\s+\((?P<position>[^)]*)\)",
        re.IGNORECASE,
    )
    _manual_quantity_pattern = re.compile(r"^\s*(?P<quantity>\d+(?:[.,]\d+)?)\s+", re.IGNORECASE)
    _manual_code_pattern = re.compile(
        r"(?P<code>(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9/-]*\d)[A-Z0-9]+(?:[-/][A-Z0-9]+)+)\b", re.IGNORECASE
    )
    _explicit_typ_code_pattern = re.compile(r"\bTYP\s*:?\s*(?P<code>[A-Z0-9]+(?:[-/][A-Z0-9]+)?)\b", re.IGNORECASE)
    _article_only_pattern = re.compile(r"\bTYP\s*:\s*(?P<article>\d{4,})\b", re.IGNORECASE)
    _article_then_model_pattern = re.compile(
        r"\bTYP\s*:?\s*(?P<article>\d{4,})\s*,\s*(?P<model>(?=[A-Z0-9]*\d)[A-Z][A-Z0-9]{2,})\b",
        re.IGNORECASE,
    )

    def parse_bytes(self, message_bytes: bytes) -> ParsedLutzEmail:
        message = BytesParser(policy=policy.default).parsebytes(message_bytes)
        return self._parse_message(message)

    def parse_file(self, path: str | Path) -> ParsedLutzEmail:
        return self.parse_bytes(Path(path).read_bytes())

    def _parse_message(self, message: EmailMessage) -> ParsedLutzEmail:
        xml_orders = self._parse_xml_attachments(message)
        if xml_orders:
            return ParsedLutzEmail(
                subject=str(message.get("Subject", "")),
                sender_email=parseaddr(str(message.get("From", "")))[1] or None,
                attachment_names=[part.get_filename() or "unnamed-attachment" for part in message.iter_attachments()],
                orders=xml_orders,
            )

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
                if lines[index].casefold().startswith(("details zur bestellung", "detaily k objedn"))
            ),
            next_commission_index,
        )
        items = self._extract_items(lines[commission_index + 1 : details_index])
        delivery_week = self._find_last_value_before(lines, commission_index, self._delivery_week_pattern)

        return LutzOrder(
            store_address=self._find_last_value_before(lines, commission_index, self._store_pattern)
            or self._find_company_store_address(lines),
            delivery_address=self._find_last_value_before(lines, commission_index, self._delivery_pattern),
            preferred_delivery_week=self._normalise_delivery_week(delivery_week),
            commission_name=(
                None
                if lines[commission_index].casefold().startswith("lagerbestellung")
                else self._find_commission_name(lines, commission_index)
            ),
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
            position = self._normalise_position(match.group("position"))
            items.append(
                LutzOrderItem(
                    model_number=model_number,
                    article_number=article_number,
                    quantity=quantity,
                    position=position,
                )
            )
        if items:
            return self._deduplicate_items(items)
        return self._extract_manual_items(lines)

    def _extract_manual_items(self, lines: list[str]) -> list[LutzOrderItem]:
        # The Czech order text is followed by a German translation of the same
        # product. Only the original section is authoritative.
        original_lines = []
        for line in lines:
            if "übersetzung zu oben" in line.casefold():
                break
            original_lines.append(line)

        quantity: int | None = None
        for index, line in enumerate(original_lines):
            quantity_match = self._manual_quantity_pattern.match(line)
            if quantity_match:
                quantity = self._parse_quantity(quantity_match.group("quantity"))
            if quantity is None:
                continue

            search_text = " ".join(original_lines[index : min(index + 4, len(original_lines))])
            article_then_model = self._article_then_model_pattern.search(search_text)
            if article_then_model:
                return [
                    LutzOrderItem(
                        model_number=article_then_model.group("model").upper(),
                        article_number=article_then_model.group("article").upper(),
                        quantity=quantity,
                        position="body",
                    )
                ]
            explicit_code = self._explicit_typ_code_pattern.search(search_text)
            if explicit_code and any(separator in explicit_code.group("code") for separator in "-/"):
                first, second = re.split(r"[-/]", explicit_code.group("code").upper(), maxsplit=1)
                model, article = (second, first) if first.isdigit() and not second.isdigit() else (first, second)
                return [
                    LutzOrderItem(
                        model_number=model,
                        article_number=article,
                        quantity=quantity,
                        position="body",
                    )
                ]
            article_only = self._article_only_pattern.search(search_text)
            if article_only:
                return [
                    LutzOrderItem(
                        model_number=None,
                        article_number=article_only.group("article").upper(),
                        quantity=quantity,
                        position="body",
                    )
                ]
            for candidate_line in original_lines[index + 1 : min(index + 4, len(original_lines))]:
                code_match = self._manual_code_pattern.search(candidate_line)
                if code_match:
                    code = code_match.group("code").upper().replace("/", "-")
                    model, article = code.rsplit("-", maxsplit=1)
                    return [
                        LutzOrderItem(
                            model_number=model,
                            article_number=article,
                            quantity=quantity,
                            position="body",
                        )
                    ]
        return []

    @staticmethod
    def _deduplicate_items(items: list[LutzOrderItem]) -> list[LutzOrderItem]:
        unique: list[LutzOrderItem] = []
        seen: set[tuple[str | None, str, int, str]] = set()
        for item in items:
            key = (item.model_number, item.article_number, item.quantity, item.position)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    @staticmethod
    def _normalise_position(value: str) -> str:
        position = value.strip()
        if re.fullmatch(r"\d+(?:[.,]\d+)*", position):
            return position.replace(",", ".")
        return position

    @staticmethod
    def _find_company_store_address(lines: list[str]) -> str | None:
        for index, line in enumerate(lines):
            if line.casefold().startswith("xlcz n") and index + 1 < len(lines):
                return lines[index + 1] or None
            if line.casefold().startswith("xlch ") and "," in line:
                return line.split(",", maxsplit=1)[1].strip() or None
            if re.match(r"^(?:PC|LE)\s*:?(?:\s+|$)", line, re.IGNORECASE):
                return re.sub(r"^(?:PC|LE)\s*:?\s*", "", line, flags=re.IGNORECASE).strip() or None
        return None

    def _parse_xml_attachments(self, message: EmailMessage) -> list[LutzOrder]:
        orders: list[LutzOrder] = []
        for part in message.iter_attachments():
            if not (part.get_filename() or "").casefold().endswith(".xml"):
                continue
            payload = part.get_payload(decode=True) or b""
            try:
                root = ET.fromstring(payload)
            except ET.ParseError:
                continue
            for head in root.findall(".//HEAD"):
                order_number = (head.findtext("OrderNumber") or "").strip()
                compact_number = re.sub(r"\s+", "-", order_number)
                if not re.fullmatch(r"[A-Z0-9]+-\d+", compact_number, re.IGNORECASE):
                    continue
                items: list[LutzOrderItem] = []
                for line in head.findall("LINE"):
                    article = (line.findtext("ProductNumber") or "").strip()
                    quantity = self._parse_quantity((line.findtext("OrderQuantity") or "").strip())
                    if not article or quantity is None:
                        continue
                    items.append(
                        LutzOrderItem(
                            model_number=None,
                            article_number=article.upper(),
                            quantity=quantity,
                            position=(line.findtext("LineItemNumber") or "XML").strip(),
                        )
                    )
                orders.append(
                    LutzOrder(
                        store_address=self._format_xml_address(head, "BY"),
                        delivery_address=self._format_xml_address(head, "DP"),
                        preferred_delivery_week=self._xml_delivery_week(head.findtext("RequestedDeliveryDate")),
                        commission_name=(head.findtext("Commission") or "").strip() or None,
                        commission_number=compact_number.upper(),
                        items=items,
                    )
                )
        return orders

    @staticmethod
    def _format_xml_address(head: ET.Element, party_flag: str) -> str | None:
        for address in head.findall("NAD"):
            if (address.findtext("FlagOfParty") or "").strip() != party_flag:
                continue
            country = (address.findtext("ISOCountryCode") or "").strip()
            postal = (address.findtext("PostalCode") or "").strip()
            city = (address.findtext("City") or "").strip()
            locality = "-".join(value for value in (country, postal) if value)
            return ", ".join(
                value
                for value in (
                    (address.findtext("Name1") or "").strip(),
                    (address.findtext("Street1") or "").strip(),
                    " ".join(value for value in (locality, city) if value),
                )
                if value
            ) or None
        return None

    @staticmethod
    def _xml_delivery_week(value: str | None) -> str | None:
        value = (value or "").strip()
        if not re.fullmatch(r"\d{6}", value):
            return None
        return f"KW{int(value[4:]):02d}/{value[:4]}"

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
