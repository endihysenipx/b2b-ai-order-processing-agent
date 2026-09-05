import io
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt
from openpyxl import Workbook
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.product import Product
from app.services.catalog_import import ImportProblem, preview_rows, preview_token, read_rows, verify_preview


def xlsx(rows):
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_csv_and_excel_keep_leading_zeros():
    for name, content in [("catalog.csv", b'\xef\xbb\xbfsku,description\n0012,"Item, blue"\n'),
                          ("catalog.xlsx", xlsx([["sku", "description"], ["0012", "Item, blue"]]))]:
        rows = preview_rows(name, content, [])
        assert rows[0]["after"]["sku"] == "0012"
        assert rows[0]["after"]["description"] == "Item, blue"
        assert rows[0]["errors"] == []


@pytest.mark.parametrize("rows", [
    [["sku", "description"], ["S1", "=1+1"]],
    [["sku", "sku"], ["S1", "S2"]],
    [["sku", "unknown"], ["S1", "value"]],
])
def test_invalid_workbooks_are_rejected(rows):
    with pytest.raises(ImportProblem):
        read_rows("catalog.xlsx", xlsx(rows))


def test_numeric_excel_sku_rejected():
    rows = preview_rows("catalog.xlsx", xlsx([["sku", "description"], [12, "Test"]]), [])
    assert "Text" in rows[0]["errors"][0]


def test_empty_oversized_and_excess_rows_rejected():
    for content in [b"sku,description\n", b"x" * (2 * 1024 * 1024 + 1),
                    b"sku,description\n" + b"S,Test\n" * 501]:
        with pytest.raises(ImportProblem):
            read_rows("catalog.csv", content)


def test_duplicates_and_alias_collisions():
    rows = preview_rows("catalog.csv", b"sku,description,aliases\nS1,One,A\nS1,Two,B\nS3,Three,A\n", [])
    assert rows[0]["errors"] and rows[1]["errors"]
    rows = preview_rows("catalog.csv", b"sku,description,aliases\nS1,One,A\nS2,Two,A\n", [])
    assert all(row["errors"] for row in rows)


def test_preview_token_bound_to_file_actor_client_and_expiration():
    token = preview_token("client", "admin", b"file", [])
    verify_preview(token, "client", "admin", b"file", [])
    for client_id, user_id, content in [("other", "admin", b"file"), ("client", "other", b"file"),
                                        ("client", "admin", b"changed")]:
        with pytest.raises(ImportProblem):
            verify_preview(token, client_id, user_id, content, [])
    claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    claims["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    expired = jwt.encode(claims, settings.secret_key, algorithm="HS256")
    with pytest.raises(ImportProblem):
        verify_preview(expired, "client", "admin", b"file", [])


@pytest.fixture
def import_customer():
    with SessionLocal() as db:
        customer = Client(client_name="Import test", customer_number="IMPORT-TEST", email_domain="import.test", extraction_prompt="")
        db.add(customer)
        db.commit()
        customer_id = customer.id
    yield customer_id
    with SessionLocal() as db:
        for product in db.scalars(select(Product).where(Product.client_id == customer_id)):
            db.delete(product)
        db.flush()
        db.delete(db.get(Client, customer_id))
        db.commit()


def test_api_preview_confirm_update_and_stale_token(client, auth_headers, import_customer):
    base = f"/api/v1/clients/{import_customer}/catalog-import"
    files = {"file": ("items.csv", b"sku,description,unit_price,currency\n001,Test,12.50,EUR\n", "text/csv")}
    preview = client.post(base + "/preview", headers=auth_headers, files=files)
    assert preview.status_code == 200, preview.text
    assert preview.json()["counts"]["create"] == 1
    with SessionLocal() as db:
        assert db.scalar(select(Product).where(Product.client_id == import_customer)) is None
    token = preview.json()["token"]
    assert client.post(base + "/confirm", headers=auth_headers, files=files,
                       data={"token": token, "confirmed": "false"}).status_code == 400
    response = client.post(base + "/confirm", headers=auth_headers, files=files,
                           data={"token": token, "confirmed": "true"})
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1
    # Replaying a committed preview cannot apply it again.
    assert client.post(base + "/confirm", headers=auth_headers, files=files,
                       data={"token": token, "confirmed": "true"}).status_code == 409
    updates = {"file": ("items.csv", b"sku,description,unit_price\n001,Changed,\n", "text/csv")}
    updated = client.post(base + "/preview", headers=auth_headers, files=updates).json()
    assert updated["rows"][0]["before"]["description"] == "Test"
    assert updated["rows"][0]["after"]["unit_price"] == "12.50"
    saved = client.post(base + "/confirm", headers=auth_headers, files=updates,
                        data={"token": updated["token"], "confirmed": "true"})
    assert saved.json()["updated"] == 1


def test_invalid_batch_cannot_partially_import(client, auth_headers, import_customer):
    base = f"/api/v1/clients/{import_customer}/catalog-import"
    files = {"file": ("items.csv", b"sku,description\nGOOD,Good\nBAD,\n", "text/csv")}
    preview = client.post(base + "/preview", headers=auth_headers, files=files).json()
    assert preview["can_import"] is False and preview["token"] is None
    assert client.post(base + "/confirm", headers=auth_headers, files=files,
                       data={"token": "invalid", "confirmed": "true"}).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(Product).where(Product.client_id == import_customer)) is None


def test_catalog_change_after_preview_blocks_batch(client, auth_headers, import_customer):
    base = f"/api/v1/clients/{import_customer}/catalog-import"
    files = {"file": ("items.csv", b"sku,description\nNEW,Test\n", "text/csv")}
    preview = client.post(base + "/preview", headers=auth_headers, files=files).json()
    with SessionLocal() as db:
        db.add(Product(client_id=import_customer, sku="OTHER", description="Added by another admin"))
        db.commit()
    response = client.post(base + "/confirm", headers=auth_headers, files=files,
                           data={"token": preview["token"], "confirmed": "true"})
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(Product).where(Product.client_id == import_customer, Product.sku == "NEW")) is None


def test_database_error_rolls_back_whole_batch(client, auth_headers, import_customer, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    base = f"/api/v1/clients/{import_customer}/catalog-import"
    files = {"file": ("items.csv", b"sku,description\nONE,One\nTWO,Two\n", "text/csv")}
    preview = client.post(base + "/preview", headers=auth_headers, files=files).json()

    def fail_commit(session):
        session.flush()
        raise IntegrityError("simulated conflict", {}, Exception("Conflict"))

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        response = client.post(base + "/confirm", headers=auth_headers, files=files,
                               data={"token": preview["token"], "confirmed": "true"})
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(Product).where(Product.client_id == import_customer)) is None


def test_template_contains_headers_only(client, auth_headers, import_customer):
    from app.services.catalog_import import COLUMNS

    response = client.get(f"/api/v1/clients/{import_customer}/catalog-import/template", headers=auth_headers)
    assert response.status_code == 200
    assert response.content.decode("utf-8-sig").splitlines() == [",".join(COLUMNS)]


def test_import_requires_admin(client, import_customer):
    from app.api.dependencies import get_current_user
    from app.main import app
    from app.models.user import User

    base = f"/api/v1/clients/{import_customer}/catalog-import"
    assert client.get(base + "/template").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: User(id="reader", role="operator")
    try:
        assert client.get(base + "/template").status_code == 403
        assert client.post(base + "/preview", files={"file": ("a.csv", b"sku,description\nA,Test")}).status_code == 403
        assert client.post(base + "/confirm", files={"file": ("a.csv", b"sku,description\nA,Test")},
                           data={"token": "x", "confirmed": "true"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user)
