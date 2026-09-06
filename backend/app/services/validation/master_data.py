from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.client import Client
from app.models.product import Product
from app.services.validation.service import ValidationResult


def validate_master_data(db, client_id, header, items, order_id=None):
    issues = []

    def flag(field, kind, message):
        issues.append(ValidationResult(field, kind, message))

    client = db.get(Client, client_id) if client_id else None
    if client is None:
        flag("customer_number", "unknown_customer", "No recognized customer is linked to this order.")
        return issues
    if not client.is_active:
        flag("customer_number", "inactive_customer", "Customer account is inactive.")
    if header.get("customer_number") and header["customer_number"] != client.customer_number:
        flag("customer_number", "customer_mismatch", "Customer number does not match the linked account.")
    if not client.master_data_enabled:
        return issues

    def normalize(value):
        return " ".join((value or "").casefold().split())

    if not client.approved_delivery_addresses:
        flag("delivery_address", "address_unverified", "No approved delivery addresses are configured.")
    elif normalize(header.get("delivery_address")) not in {normalize(a) for a in client.approved_delivery_addresses}:
        flag("delivery_address", "address_mismatch", "Delivery address is not an approved customer address.")
    products = list(db.scalars(select(Product).where(Product.client_id == client_id)))
    lookup = {key: product for product in products for key in [product.sku, *product.aliases]}
    quantities = defaultdict(int)
    matched = {}
    matched_lines = defaultdict(list)
    for index, item in enumerate(items, 1):
        prefix = f"items[{index}]"
        product = lookup.get(item.get("article_number"))
        if product is None:
            flag(prefix + ".article_number", "unknown_product", "Article is not in the customer catalog.")
            continue
        matched[product.id] = product
        matched_lines[product.id].append(prefix)
        if not product.is_active:
            flag(prefix + ".article_number", "inactive_product", f"Product {product.sku} is inactive.")
        quantity = item.get("quantity") or 0
        quantities[product.id] += max(quantity, 0)
        if quantity < product.minimum_quantity:
            flag(prefix + ".quantity", "minimum_quantity", f"Minimum quantity is {product.minimum_quantity}.")
        if product.unit_price is not None:
            price = item.get("unit_price")
            if price is None and item.get("total_price") is not None and quantity > 0:
                price = Decimal(str(item["total_price"])) / quantity
            if price is None or Decimal(str(price)) != product.unit_price or item.get("currency") != product.currency:
                flag(prefix + ".unit_price", "price_mismatch", "Price or currency differs from the customer agreement.")
            if item.get("total_price") is not None and quantity > 0:
                if Decimal(str(item["total_price"])) != product.unit_price * quantity:
                    flag(prefix + ".total_price", "price_mismatch", "Line total differs from the customer agreement.")
    from app.models.stock_reservation import StockReservation

    own = {r.product_id: r.quantity for r in db.scalars(
        select(StockReservation).where(StockReservation.order_id == order_id))} if order_id else {}
    now = datetime.now(UTC).replace(tzinfo=None)
    for product_id, product in matched.items():
        available = (product.available or 0) + own.get(product_id, 0)
        stamp = product.stock_updated_at
        if stamp and stamp.tzinfo:
            stamp = stamp.astimezone(UTC).replace(tzinfo=None)
        if product.on_hand is None or stamp is None:
            kind, message = "stock_unknown", f"Stock is unknown for {product.sku}."
        elif now - stamp > timedelta(hours=24) or stamp > now:
            kind, message = "stock_stale", f"Stock for {product.sku} needs a fresh snapshot (maximum age 24 hours)."
        elif quantities[product_id] > available:
            kind = "stock_shortage"
            message = f"{product.sku}: requested {quantities[product_id]}, available {available} at {product.warehouse}."
        else:
            continue
        for prefix in matched_lines[product_id]:
            flag(prefix + ".quantity", kind, message)
    return issues
