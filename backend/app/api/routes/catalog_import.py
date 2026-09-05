import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.routes.master_data import scoped_client
from app.db.session import get_db
from app.models.client import Client
from app.models.product import Product
from app.schemas.master_data import ProductInput
from app.services.catalog_import import COLUMNS, MAX_BYTES, ImportProblem, preview_rows, preview_token, verify_preview

router = APIRouter(prefix="/clients", tags=["catalog import"])
logger = logging.getLogger(__name__)


@router.get("/{client_id}/catalog-import/template")
def template(client_id: str, db: Session = Depends(get_db), user=Depends(require_admin)):
    scoped_client(db, user, client_id)
    return Response("\ufeff" + ",".join(COLUMNS) + "\r\n", media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="product-import-template.csv"'})


def uploaded_content(file):
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "File exceeds 2 MB.")
    return content


@router.post("/{client_id}/catalog-import/preview")
def preview(client_id: str, file: Annotated[UploadFile, File()],
            db: Session = Depends(get_db), user=Depends(require_admin)):
    scoped_client(db, user, client_id)
    content = uploaded_content(file)
    products = list(db.scalars(select(Product).where(Product.client_id == client_id)))
    try:
        rows = preview_rows(file.filename or "", content, products)
    except ImportProblem as exc:
        raise HTTPException(422, str(exc)) from exc
    valid = not any(row["errors"] for row in rows)
    return {"rows": rows, "can_import": valid,
            "counts": {action: sum(row["action"] == action and not row["errors"] for row in rows)
                       for action in ["create", "update", "unchanged"]},
            "error_rows": sum(bool(row["errors"]) for row in rows),
            "token": preview_token(client_id, user.id, content, products) if valid else None}


@router.post("/{client_id}/catalog-import/confirm")
def confirm(client_id: str, file: Annotated[UploadFile, File()], token: Annotated[str, Form(max_length=4096)],
            confirmed: Annotated[bool, Form()], db: Session = Depends(get_db), user=Depends(require_admin)):
    scoped_client(db, user, client_id)
    if not confirmed:
        raise HTTPException(400, "Explicit confirmation is required.")
    content = uploaded_content(file)
    # Share the same lock as individual catalog writes; validate again while holding it.
    db.scalar(select(Client).where(Client.id == client_id).with_for_update())
    products = list(db.scalars(select(Product).where(Product.client_id == client_id)))
    try:
        verify_preview(token, client_id, user.id, content, products)
        rows = preview_rows(file.filename or "", content, products)
        if any(row["errors"] for row in rows):
            raise ImportProblem("Validation changed. Preview the file again and resolve all errors.")
    except ImportProblem as exc:
        raise HTTPException(409, str(exc)) from exc
    existing = {p.sku: p for p in products}
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    for row in rows:
        if row["action"] == "unchanged":
            counts["unchanged"] += 1
            continue
        product = existing.get(row["sku"])
        if product is None:
            product = Product(client_id=client_id)
            db.add(product)
            counts["created"] += 1
        else:
            counts["updated"] += 1
        values = ProductInput.model_validate(row["after"]).model_dump()
        if values["stock_updated_at"]:
            values["stock_updated_at"] = values["stock_updated_at"].replace(tzinfo=None)
        for key, value in values.items():
            setattr(product, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Catalog conflict. Nothing was imported; preview again.") from exc
    logger.info("Catalog imported actor=%s client=%s created=%s updated=%s unchanged=%s",
                user.id, client_id, counts["created"], counts["updated"], counts["unchanged"])
    return counts
