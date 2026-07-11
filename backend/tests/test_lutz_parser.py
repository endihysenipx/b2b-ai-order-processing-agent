from email.message import EmailMessage

from app.services.email.lutz_parser import parse_lutz_email


def build_lutz_email(body: str) -> bytes:
    message = EmailMessage()
    message["From"] = "OFFICE-LUTZ@LUTZ.AT"
    message["To"] = "Bestellungen_crm@example.com"
    message["Subject"] = "Bestellung UH4Z6A von Lutz"
    message.set_content(body)
    message.add_attachment(b"pdf-content", maintype="application", subtype="pdf", filename="UH_CTW_27745-2_05310214-YC.pdf")
    message.add_attachment(b"dhp-content", maintype="application", subtype="octet-stream", filename="UH_CTW_27745-2.dhp")
    return message.as_bytes()


def test_parser_extracts_requested_lutz_fields_and_ignores_detail_repeats():
    result = parse_lutz_email(
        build_lutz_email(
            """
            Filiale: D-36043 Fulda, Heidelsteinstraße 18
            Anlieferung: Industriestr. 25, D-21493 Schwarzenbek
            Liefertermin: KW26/2026, NICHT FRUEHER NICHT SPAETER

            SARNES
            Komm: UH4Z6A-4 Gebiet: 1C4 (ArtNr: 05310214/YC)

            1.00 BEREICH JUGENDZIMMER SYSTEM ONE
            1 x CQ9696TA-04617 (1) Schwebetürenschrank 3-trg
            2 x OJ00-11937 (1.1) Kleiderstange Sockelbreite
            1 x OJ00-11945 (1.2) Krawattenhalter
            Details zur Bestellung:
            1 x CQ9696TA-04617 (FPos: 1) Schwebetürenschrank 3-trg
            """
        )
    )

    assert result.sender_email == "OFFICE-LUTZ@LUTZ.AT"
    assert result.attachment_names == ["UH_CTW_27745-2_05310214-YC.pdf", "UH_CTW_27745-2.dhp"]
    assert len(result.orders) == 1
    assert result.orders[0].model_dump() == {
        "store_address": "D-36043 Fulda, Heidelsteinstraße 18",
        "delivery_address": "Industriestr. 25, D-21493 Schwarzenbek",
        "preferred_delivery_week": "KW26/2026",
        "commission_name": "SARNES",
        "commission_number": "UH4Z6A-4",
        "items": [
            {"model_number": "CQ9696TA", "article_number": "04617", "quantity": 1, "position": "1"},
            {"model_number": "OJ00", "article_number": "11937", "quantity": 2, "position": "1.1"},
            {"model_number": "OJ00", "article_number": "11945", "quantity": 1, "position": "1.2"},
        ],
    }


def test_parser_creates_separate_orders_for_multiple_commission_blocks():
    result = parse_lutz_email(
        build_lutz_email(
            """
            Filiale: D-68309 Mannheim, Spreewaldallee 40
            Anlieferung: Spreewaldallee 38, 68309 Mannheim
            Liefertermin: KW36/2026, NICHT FRUEHER NICHT SPAETER
            JUNGE
            Komm: M1FGMA-1 Gebiet: MA2 (ArtNr: 05310023/YB)
            1 x OF961899-27523G (2) Konsole
            Details zur Bestellung:
            1 x OF961899-27523G (FPos: 2) Konsole

            Liefertermin: KW37/2026, NICHT FRUEHER NICHT SPAETER
            JUNGE
            Komm: M1FGMA-2 Gebiet: MA2 (ArtNr: 05310214/YB)
            1 x CQ9618XP-61744 (1) Schwebetürenschrank
            Details zur Bestellung:
            1 x CQ9618XP-61744 (FPos: 1) Schwebetürenschrank
            """
        )
    )

    assert [(order.commission_number, order.preferred_delivery_week) for order in result.orders] == [
        ("M1FGMA-1", "KW36/2026"),
        ("M1FGMA-2", "KW37/2026"),
    ]
    assert result.orders[0].items[0].model_number == "OF961899"
    assert result.orders[1].items[0].article_number == "61744"


def test_lutz_preview_endpoint_returns_a_non_persistent_parse(client, auth_headers):
    response = client.post(
        "/api/v1/emails/lutz-preview",
        files={"file": ("lutz.eml", build_lutz_email("SARNES\nKomm: UH4Z6A-4\n1 x CQ9696TA-04617 (1)"), "message/rfc822")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["orders"][0]["items"][0]["article_number"] == "04617"
