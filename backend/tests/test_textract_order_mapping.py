from datetime import date
from decimal import Decimal

from app.services.aws_document_processing import TextractOrderMapper


def test_maps_lesnina_textract_table_to_structured_order():
    text = """
Datum: 24.07.2026
Skica uz ugovor: KUFPE5 / 2
Poz.
Br.art.
Opis
V/S/D
KoličinBojed.cijenaUkup.cijena
STAUD 0531 System One
I
CQSN91TA-48230
Schwebetürenschrank
298,0/222,3/68,0 cm
1
1.234,00
1.234,00
1.1
OJ99-33828
Fachboden
97,0/2,2/50,0 cm
1
86,00
86,00
1.2
OJ00-13076
Kleiderstange
1
123,00
123,00
1.3
OJ99-33829
Fachboden
147,0/2,2/50,0 cm
1
152,00
152,00
Ukupni zbroj:
EUR
1.595,00
1 X OJ99-33829
CQSN91 A-48230
"""

    mapping = TextractOrderMapper().map_text(text)

    assert mapping.order_date == date(2026, 7, 24)
    assert mapping.currency == "EUR"
    assert mapping.total_price == Decimal("1595.00")
    assert [item.model_dump() for item in mapping.items] == [
        {
            "model_number": "CQSN91TA",
            "article_number": "48230",
            "quantity": 1,
            "unit_price": Decimal("1234.00"),
            "total_price": Decimal("1234.00"),
            "currency": "EUR",
        },
        {
            "model_number": "OJ99",
            "article_number": "33828",
            "quantity": 1,
            "unit_price": Decimal("86.00"),
            "total_price": Decimal("86.00"),
            "currency": "EUR",
        },
        {
            "model_number": "OJ00",
            "article_number": "13076",
            "quantity": 1,
            "unit_price": Decimal("123.00"),
            "total_price": Decimal("123.00"),
            "currency": "EUR",
        },
        {
            "model_number": "OJ99",
            "article_number": "33829",
            "quantity": 1,
            "unit_price": Decimal("152.00"),
            "total_price": Decimal("152.00"),
            "currency": "EUR",
        },
    ]
