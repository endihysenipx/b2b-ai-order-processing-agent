from sqlalchemy import select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.user import User


def _mcp_request(client, auth_headers, method: str, params: dict | None = None, request_id: int = 1):
    return client.post(
        "/mcp",
        headers={
            **auth_headers,
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
        },
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        },
    )


def test_mcp_requires_a_valid_bearer_token(client):
    response = client.post(
        "/mcp",
        headers={"Accept": "application/json, text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        },
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_mcp_rejects_an_untrusted_host(client, auth_headers):
    response = client.post(
        "/mcp",
        headers={
            **auth_headers,
            "Accept": "application/json, text/event-stream",
            "Host": "untrusted.example",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        },
    )

    assert response.status_code == 421


def test_mcp_advertises_only_read_only_order_tools(client, auth_headers):
    response = _mcp_request(client, auth_headers, "tools/list")

    assert response.status_code == 200, response.text
    tools = response.json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {
        "get_attention_queue",
        "get_daily_briefing",
        "search_orders",
        "get_order_details",
        "get_order_evidence",
        "get_operations_report",
        "get_validation_issues",
        "get_processing_summary",
    }
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
    assert all(not tool["annotations"]["destructiveHint"] for tool in tools)


def test_mcp_can_search_and_read_orders_without_exposing_storage_paths(client, auth_headers):
    search_response = _mcp_request(
        client,
        auth_headers,
        "tools/call",
        {"name": "search_orders", "arguments": {"limit": 2}},
    )

    assert search_response.status_code == 200, search_response.text
    search_result = search_response.json()["result"]["structuredContent"]
    assert search_result["returned"] == 2
    assert search_result["total"] >= 5

    order_id = search_result["orders"][0]["id"]
    detail_response = _mcp_request(
        client,
        auth_headers,
        "tools/call",
        {"name": "get_order_details", "arguments": {"order_id": order_id}},
        request_id=2,
    )

    assert detail_response.status_code == 200
    detail_result = detail_response.json()["result"]["structuredContent"]
    assert detail_result["id"] == order_id
    assert "file_path" not in detail_response.text
    assert "s3_object_key" not in detail_response.text

    evidence_response = _mcp_request(
        client,
        auth_headers,
        "tools/call",
        {
            "name": "get_order_evidence",
            "arguments": {"order_id": order_id, "max_chars_per_source": 500},
        },
        request_id=3,
    )
    assert evidence_response.status_code == 200, evidence_response.text
    assert evidence_response.json()["result"]["structuredContent"]["order_id"] == order_id
    assert "file_path" not in evidence_response.text

    validation_response = _mcp_request(
        client,
        auth_headers,
        "tools/call",
        {"name": "get_validation_issues", "arguments": {"order_id": order_id}},
        request_id=4,
    )
    assert validation_response.status_code == 200, validation_response.text
    assert validation_response.json()["result"]["structuredContent"]["order_id"] == order_id

    summary_response = _mcp_request(
        client,
        auth_headers,
        "tools/call",
        {"name": "get_processing_summary", "arguments": {}},
        request_id=5,
    )
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["result"]["structuredContent"]["total_orders"] >= 5


def test_mcp_provides_role_aware_briefings_attention_queue_and_management_report(client, auth_headers):
    briefing = _mcp_request(client, auth_headers, "tools/call", {"name": "get_daily_briefing", "arguments": {}})
    attention = _mcp_request(client, auth_headers, "tools/call", {"name": "get_attention_queue", "arguments": {}})
    report = _mcp_request(client, auth_headers, "tools/call", {"name": "get_operations_report", "arguments": {}})

    assert briefing.status_code == 200, briefing.text
    briefing_result = briefing.json()["result"]["structuredContent"]
    assert briefing_result["viewer_role"] == "admin"
    assert briefing_result["access_scope"] == "all organization clients"
    assert briefing_result["timezone"] == "Europe/Warsaw"

    assert attention.status_code == 200, attention.text
    attention_result = attention.json()["result"]["structuredContent"]
    assert attention_result["total_needing_attention"] >= 3
    assert attention_result["orders"][0]["priority"] in {"critical", "high"}
    assert attention_result["orders"][0]["reasons"]

    assert report.status_code == 200, report.text
    report_result = report.json()["result"]["structuredContent"]
    assert report_result["total_orders"] >= 5
    assert set(report_result["orders_by_client"]) == {"Contoso Interior Supply", "Northwind Retail Group"}
    assert report_result["orders_needing_attention"] >= 3
    assert 0 <= report_result["ready_or_completed_rate_percent"] <= 100


def test_mcp_reports_enforce_operator_client_scope(client):
    with SessionLocal() as db:
        northwind = db.scalar(select(Client).where(Client.client_name == "Northwind Retail Group"))
        operator = User(
            full_name="MCP Scoped Operator",
            email="mcp-operator@example.com",
            password_hash="not-used-by-this-token-test",
            role="operator",
        )
        operator.clients = [northwind]
        db.add(operator)
        db.commit()
        db.refresh(operator)
        token = create_access_token(operator.id, operator.role, operator.auth_version)

    headers = {"Authorization": f"Bearer {token}"}
    report = _mcp_request(client, headers, "tools/call", {"name": "get_operations_report", "arguments": {}})
    attention = _mcp_request(client, headers, "tools/call", {"name": "get_attention_queue", "arguments": {}})

    assert report.status_code == 200, report.text
    report_result = report.json()["result"]["structuredContent"]
    assert report_result["viewer_role"] == "operator"
    assert report_result["access_scope"] == "1 assigned client"
    assert set(report_result["orders_by_client"]) == {"Northwind Retail Group"}

    assert attention.status_code == 200, attention.text
    attention_orders = attention.json()["result"]["structuredContent"]["orders"]
    assert attention_orders
    assert all(item["order"]["client_name"] == "Northwind Retail Group" for item in attention_orders)


def test_mcp_returns_a_tool_error_for_an_unknown_order(client, auth_headers):
    response = _mcp_request(
        client,
        auth_headers,
        "tools/call",
        {"name": "get_order_details", "arguments": {"order_id": "missing-order"}},
    )

    assert response.status_code == 200
    assert response.json()["result"]["isError"] is True
    assert "Order not found" in response.text
