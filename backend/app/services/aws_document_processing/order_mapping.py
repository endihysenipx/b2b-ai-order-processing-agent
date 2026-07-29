from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field


class MappedOrderItem(BaseModel):
    model_number: str
    article_number: str
    quantity: int = 1
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    currency: str | None = None


class TextractOrderMapping(BaseModel):
    order_date: date | None = None
    total_price: Decimal | None = None
    currency: str | None = None
    items: list[MappedOrderItem] = Field(default_factory=list)


class TextractOrderMapper:
    """Maps the line-oriented output of a furniture order table without an LLM."""

    _item_code = re.compile(
        r"^(?P<model>[A-Z0-9][A-Z0-9 ]{1,30})\s*-\s*(?P<article>[A-Z0-9]{4,20})$",
        re.IGNORECASE,
    )
    _money = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2}$|^\d+,\d{2}$")
    _quantity = re.compile(r"^\d{1,3}$")
    _date = re.compile(r"\bDatum\s*:\s*(\d{2}\.\d{2}\.\d{4})\b", re.IGNORECASE)
    _currency = re.compile(r"^[A-Z]{3}$")

    def map_text(self, text: str) -> TextractOrderMapping:
        lines = [self._normalize_line(line) for line in text.splitlines()]
        lines = [line for line in lines if line]

        order_date = self._extract_order_date(lines)
        table_start = self._find_table_start(lines)
        table_end = self._find_table_end(lines, table_start)
        currency, order_total = self._extract_order_total(lines, table_end)

        items: list[MappedOrderItem] = []
        seen: set[tuple[str, str]] = set()
        table_lines = lines[table_start:table_end]
        code_positions = [
            (index, match)
            for index, line in enumerate(table_lines)
            if (match := self._item_code.fullmatch(line)) is not None
        ]

        for position, (index, match) in enumerate(code_positions):
            next_index = code_positions[position + 1][0] if position + 1 < len(code_positions) else len(table_lines)
            block = table_lines[index + 1 : next_index]
            model_number = re.sub(r"\s+", "", match.group("model")).upper()
            article_number = match.group("article").upper()
            key = (model_number, article_number)
            if key in seen:
                continue
            seen.add(key)

            quantity, unit_price, item_total = self._extract_item_values(block)
            items.append(
                MappedOrderItem(
                    model_number=model_number,
                    article_number=article_number,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=item_total,
                    currency=currency,
                )
            )

        return TextractOrderMapping(
            order_date=order_date,
            total_price=order_total,
            currency=currency,
            items=items,
        )

    @staticmethod
    def _normalize_line(line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()

    def _find_table_start(self, lines: list[str]) -> int:
        for index, line in enumerate(lines):
            if line.casefold() in {"poz.", "poz"}:
                return index + 1
        return 0

    @staticmethod
    def _find_table_end(lines: list[str], start: int) -> int:
        for index in range(start, len(lines)):
            if lines[index].casefold().startswith("ukupni zbroj"):
                return index
        return len(lines)

    def _extract_order_date(self, lines: list[str]) -> date | None:
        for line in lines:
            if match := self._date.search(line):
                try:
                    return datetime.strptime(match.group(1), "%d.%m.%Y").date()
                except ValueError:
                    return None
        return None

    def _extract_order_total(self, lines: list[str], table_end: int) -> tuple[str | None, Decimal | None]:
        currency: str | None = None
        total: Decimal | None = None
        for line in lines[table_end : table_end + 8]:
            if currency is None and self._currency.fullmatch(line):
                currency = line.upper()
            if total is None and self._money.fullmatch(line):
                total = self._parse_money(line)
        return currency, total

    def _extract_item_values(self, block: list[str]) -> tuple[int, Decimal | None, Decimal | None]:
        price_positions = [
            (index, self._parse_money(line))
            for index, line in enumerate(block)
            if self._money.fullmatch(line)
        ]
        prices = [price for _, price in price_positions if price is not None]
        first_price_index = price_positions[0][0] if price_positions else len(block)

        quantity = 1
        for line in block[:first_price_index]:
            if self._quantity.fullmatch(line):
                value = int(line)
                if value > 0:
                    quantity = value

        unit_price = prices[0] if prices else None
        item_total = prices[1] if len(prices) > 1 else None
        if unit_price is not None and item_total is None:
            item_total = unit_price * quantity
        return quantity, unit_price, item_total

    @staticmethod
    def _parse_money(value: str) -> Decimal | None:
        try:
            return Decimal(value.replace(".", "").replace(",", "."))
        except InvalidOperation:
            return None
