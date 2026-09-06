"""Deterministic commercial calculations; no external calls or writes during evaluation."""

from decimal import ROUND_HALF_UP, Decimal

from app.schemas.business_rules import BusinessRules


def money(value):
    return format(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def client_rules(client):
    return BusinessRules.model_validate((getattr(client, "validation_rules", None) or {}).get("business_rules", {}))


def evaluate(rules, subtotal, currency):
    enabled = any((rules.freight_enabled, rules.discount_enabled, rules.minimum_enabled, rules.review_enabled))
    result = {"currency": currency or rules.currency, "subtotal": None, "discount": "0.00", "freight": "0.00",
              "total": None, "applied": [], "blockers": [], "review_required": False, "enabled": enabled}
    if subtotal is None or not Decimal(subtotal).is_finite() or Decimal(subtotal) < 0:
        if enabled:
            result["blockers"].append("Enter non-negative prices for every line before applying business rules.")
        return result
    subtotal = Decimal(money(subtotal))
    result.update(subtotal=money(subtotal), total=money(subtotal))
    if enabled and currency != rules.currency:
        result["blockers"].append(f"These rules require {rules.currency}; correct the order currency. No conversion is applied.")
        return result
    discount = Decimal("0")
    freight = Decimal("0")
    if rules.discount_enabled and subtotal >= rules.discount_from:
        discount = Decimal(money(subtotal * rules.discount_percent / 100))
        result["applied"].append(f"{rules.discount_percent}% discount: merchandise subtotal is at least {money(rules.discount_from)}.")
    if rules.freight_enabled and subtotal < rules.freight_below:
        freight = rules.freight_charge
        result["applied"].append(f"{money(freight)} freight: merchandise subtotal is below {money(rules.freight_below)}.")
    elif rules.freight_enabled:
        result["applied"].append(f"Free freight: merchandise subtotal reached {money(rules.freight_below)}.")
    if rules.minimum_enabled and subtotal < rules.minimum_order:
        result["blockers"].append(f"Minimum merchandise order is {money(rules.minimum_order)} {rules.currency}; add {money(rules.minimum_order - subtotal)}.")
    total = subtotal - discount + freight
    if rules.review_enabled and total >= rules.review_from:
        result["review_required"] = True
        result["applied"].append(f"Human review required: final total is at least {money(rules.review_from)}.")
    result.update(discount=money(discount), freight=money(freight), total=money(total))
    return result


def order_terms(order):
    rules = BusinessRules.model_validate(order.business_rules_snapshot) if order.business_rules_snapshot is not None else client_rules(order.client)
    rows = order.items
    currencies = {item.currency for item in rows if item.currency}
    currency = order.currency or (next(iter(currencies)) if len(currencies) == 1 else None)
    subtotal = order.total_price if not rows else Decimal("0")
    for item in rows:
        if item.quantity is not None and item.unit_price is not None:
            if item.quantity <= 0 or item.unit_price < 0:
                subtotal = None
                break
            subtotal += Decimal(money(item.quantity * item.unit_price))
        elif item.total_price is not None and item.total_price >= 0:
            subtotal += item.total_price
        else:
            subtotal = None
            break
    result = evaluate(rules, subtotal, currency)
    if result["enabled"] and any(item.currency != currency for item in rows):
        result["blockers"].append("All lines must have the same currency as the order.")
        result.update(total=None, discount="0.00", freight="0.00", applied=[])
    return result


def freeze_rules(order):
    order.business_rules_snapshot = client_rules(order.client).model_dump(mode="json")
