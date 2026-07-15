from __future__ import annotations

import html
import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from enum import StrEnum

from pydantic import BaseModel, Field

from app.services.email.lutz_parser import LutzEmailParseError, LutzEmailParser, LutzOrder, LutzOrderItem
from app.services.email.profile_detection import ClientProfile, ClientProfileDetection, ClientProfileDetector


class EmailMessageType(StrEnum):
    ORDER = "order"
    RETURN = "return"
    CONFIRMATION_REQUEST = "confirmation_request"
    UNKNOWN = "unknown"


class IntakeNextAction(StrEnum):
    READY_FOR_VALIDATION = "ready_for_validation"
    WAITING_FOR_REPLY = "waiting_for_reply"
    NEEDS_OCR = "needs_ocr"
    RETURN_REVIEW = "return_review"
    CONFIRMATION_RESPONSE = "confirmation_response"
    MANUAL_REVIEW = "manual_review"


class EmailIntakePreview(BaseModel):
    client_profile: ClientProfile | None = None
    client_detection: ClientProfileDetection
    message_type: EmailMessageType
    next_action: IntakeNextAction
    subject: str
    sender_email: str | None = None
    attachment_names: list[str]
    ocr_attachment_names: list[str] = Field(default_factory=list)
    orders: list[LutzOrder] = Field(default_factory=list)
    reference_codes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EmailIntakeParseError(ValueError):
    """Raised when an order email cannot be parsed using its selected client profile."""


