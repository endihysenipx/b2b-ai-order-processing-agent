from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import accessible_client_ids, get_current_user, require_admin
from app.api.routes.orders import refresh_validation
from app.db.session import get_db
from app.models.client import Client
from app.models.email import Email
from app.models.order import Order
from app.schemas.business_rules import BusinessRules, ClientCaseCreate, RulePreview
from app.services.audit import ORDER_FIELDS, order_change, record_change, snapshot
from app.services.business_rules import client_rules, evaluate
from app.services.client_cases import convert_case
from app.services.stock import release_stock

router = APIRouter(prefix="/business-rules", tags=["business rules"])


@router.get("")
def list_rules(db: Session = Depends(get_db), user=Depends(get_current_user)):
    allowed = accessible_client_ids(user)
    query = select(Client).order_by(Client.client_name)
    if allowed is not None:
        query = query.where(Client.id.in_(allowed))
    return [{"client_id": client.id, "client_name": client.client_name, "is_active": client.is_active,
             "rules": client_rules(client).model_dump(mode="json")} for client in db.scalars(query)]


@router.post("/preview")
def preview_rules(payload: RulePreview, user=Depends(get_current_user)):
    return evaluate(payload.rules, payload.subtotal, payload.rules.currency)


@router.put("/clients/{client_id}")
def save_rules(client_id: str, payload: BusinessRules, db: Session = Depends(get_db), user=Depends(require_admin)):
    client = db.scalar(select(Client).where(Client.id == client_id).with_for_update())
    if client is None:
        raise HTTPException(404, "Client not found")
    before = {"business_rules": client_rules(client).model_dump(mode="json")}
    after = {"business_rules": payload.model_dump(mode="json")}
    if before == after:
        return {"updated_orders": 0, "rules": after["business_rules"]}
    orders = list(db.scalars(select(Order).where(Order.client_id == client.id).with_for_update()))
    for order in orders:
        if any(xml.sent_at is not None for xml in order.generated_xmls) and order.business_rules_snapshot is None:
            order.business_rules_snapshot = before["business_rules"]
    # Preserve non-commercial validation settings and all sent-order snapshots.
    client.validation_rules = {**(client.validation_rules or {}), **after}
    record_change(db, user, client, "customer", client, before, after, "business_rules_updated")
    count = 0
    for order in orders:
        if any(xml.sent_at is not None for xml in order.generated_xmls) or order.status == "Rejected":
            continue
        previous = snapshot(order, ORDER_FIELDS)
        release_stock(db, order, user)
        refresh_validation(db, order)
        order.generated_xmls.clear()
        order_change(db, user, order, previous, "business_rules_recalculated")
        count += 1
    db.commit()
    return {"updated_orders": count, "rules": after["business_rules"]}


@router.get("/sources")
def case_sources(db: Session = Depends(get_db), user=Depends(require_admin)):
    query = (select(Email).where(Email.subject.ilike("%Bestellung%"))
             .order_by(Email.received_at.desc()).limit(30))
    return [{"id": email.id, "subject": email.subject, "received_at": email.received_at,
             "order_count": len(email.orders), "converted": any(o.case_source for o in email.orders)}
            for email in db.scalars(query)]


@router.get("/cases")
def list_cases(db: Session = Depends(get_db), user=Depends(get_current_user)):
    allowed = accessible_client_ids(user)
    query = select(Order).where(Order.case_source["label"].as_string().is_not(None)).order_by(Order.updated_at.desc())
    if allowed is not None:
        query = query.where(Order.client_id.in_(allowed))
    return [{"id": order.id, "client_id": order.client_id, "client_name": order.client.client_name,
             "label": order.case_source["label"], "status": order.status,
             "commercial_terms": order.commercial_terms}
            for order in db.scalars(query) if order.case_source]


@router.post("/cases")
def create_case(payload: ClientCaseCreate, db: Session = Depends(get_db), user=Depends(require_admin)):
    order = convert_case(db, user, payload)
    db.commit()
    return {"id": order.id, "commercial_terms": order.commercial_terms}
