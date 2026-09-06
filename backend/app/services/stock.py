from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select

from app.models.product import Product
from app.models.stock_reservation import StockReservation
from app.services.audit import record_change


def release_stock(db, order, actor):
    for row in db.scalars(select(StockReservation).where(StockReservation.order_id == order.id)):
        product = db.get(Product, row.product_id)
        record_change(db, actor, order.client, "product", product,
                      {"order_reserved": product.order_reserved},
                      {"order_reserved": product.order_reserved - row.quantity},
                      "stock_released", order_id=order.id)
        db.delete(row)
        db.flush()
        db.expire(product, ["stock_reservations"])
    db.expire(order, ["stock_reservations"])


def reserve_stock(db, order, actor):
    # Caller holds the client lock through validation, reservation and commit.
    if order.is_demo or not order.client.master_data_enabled:
        return
    products = list(db.scalars(select(Product).where(Product.client_id == order.client_id)))
    lookup = {key: p for p in products for key in [p.sku, *p.aliases]}
    required = defaultdict(int)
    for item in order.items:
        product = lookup.get(item.article_number)
        if product is None or not item.quantity or item.quantity < 0:
            raise HTTPException(409, "Correct order items before reserving stock.")
        required[product.id] += item.quantity
    existing = {r.product_id: r for r in db.scalars(
        select(StockReservation).where(StockReservation.order_id == order.id))}
    for product in products:
        quantity = required.get(product.id, 0)
        row = existing.get(product.id)
        previous = row.quantity if row else 0
        if quantity == previous:
            continue
        if product.available is None or quantity > product.available + previous:
            raise HTTPException(409, "Available stock changed. Validate the order again.")
        before = product.order_reserved
        if row and not quantity:
            db.delete(row)
        elif row:
            row.quantity = quantity
        elif quantity:
            db.add(StockReservation(order_id=order.id, product_id=product.id, quantity=quantity))
        record_change(db, actor, order.client, "product", product,
                      {"order_reserved": before}, {"order_reserved": before + quantity - previous},
                      "stock_reserved", order_id=order.id)
        db.flush()
        db.expire(product, ["stock_reservations"])
    db.expire(order, ["stock_reservations"])
