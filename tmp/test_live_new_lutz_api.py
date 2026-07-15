from collections import Counter
from pathlib import Path

import httpx


BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "Email Samples" / "NEW LUTZ SAMPLES"


login = httpx.post(
    f"{BASE_URL}/api/v1/auth/login",
    json={"email": "admin@example.com", "password": "Admin123!"},
    timeout=10,
)
login.raise_for_status()
headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

results = []
for path in sorted(SAMPLES.glob("*.eml")):
    with path.open("rb") as source:
        response = httpx.post(
            f"{BASE_URL}/api/v1/emails/preview",
            headers=headers,
            files={"file": (path.name, source, "message/rfc822")},
            timeout=30,
        )
    response.raise_for_status()
    payload = response.json()
    results.append(
        {
            "file": path.name,
            "message_type": payload["message_type"],
            "client": payload.get("client_profile"),
            "action": payload["next_action"],
            "orders": len(payload["orders"]),
            "items": sum(len(order["items"]) for order in payload["orders"]),
        }
    )

print(f"HTTP_OK={len(results)}")
print(f"MESSAGE_TYPES={dict(Counter(row['message_type'] for row in results))}")
print(f"NEXT_ACTIONS={dict(Counter(row['action'] for row in results))}")
print(f"ORDER_BLOCKS={sum(row['orders'] for row in results)}")
print(f"ITEMS={sum(row['items'] for row in results)}")
print("WAITING_FOR_REPLY:")
for row in results:
    if row["action"] == "waiting_for_reply":
        print(f"  {row['file']} | orders={row['orders']} items={row['items']}")