class ClientEmailIntakeService:
    """Classify and preview client emails without saving them to the database."""

    _commission_pattern = re.compile(r"^\s*Komm\s*:\s*(?P<number>[A-Z0-9]+-\d+)\b", re.IGNORECASE)
    _tip_compound_pattern = re.compile(r"\bTIP\s*:\s*(?P<code>[A-Z0-9]+(?:-[A-Z0-9]+)+)\b", re.IGNORECASE)
    _tip_separate_pattern = re.compile(
        r"\bTIP\s*:\s*(?P<article>[A-Z0-9]+)\s*,\s*MOD\s*:\s*(?P<model>[A-Z0-9]+(?:-[A-Z0-9]+)+)\b",
        re.IGNORECASE,
    )
    _reference_pattern = re.compile(r"\b[A-Z]{2,}\d[A-Z0-9]{2,}\b", re.IGNORECASE)

    def __init__(self) -> None:
        self._lutz_parser = LutzEmailParser()
        self._profile_detector = ClientProfileDetector()

    def parse(self, message_bytes: bytes, client_profile: ClientProfile | None = None) -> EmailIntakePreview:
        message = BytesParser(policy=policy.default).parsebytes(message_bytes)
        body = self._get_message_body(message)
        attachment_names = [part.get_filename() or "unnamed-attachment" for part in message.iter_attachments()]
        message_type = self._classify_message(str(message.get("Subject", "")), body)
        reference_codes = self._find_reference_codes(f"{message.get('Subject', '')}\n{body}")
        client_detection = (
            self._profile_detector.manual_override(client_profile)
            if client_profile is not None
            else self._profile_detector.detect(str(message.get("Subject", "")), body, attachment_names)
        )
        detected_profile = client_detection.client_profile

        if detected_profile is None:
            return EmailIntakePreview(
                client_detection=client_detection,
                message_type=message_type,
                next_action=IntakeNextAction.MANUAL_REVIEW,
                subject=str(message.get("Subject", "")),
                sender_email=parseaddr(str(message.get("From", "")))[1] or None,
                attachment_names=attachment_names,
                reference_codes=reference_codes,
                notes=["No client profile was detected with sufficient confidence; assign a profile before processing."],
            )

        if message_type is not EmailMessageType.ORDER:
            return EmailIntakePreview(
                client_profile=detected_profile,
                client_detection=client_detection,
                message_type=message_type,
                next_action=self._next_action_for_non_order(message_type),
                subject=str(message.get("Subject", "")),
                sender_email=parseaddr(str(message.get("From", "")))[1] or None,
                attachment_names=attachment_names,
                reference_codes=reference_codes,
                notes=[self._note_for_non_order(message_type)],
            )

        try:
            parsed_order_email = self._lutz_parser.parse_bytes(message_bytes)
        except LutzEmailParseError as exc:
            raise EmailIntakeParseError(str(exc)) from exc

        orders = parsed_order_email.orders
        ocr_attachment_names: list[str] = []
        notes: list[str] = ["Order headers were extracted from the email body."]
        if detected_profile is ClientProfile.LESNINA:
            orders = self._apply_lesnina_text_only_items(orders, body)
            ocr_attachment_names = [
                filename for filename in attachment_names if filename.casefold().endswith((".tif", ".tiff"))
            ]
            if ocr_attachment_names:
                notes.append("Lesnina line items are expected in TIFF scans and require OCR before validation.")
            elif any(order.items for order in orders):
                notes.append("A Lesnina TIP/MOD text-only item was extracted from the email body.")
            else:
                notes.append("No TIFF attachment or text-only item reference was found; route this order to review.")
        else:
            notes.append("Lutz line items were extracted from the email body.")
            if any(item.model_number is None for order in orders for item in order.items):
                notes.append("At least one item has no model number; request the missing value from the customer.")

        return EmailIntakePreview(
            client_profile=detected_profile,
            client_detection=client_detection,
            message_type=message_type,
            next_action=self._next_order_action(detected_profile, orders, ocr_attachment_names),
            subject=parsed_order_email.subject,
            sender_email=parsed_order_email.sender_email,
            attachment_names=attachment_names,
            ocr_attachment_names=ocr_attachment_names,
            orders=orders,
            reference_codes=reference_codes,
            notes=notes,
        )

    def _apply_lesnina_text_only_items(self, orders: list[LutzOrder], body: str) -> list[LutzOrder]:
        lines = LutzEmailParser._normalise_lines(body)
        commission_indexes = [index for index, line in enumerate(lines) if self._commission_pattern.match(line)]
        order_sections = {
            self._commission_pattern.match(lines[index]).group("number").upper(): lines[index:next_index]
            for index, next_index in zip(commission_indexes, commission_indexes[1:] + [len(lines)], strict=True)
            if self._commission_pattern.match(lines[index])
        }
        updated_orders: list[LutzOrder] = []
        for order in orders:
            extracted_items = self._extract_lesnina_tip_items(order_sections.get(order.commission_number, []))
            updated_orders.append(order.model_copy(update={"items": extracted_items}) if extracted_items else order)
        return updated_orders

    def _extract_lesnina_tip_items(self, lines: list[str]) -> list[LutzOrderItem]:
        text = "\n".join(lines)
        separate_match = self._tip_separate_pattern.search(text)
        if separate_match:
            return [
                LutzOrderItem(
                    model_number=separate_match.group("model").upper(),
                    article_number=separate_match.group("article").upper(),
                    quantity=1,
                    position="TIP",
                )
            ]

        compound_match = self._tip_compound_pattern.search(text)
        if compound_match:
            model_number, article_number = compound_match.group("code").upper().rsplit("-", maxsplit=1)
            return [LutzOrderItem(model_number=model_number, article_number=article_number, quantity=1, position="TIP")]
        return []

    @staticmethod
    def _classify_message(subject: str, body: str) -> EmailMessageType:
        text = f"{subject}\n{body}".casefold()
        subject_text = subject.casefold()
        if "retoure" in text:
            return EmailMessageType.RETURN
        if "auftragsbestaetigung" in text or re.search(r"\bab\b", subject_text) or "schicken sie uns die ab" in text:
            return EmailMessageType.CONFIRMATION_REQUEST
        if "bestellung" in subject_text:
            return EmailMessageType.ORDER
        return EmailMessageType.UNKNOWN

    @staticmethod
    def _get_message_body(message: EmailMessage) -> str:
        body = message.get_body(preferencelist=("plain", "html"))
        if body is None:
            return ""
        content = body.get_content()
        if body.get_content_type() == "text/html":
            content = re.sub(r"(?i)<br\s*/?>", "\n", content)
            content = re.sub(r"(?i)</p\s*>", "\n", content)
            content = html.unescape(re.sub(r"<[^>]+>", " ", content))
        return content

    @classmethod
    def _find_reference_codes(cls, text: str) -> list[str]:
        return list(dict.fromkeys(match.group(0).upper() for match in cls._reference_pattern.finditer(text)))

    @staticmethod
    def _next_action_for_non_order(message_type: EmailMessageType) -> IntakeNextAction:
        if message_type is EmailMessageType.RETURN:
            return IntakeNextAction.RETURN_REVIEW
        if message_type is EmailMessageType.CONFIRMATION_REQUEST:
            return IntakeNextAction.CONFIRMATION_RESPONSE
        return IntakeNextAction.MANUAL_REVIEW

    @staticmethod
    def _note_for_non_order(message_type: EmailMessageType) -> str:
        if message_type is EmailMessageType.RETURN:
            return "This message is a return and must not create an order."
        if message_type is EmailMessageType.CONFIRMATION_REQUEST:
            return "This message requests an order confirmation and must not create an order."
        return "This message does not match a supported order, return, or confirmation format."

    @staticmethod
    def _next_order_action(
        client_profile: ClientProfile, orders: list[LutzOrder], ocr_attachment_names: list[str]
    ) -> IntakeNextAction:
        if client_profile is ClientProfile.LESNINA and ocr_attachment_names:
            return IntakeNextAction.NEEDS_OCR
        if any(item.model_number is None for order in orders for item in order.items):
            return IntakeNextAction.WAITING_FOR_REPLY
        if all(order.items for order in orders):
            return IntakeNextAction.READY_FOR_VALIDATION
        return IntakeNextAction.MANUAL_REVIEW


def parse_email_intake(message_bytes: bytes, client_profile: ClientProfile | None = None) -> EmailIntakePreview:
    """Classify and preview an email using automatic detection or an optional override."""

    return ClientEmailIntakeService().parse(message_bytes, client_profile)
