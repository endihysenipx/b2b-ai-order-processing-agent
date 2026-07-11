from email.message import EmailMessage

from app.services.email.intake import ClientProfile, parse_email_intake


def build_email(subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None) -> bytes:
    message = EmailMessage()
    message["From"] = "crm@staudmoebel.de"
    message["To"] = "bestellungen@example.com"
    message["Subject"] = subject
    message.set_content(body)
    for filename, content in attachments or []:
        message.add_attachment(content, maintype="application", subtype="octet-stream", filename=filename)
    return message.as_bytes()


def test_lesnina_tiff_order_routes_to_ocr_with_header_fields():
    result = parse_email_intake(
        build_email(
            "Bestellung KJPBYZ von Lutz",
            """
            ANLIEFERUNG: Ulica Dusana Vukotica 7, HR-10090 ZAGREB
            Liefertermin: KW38/2026, NICHT FRUEHER, NICHT SPAETER
            ZELIC
            Komm: KJPBYZ-1 (ArtNr: 05310015/1M)
            1.00 ORMAR S KLASICNIM VRATIMA
            PREMA SKICI I SPECIFIKACIJI BROJ 10508
            """,
            attachments=[("EX-00005.TIF", b"tiff-content")],
        )
    )

    assert result.client_profile == "lesnina"
    assert result.client_detection.confidence >= 0.65
    assert result.client_detection.is_manual_override is False
    assert result.message_type == "order"
    assert result.next_action == "needs_ocr"
    assert result.ocr_attachment_names == ["EX-00005.TIF"]
    assert result.orders[0].model_dump() == {
        "store_address": None,
        "delivery_address": "Ulica Dusana Vukotica 7, HR-10090 ZAGREB",
        "preferred_delivery_week": "KW38/2026",
        "commission_name": "ZELIC",
        "commission_number": "KJPBYZ-1",
        "items": [],
    }


def test_lesnina_tip_text_only_order_is_ready_for_validation():
    result = parse_email_intake(
        build_email(
            "Bestellung IP1G7M von Lutz",
            """
            ANLIEFERUNG: Moemax Split, HR-21204 Dugopolje
            Liefertermin: KW35/2026, NICHT FRUEHER, NICHT SPAETER
            PUTNIK
            Komm: IP1G7M-1 (ArtNr: 05310183/13)
            TIP: LUAW71SP96-92764, BIJELO STAKLO/OGLEDALO, 3 VRATA
            """,
        ),
        ClientProfile.LESNINA,
    )

    assert result.next_action == "ready_for_validation"
    assert result.ocr_attachment_names == []
    assert result.orders[0].items[0].model_number == "LUAW71SP96"
    assert result.orders[0].items[0].article_number == "92764"


def test_lutz_profile_is_detected_from_body_and_attachment_signals():
    result = parse_email_intake(
        build_email(
            "Bestellung UH4Z6A von Lutz",
            """
            Filiale: D-36043 Fulda, Heidelsteinstraße 18
            Anlieferung: Industriestr. 25, D-21493 Schwarzenbek
            Liefertermin: KW26/2026
            SARNES
            Komm: UH4Z6A-4
            1 x CQ9696TA-04617 (1) Schwebetürenschrank
            Details zur Bestellung:
            """,
            attachments=[("UH_CTW_27745-2.dhp", b"dhp-content")],
        )
    )

    assert result.client_profile == "lutz"
    assert result.client_detection.confidence >= 0.65
    assert "Contains a Lutz DHP planning attachment." in result.client_detection.evidence
    assert result.next_action == "ready_for_validation"


def test_unknown_client_format_routes_to_manual_review():
    result = parse_email_intake(build_email("Question", "Can you help with this document?"))

    assert result.client_profile is None
    assert result.client_detection.confidence == 0
    assert result.next_action == "manual_review"


def test_lesnina_return_and_confirmation_request_do_not_create_orders():
    return_result = parse_email_intake(
        build_email("Retoure Endfrist", "Lesnina H d.o.o. Bitte erfassen Sie die Retoure bis zum Ablauf der Endfrist."),
    )
    confirmation_result = parse_email_intake(
        build_email("AB", "Lesnina Rijeka. Hallo, ich bitte Sie um AB fur KNC7V8 und KNC84W."),
    )

    assert (return_result.message_type, return_result.next_action, return_result.orders) == (
        "return",
        "return_review",
        [],
    )
    assert return_result.client_profile == "lesnina"
    assert (confirmation_result.message_type, confirmation_result.next_action, confirmation_result.orders) == (
        "confirmation_request",
        "confirmation_response",
        [],
    )
    assert confirmation_result.client_profile == "lesnina"
    assert confirmation_result.reference_codes == ["KNC7V8", "KNC84W"]


def test_client_aware_preview_endpoint_uses_the_selected_profile(client, auth_headers):
    response = client.post(
        "/api/v1/emails/preview",
        files={
            "file": (
                "lesnina.eml",
                build_email(
                    "Bestellung IP1G7M von Lutz",
                    "ANLIEFERUNG: Moemax Split, HR-21204 Dugopolje\nAviso per Mail\nPUTNIK\nKomm: IP1G7M-1\nTIP: LUAW71SP96-92764",
                ),
                "message/rfc822",
            )
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["client_profile"] == "lesnina"
    assert response.json()["client_detection"]["is_manual_override"] is False
    assert response.json()["orders"][0]["items"][0]["model_number"] == "LUAW71SP96"
