from app.services.validation.service import ValidationResult


def decide_order_status(
    issues: list[ValidationResult],
    *,
    is_scanned_source: bool = False,
    low_confidence: bool = False,
    conflict: bool = False,
    technical_exception: bool = False,
) -> str:
    if technical_exception:
        return "Failed"
    if any(issue.issue_type == "missing_required_field" for issue in issues):
        return "Waiting for Reply"
    if is_scanned_source or low_confidence or conflict:
        return "Human in the Loop"
    return "OK"
