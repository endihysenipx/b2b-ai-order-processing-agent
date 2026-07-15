from app.services.aws_document_processing import LesninaMappedItem, LesninaTableMapper, LesninaTableMapping
from app.services.aws_document_processing.service import TextractTable, TextractTableCell
from app.services.email.lutz_parser import LutzOrder


def cell(row, column, text, confidence=99.0):
    return TextractTableCell(row=row, column=column, text=text, confidence=confidence)


def test_maps_pilot_style_lesnina_table_into_normalized_items():
    table = TextractTable(
        page=2,
        cells=[
            cell(1, 1, "Pos."),
            cell(1, 2, "ArtNr"),
            cell(1, 3, "Beschreibung"),
            cell(1, 5, "Menge"),
            cell(3, 1, "1"),
            cell(3, 2, "CQSP18TA-48327K", 98.4),
            cell(4, 3, "Schwebetürenschrank"),
            cell(4, 5, "1", 98.0),
            cell(5, 1, "1.1"),
            cell(5, 2, "OJ00-30155", 97.2),
            cell(5, 5, "1", 96.5),
            cell(6, 1, "1.2"),
            cell(6, 2, "OJ99-63826", 98.1),
            cell(6, 5, "1", 97.8),
        ],
    )

    result = LesninaTableMapper().map_tables([table])

    assert result.requires_review is False
    assert result.issues == []
    assert [(item.model_number, item.article_number, item.quantity, item.position) for item in result.items] == [
        ("CQSP18TA", "48327K", 1, "1"),
        ("OJ00", "30155", 1, "1.1"),
        ("OJ99", "63826", 1, "1.2"),
    ]


def test_low_confidence_and_invalid_quantity_are_routed_to_review():
    table = TextractTable(
        page=1,
        cells=[
            cell(1, 1, "Poz."),
            cell(1, 2, "Br.art."),
            cell(1, 3, "Količina"),
            cell(2, 1, "1"),
            cell(2, 2, "OJ00-30155", 82.0),
            cell(2, 3, "1", 85.0),
            cell(3, 1, "2"),
            cell(3, 2, "OJ99-63826"),
            cell(3, 3, "one"),
        ],
    )

    result = LesninaTableMapper().map_tables([table])

    assert result.requires_review is True
    assert len(result.items) == 1
    assert result.items[0].requires_review is True
    assert "below the 90.0% review threshold" in result.items[0].review_reasons[0]
    assert "invalid or missing quantity" in result.issues[0]


def test_merge_preserves_email_headers_and_adds_mapped_items():
    table = TextractTable(
        page=2,
        cells=[
            cell(1, 1, "Pos."),
            cell(1, 2, "ArtNr"),
            cell(1, 3, "Menge"),
            cell(2, 1, "1"),
            cell(2, 2, "OJ00-30155"),
            cell(2, 3, "2"),
        ],
    )
    mapping = LesninaTableMapper().map_tables([table])
    email_order = LutzOrder(
        delivery_address="Šijanska cesta 60, HR-52215 Vodnjan",
        preferred_delivery_week="KW37/2026",
        commission_name="ROSSI",
        commission_number="HVSTUE-1",
        items=[],
    )

    result = LesninaTableMapper.merge_order(email_order, mapping)

    assert result.requires_review is False
    assert result.order.delivery_address == "Šijanska cesta 60, HR-52215 Vodnjan"
    assert result.order.commission_number == "HVSTUE-1"
    assert result.order.items[0].model_dump() == {
        "model_number": "OJ00",
        "article_number": "30155",
        "quantity": 2,
        "position": "1",
    }


def test_maps_combined_croatian_quantity_price_column_and_deduplicates_repeat_table():
    primary = TextractTable(
        page=3,
        cells=[
            cell(1, 1, "Poz."),
            cell(1, 2, "Br.art."),
            cell(1, 5, "KoličinBojed.cijenaUkup.cjena"),
            cell(3, 1, "1"),
            cell(3, 2, "CQ9122XP-33234"),
            cell(4, 5, "1 1.951,00"),
            cell(6, 1, "1.1"),
            cell(6, 2, "OJ99-53820"),
            cell(6, 5, "1 297,00"),
        ],
    )
    repeated = TextractTable(
        page=7,
        cells=[
            cell(1, 1, "Poz."),
            cell(1, 2, "Br.art."),
            cell(1, 5, "Količina"),
            cell(2, 1, "1.1"),
            cell(2, 2, "OJ99-53820", 95.0),
            cell(2, 5, "1", 95.0),
        ],
    )

    result = LesninaTableMapper().map_tables([primary, repeated])

    assert result.requires_review is False
    assert [(item.model_number, item.article_number, item.quantity) for item in result.items] == [
        ("CQ9122XP", "33234", 1),
        ("OJ99", "53820", 1),
    ]


