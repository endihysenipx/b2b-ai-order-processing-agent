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


def test_czech_manual_order_allows_missing_model_and_ignores_translation():
    result = parse_lutz_email(
        build_lutz_email(
            """
            XLCZ Nábytek s.r.o.
            CZ-25101 Cestlice, Prazská 135
            ANLIEFERUNG: XXXLUTZ CZ-15800 Praha 5, Narozni 1390/4
            Liefertermin: KW36/2026
            SEVIDOV
            Komm: PRKMJW-1
            1.00 KOMODA OMEGA
            TYP:80976,PROV:DEKOR SAND
            --Übersetzung zu oben angeführtem Text--
            1.00 KOMMODE OMEGA
            TYP:80976
            """
        )
    )

    assert result.orders[0].store_address == "CZ-25101 Cestlice, Prazská 135"
    assert result.orders[0].items[0].model_dump() == {
        "model_number": None,
        "article_number": "80976",
        "quantity": 1,
        "position": "body",
    }


def test_czech_warehouse_and_manual_article_model_formats_are_parsed():
    result = parse_lutz_email(
        build_lutz_email(
            """
            XLCZ Nábytek s.r.o.
            CZ-251 01 Cestlice, k Chotobuzi 331
            Anlieferung: k Chotobuzi 331, CZ-251 01 Cestlice
            Liefertermin: KW37/2026
            Lagerbestellung: DGRNS-1
            1.00 TÜRDÄMPFER SONATE/LUMOS
            ZB00/84006 NEUTRAL DEKOR
            Liefertermin: KW38/2026
            NOVAK
            Komm: PRKLYQ-1
            1.00 SKRÍN
            TYP 57384, PDSU71SP96
            """
        )
    )

    assert result.orders[0].items[0].model_dump(exclude={"position"}) == {
        "model_number": "ZB00",
        "article_number": "84006",
        "quantity": 1,
    }
    assert result.orders[1].items[0].model_dump(exclude={"position"}) == {
        "model_number": "PDSU71SP96",
        "article_number": "57384",
        "quantity": 1,
    }


def test_czech_eancom_xml_order_is_parsed_without_ocr():
    message = EmailMessage()
    message["From"] = "crm@staudmoebel.de"
    message["Subject"] = "Bestellung ZPNWLH von Lutz"
    message.set_content("Mail: OFFICE-LUTZ@LUTZ.AT\nXLCZ Nábytek s.r.o.")
    message.add_attachment(
        b"""<ORDERS><HEAD><OrderNumber>ZPNWLH  1</OrderNumber><Commission>NOVAKOVA</Commission>
        <RequestedDeliveryDate>202635</RequestedDeliveryDate>
        <NAD><FlagOfParty>BY</FlagOfParty><Name1>MX-Praha I</Name1><Street1>Kolbenova 50</Street1>
        <PostalCode>19000</PostalCode><City>Praha</City><ISOCountryCode>CZ</ISOCountryCode></NAD>
        <NAD><FlagOfParty>DP</FlagOfParty><Name1>RVZ-MX PRAHA</Name1><Street1>Kolbenova 50</Street1>
        <PostalCode>19000</PostalCode><City>Praha</City><ISOCountryCode>CZ</ISOCountryCode></NAD>
        <LINE><LineItemNumber>1</LineItemNumber><ProductNumber>28139</ProductNumber><OrderQuantity>1</OrderQuantity></LINE>
        </HEAD></ORDERS>""",
        maintype="application",
        subtype="xml",
        filename="order.xml",
    )

    result = parse_lutz_email(message.as_bytes())
    assert result.orders[0].commission_number == "ZPNWLH-1"
    assert result.orders[0].preferred_delivery_week == "KW35/2026"
    assert result.orders[0].items[0].model_number is None
    assert result.orders[0].items[0].article_number == "28139"


def test_translated_decimal_comma_position_is_deduplicated_without_merging_other_positions():
    result = parse_lutz_email(
        build_lutz_email(
            """
            Filiale: CZ-61900 Brno
            Anlieferung: Videnska 151/123, CZ-61900 Brno
            Liefertermin: KW36/2026
            BEHROVA
            Komm: BCRKE6-4
            2 x OJ00-11936 (2.2) Original item
            2 x OJ00-11936 (2,2) Translated duplicate
            2 x OJ00-11936 (4.1) Same article at a genuinely different position
            """
        )
    )

    assert [item.position for item in result.orders[0].items] == ["2.2", "4.1"]


def test_czech_manual_parser_prefers_typ_code_over_two_set_description_and_handles_reversed_code():
    result = parse_lutz_email(
        build_lutz_email(
            """
            XLCZ Nábytek s.r.o.
            CZ-25101 Cestlice, Prazská 135
            Anlieferung: CZ-30100 Plzen
            Liefertermin: KW38/2026
            Lagerbestellung: DGSGP-1
            2.00 VKLÁDACÍ POLICE TEXLINE, 2-SET
            TYP: ZB99-59725, TEXLINE
            Lagerbestellung: DGSGP-2
            1.00 INNENEINTEILUNG ZUBEHÖR
            TYP: 56847-ZB99, BESTEHEND AUS
            """
        )
    )

    assert [(order.commission_name, order.items[0].model_number, order.items[0].article_number) for order in result.orders] == [
        (None, "ZB99", "59725"),
        (None, "ZB99", "56847"),
    ]


def test_swiss_lutz_company_header_supplies_store_address():
    result = parse_lutz_email(
        build_lutz_email(
            """
            XLCH AG, Rössliweg 48, CH-4852 Rothrist
            Anlieferung: RÖSSLIWEG 43, CH-4852 ROTHRIST
            Liefertermin: KW36/2026
            DIBKE
            Komm: RJNJ3H-3
            1 x CQEG9199-76931C (2)
            """
        )
    )

    assert result.orders[0].store_address == "Rössliweg 48, CH-4852 Rothrist"


def test_lesnina_le_branch_header_supplies_store_address():
    result = parse_lutz_email(
        build_lutz_email(
            """
            Lesnina H. d.o.o. Slavonska avenija 106, 10000 Zagreb
            LE Pula, HR-52215 Vodnjan, Šijanska cesta 60
            Anlieferung: Šijanska cesta 60, HR-52215 Vodnjan
            Liefertermin: KW37/2026
            ROSSI
            Komm: HVSTUE-1
            PREMA SKICI
            """
        )
    )

    assert result.orders[0].store_address == "Pula, HR-52215 Vodnjan, Šijanska cesta 60"
