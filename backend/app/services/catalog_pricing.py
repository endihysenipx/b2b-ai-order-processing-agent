"""Fill missing intake prices from the assigned client's active catalog."""

from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from app.models.client import Client
from app.models.product import Product
from app.services.audit import ITEM_FIELDS, ORDER_FIELDS, order_change, record_change, snapshot


def apply_catalog_prices(db, order, items=None):
    if order.approved_at or order.status in {"Approved", "ERP Ready", "XMLs Sent", "Rejected"}:
        return 0
    client = db.get(Client, order.client_id)
    if client is None or not client.master_data_enabled:
        return 0
    products = list(db.scalars(select(Product).where(Product.client_id == client.id, Product.is_active.is_(True))))
    lookup = {identifier: product for product in products for identifier in [product.sku, *product.aliases]}
    actor = SimpleNamespace(id="system:catalog-pricing", full_name="Automatic catalog pricing")
    changed = 0
    rows = order.items if items is None else items
    for item in rows:
        product = lookup.get(item.article_number)
        if product is None or product.unit_price is None or not product.currency:
            continue
        if item.unit_price is not None or not item.quantity or item.quantity <= 0:
            continue
        if (item.currency and item.currency != product.currency) or (order.currency and order.currency != product.currency):
            continue
        total = (product.unit_price * item.quantity).quantize(Decimal("0.01"))
        if total >= Decimal("10000000000") or (item.total_price is not None and item.total_price != total):
            continue
        before = snapshot(item, ITEM_FIELDS)
        item.unit_price = product.unit_price
        item.currency = product.currency
        item.total_price = total
        record_change(db, actor, client, "order_item", item, before, snapshot(item, ITEM_FIELDS),
                      "catalog_price_applied", order_id=order.id)
        changed += 1
    currencies = {item.currency for item in rows}
    if changed and rows and len(currencies) == 1 and None not in currencies and all(item.total_price is not None for item in rows):
        before = snapshot(order, ORDER_FIELDS)
        subtotal = sum(item.total_price for item in rows)
        if order.currency is None:
            order.currency = next(iter(currencies))
        if order.total_price is None and subtotal < Decimal("10000000000"):
            order.total_price = subtotal
        order_change(db, actor, order, before, "catalog_order_totals_applied")
    return changed