def test_uses_quantity_column_left_of_merged_quantity_and_price_header():
    table = TextractTable(
        page=2,
        cells=[
            cell(1, 1, "Poz."),
            cell(1, 2, "Br.art."),
            cell(1, 6, "KoličinBojed.cijenaUkup.cijena"),
            cell(3, 1, "1"),
            cell(3, 2, "CQSN91XP-48408"),
            cell(4, 5, "1"),
            cell(4, 6, "1.608,00"),
            cell(5, 1, "1.1"),
            cell(5, 2, "OJ99-66018"),
            cell(5, 5, "2"),
            cell(5, 6, "493,00"),
        ],
    )

    result = LesninaTableMapper().map_tables([table])

    assert [(item.model_number, item.article_number, item.quantity) for item in result.items] == [
        ("CQSN91XP", "48408", 1),
        ("OJ99", "66018", 2),
    ]


def test_recognizes_serbian_quantity_header():
    table = TextractTable(
        page=3,
        cells=[
            cell(1, 1, "Poz."),
            cell(1, 2, "Br.art."),
            cell(1, 5, "Kollerinapo"),
            cell(2, 1, "1"),
            cell(2, 2, "OGSP7196-12555"),
            cell(2, 5, "1"),
        ],
    )

    result = LesninaTableMapper().map_tables([table])

    assert result.items[0].model_number == "OGSP7196"
    assert result.items[0].quantity == 1


def test_shifted_continuation_quantities_are_consumed_once_in_item_order():
    table = TextractTable(
        page=2,
        cells=[
            cell(1, 1, "Poz."),
            cell(1, 2, "Br.art."),
            cell(1, 5, "Količina"),
            cell(3, 1, "1.1"),
            cell(3, 2, "OJ99-53818"),
            cell(4, 1, "1.2"),
            cell(4, 2, "OJ99-53875"),
            cell(4, 3, "Description of previous item"),
            cell(4, 5, "1"),
            cell(5, 1, "1.3"),
            cell(5, 2, "OJ00-30156"),
            cell(5, 3, "Description of second item"),
            cell(5, 5, "1"),
            cell(6, 3, "Description of third item"),
            cell(6, 5, "1"),
        ],
    )

    result = LesninaTableMapper().map_tables([table])

    assert [(item.article_number, item.quantity) for item in result.items] == [
        ("53818", 1),
        ("53875", 1),
        ("30156", 1),
    ]


def test_distorted_serbian_header_and_ocr_letter_i_quantity_are_supported():
    table = TextractTable(
        page=3,
        cells=[
            cell(1, 1, "Poz."),
            cell(1, 2, "Br.art."),
            cell(1, 5, "KoClemaapo"),
            cell(1, 6, "komadukupna"),
            cell(1, 7, "cena"),
            cell(2, 1, "1"),
            cell(2, 2, "CQAW9699-76502"),
            cell(2, 5, "I"),
        ],
    )

    result = LesninaTableMapper().map_tables([table])

    assert result.items[0].model_number == "CQAW9699"
    assert result.items[0].quantity == 1


def test_ocr_position_i_and_malformed_repeat_position_are_normalized_and_deduplicated():
    primary = TextractTable(
        page=2,
        cells=[
            cell(1, 1, "Pos."),
            cell(1, 2, "ArtNr"),
            cell(1, 5, "Menge"),
            cell(2, 1, "I"),
            cell(2, 2, "OGAW81SP96-24907"),
            cell(2, 5, "1"),
        ],
    )
    repeat = TextractTable(
        page=7,
        cells=[
            cell(1, 1, "Pos."),
            cell(1, 2, "ArtNr"),
            cell(1, 5, "Menge"),
            cell(2, 1, ","),
            cell(2, 2, "OGAW81SP96-24907"),
            cell(2, 5, "1"),
        ],
    )

    result = LesninaTableMapper().map_tables([primary, repeat])

    assert [(item.position, item.article_number) for item in result.items] == [("1", "24907")]


def test_multiple_commission_blocks_receive_their_matching_position_groups():
    mapping = LesninaTableMapping(
        items=[
            LesninaMappedItem(model_number="CQAW96TB", article_number="60930", quantity=1, position="1", source_row=1),
            LesninaMappedItem(model_number="OJ99", article_number="14327", quantity=1, position="1.1", source_row=2),
            LesninaMappedItem(model_number="CQSP96TB", article_number="48362", quantity=1, position="2", source_row=3),
            LesninaMappedItem(model_number="OJ00", article_number="13076", quantity=1, position="2.1", source_row=4),
        ]
    )
    orders = [
        LutzOrder(commission_number="KJPBYZ-1", items=[]),
        LutzOrder(commission_number="KJPBYZ-2", items=[]),
    ]

    result = LesninaTableMapper.merge_email_orders(orders, mapping)

    assert [item.article_number for item in result.orders[0].order.items] == ["60930", "14327"]
    assert [item.article_number for item in result.orders[1].order.items] == ["48362", "13076"]
