import base64
import hashlib
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from mcp.shared.auth import OAuthClientInformationFull

from app.core.config import settings
from app.oauth.provider import READ_SCOPE, oauth_provider


def _client() -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id="https://chatgpt.com/oauth/test/client.json",
        client_name="ChatGPT Test",
        redirect_uris=["https://chatgpt.com/connector_platform_oauth_redirect"],
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope=READ_SCOPE,
    )


def _pkce(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


def _unsigned_int(value: int) -> str:
    width = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(width, "big")).decode().rstrip("=")


def test_oauth_discovery_and_mcp_challenge(client):
    authorization = client.get("/.well-known/oauth-authorization-server")
    assert authorization.status_code == 200
    assert authorization.json()["client_id_metadata_document_supported"] is True
    assert authorization.json()["authorization_response_iss_parameter_supported"] is True
    assert authorization.json()["code_challenge_methods_supported"] == ["S256"]

    resource = client.get("/.well-known/oauth-protected-resource/mcp")
    assert resource.status_code == 200
    assert resource.json() == {
        "resource": settings.mcp_resource_url,
        "authorization_servers": [settings.oauth_issuer_url],
        "scopes_supported": [READ_SCOPE],
        "bearer_methods_supported": ["header"],
    }

    challenged = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"},
    )
    assert challenged.status_code == 401
    assert f'resource_metadata="{settings.oauth_issuer_url}/.well-known/oauth-protected-resource/mcp"' in challenged.headers[
        "www-authenticate"
    ]


def test_chatgpt_authorization_code_and_refresh_flow(client, auth_headers, monkeypatch):
    oauth_client = _client()

    async def get_test_client(client_id: str):
        return oauth_client if client_id == oauth_client.client_id else None

    monkeypatch.setattr(oauth_provider, "get_client", get_test_client)
    verifier = "test-verifier-with-at-least-forty-three-characters-123456789"
    authorize = client.get(
        "/authorize",
        params={
            "client_id": oauth_client.client_id,
            "redirect_uri": str(oauth_client.redirect_uris[0]),
            "response_type": "code",
            "code_challenge": _pkce(verifier),
            "code_challenge_method": "S256",
            "state": "test-state",
            "scope": READ_SCOPE,
            "resource": settings.mcp_resource_url,
        },
        follow_redirects=False,
    )
    assert authorize.status_code == 302
    request_token = parse_qs(urlsplit(authorize.headers["location"]).query)["request"][0]

    consent = client.post(
        "/api/v1/oauth/authorize/complete",
        json={"request_token": request_token, "approved": True},
        headers=auth_headers,
    )
    assert consent.status_code == 200, consent.text
    callback = urlsplit(consent.json()["redirect_url"])
    callback_params = parse_qs(callback.query)
    assert callback_params["state"] == ["test-state"]
    assert callback_params["iss"] == [settings.oauth_issuer_url]

    token = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": oauth_client.client_id,
            "code": callback_params["code"][0],
            "redirect_uri": str(oauth_client.redirect_uris[0]),
            "code_verifier": verifier,
            "resource": settings.mcp_resource_url,
        },
    )
    assert token.status_code == 200, token.text
    issued = token.json()
    assert issued["scope"] == READ_SCOPE
    assert issued["refresh_token"]

    mcp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={
            "Authorization": f"Bearer {issued['access_token']}",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
        },
    )
    assert mcp.status_code == 200, mcp.text
    assert len(mcp.json()["result"]["tools"]) == 8

    rest = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {issued['access_token']}"})
    assert rest.status_code == 401

    refreshed = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": oauth_client.client_id,
            "refresh_token": issued["refresh_token"],
            "scope": READ_SCOPE,
            "resource": settings.mcp_resource_url,
        },
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["refresh_token"] != issued["refresh_token"]

    replay = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": oauth_client.client_id,
            "refresh_token": issued["refresh_token"],
            "scope": READ_SCOPE,
            "resource": settings.mcp_resource_url,
        },
    )
    assert replay.status_code == 400
    assert replay.json()["error"] == "invalid_grant"

    family_revoked = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": oauth_client.client_id,
            "refresh_token": refreshed.json()["refresh_token"],
            "scope": READ_SCOPE,
            "resource": settings.mcp_resource_url,
        },
    )
    assert family_revoked.status_code == 400
    assert family_revoked.json()["error"] == "invalid_grant"


def test_chatgpt_private_key_client_assertions_are_verified_and_one_use(client, monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    oauth_client = OAuthClientInformationFull(
        client_id="https://chatgpt.com/oauth/signed/client.json",
        client_name="ChatGPT Signed Test",
        redirect_uris=["https://chatgpt.com/connector_platform_oauth_redirect"],
        token_endpoint_auth_method="private_key_jwt",
        grant_types=["authorization_code", "refresh_token"],
        scope=READ_SCOPE,
        jwks={
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "test-signing-key",
                    "use": "sig",
                    "alg": "RS256",
                    "n": _unsigned_int(numbers.n),
                    "e": _unsigned_int(numbers.e),
                }
            ]
        },
    )

    async def get_signed_client(client_id: str):
        return oauth_client if client_id == oauth_client.client_id else None

    monkeypatch.setattr(oauth_provider, "get_client", get_signed_client)
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": oauth_client.client_id,
            "sub": oauth_client.client_id,
            "aud": f"{settings.oauth_issuer_url}/token",
            "iat": now,
            "exp": now + 120,
            "jti": "one-use-client-assertion",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-signing-key"},
    )
    form = {
        "grant_type": "authorization_code",
        "client_id": oauth_client.client_id,
        "code": "not-an-authorization-code",
        "redirect_uri": str(oauth_client.redirect_uris[0]),
        "code_verifier": "not-used-because-the-code-does-not-exist",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": assertion,
        "resource": settings.mcp_resource_url,
    }

    authenticated = client.post("/token", data=form)
    assert authenticated.status_code == 400
    assert authenticated.json()["error"] == "invalid_grant"

    replay = client.post("/token", data=form)
    assert replay.status_code == 401
    assert replay.json()["error"] == "invalid_client"
