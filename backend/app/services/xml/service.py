from datetime import UTC, datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from app.core.config import settings
from app.models.order import Order


def _write_xml(path: Path, root: Element) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tostring(root, encoding="utf-8", xml_declaration=True))
    return str(path)


def generate_header_xml(order: Order) -> str:
    root = Element("OrderHeader")
    fields = {
        "OrderId": order.id,
        "TicketNumber": order.ticket_number or "",
        "CustomerNumber": order.customer_number or "",
        "CustomerName": order.customer_name or "",
        "CommissionNumber": order.commission_number or "",
        "DeliveryAddress": order.delivery_address or "",
        "Status": order.status,
    }
    for key, value in fields.items():
        SubElement(root, key).text = value
    path = Path(settings.storage_root) / "xml" / order.id / "header.xml"
    return _write_xml(path, root)


def generate_items_xml(order: Order) -> str:
    root = Element("OrderItems")
    for item in order.items:
        item_node = SubElement(root, "Item")
        SubElement(item_node, "ArticleNumber").text = item.article_number or ""
        SubElement(item_node, "ModelNumber").text = item.model_number or ""
        SubElement(item_node, "Quantity").text = str(item.quantity or "")
        SubElement(item_node, "UnitPrice").text = str(item.unit_price or "")
        SubElement(item_node, "Currency").text = item.currency or ""
    path = Path(settings.storage_root) / "xml" / order.id / "items.xml"
    return _write_xml(path, root)


def simulate_send_xml(order: Order) -> dict:
    return {
        "order_id": order.id,
        "status": "simulated_success",
        "sent_at": datetime.now(UTC).isoformat(),
        "message": "ERP XML transmission simulated; no real ERP connection was used.",
    }
