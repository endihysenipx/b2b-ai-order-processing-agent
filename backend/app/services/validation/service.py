from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ValidationResult:
    field_name: str
    issue_type: str
    message: str
    severity: str = "error"


def validate_order_data(order_data: dict, items: list[dict], is_scanned_source: bool = False) -> list[ValidationResult]:
    issues: list[ValidationResult] = []
    required_fields = [
        ("ticket_number", "missing ticket number"),
        ("customer_number", "missing customer number"),
        ("commission_number", "missing commission number"),
        ("delivery_address", "missing delivery address"),
    ]
    for field_name, message in required_fields:
        if not order_data.get(field_name):
            issues.append(ValidationResult(field_name, "missing_required_field", message))

    for index, item in enumerate(items, start=1):
        prefix = f"items[{index}]"
        if not item.get("article_number"):
            issues.append(
                ValidationResult(f"{prefix}.article_number", "missing_required_field", "missing article number")
            )
        quantity = item.get("quantity")
        if quantity is None:
            issues.append(ValidationResult(f"{prefix}.quantity", "missing_required_field", "missing quantity"))
        elif quantity <= 0:
            issues.append(
                ValidationResult(f"{prefix}.quantity", "invalid_quantity", "invalid or non-positive quantity")
            )
        price_present = item.get("unit_price") is not None or item.get("total_price") is not None
        if price_present and not item.get("currency"):
            issues.append(
                ValidationResult(
                    f"{prefix}.currency", "missing_required_field", "missing currency when price is present"
                )
            )

    if order_data.get("total_price") not in (None, Decimal("0")) and not order_data.get("currency"):
        issues.append(ValidationResult("currency", "missing_required_field", "missing currency when price is present"))

    if is_scanned_source:
        issues.append(
            ValidationResult(
                "attachments",
                "manual_review_required",
                "scanned or image document requires Human in the Loop review",
                "warning",
            )
        )
    return issues
