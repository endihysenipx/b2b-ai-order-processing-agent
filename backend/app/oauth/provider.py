import hashlib
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
from jose import JWTError, jwt
from mcp.server.auth.middleware.client_auth import AuthenticationError
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, decode_token
from app.db.session import SessionLocal
from app.models.oauth import OAuthAuthorizationCode, OAuthClientAssertion, OAuthRefreshToken
from app.models.user import User

logger = logging.getLogger(__name__)

READ_SCOPE = "orders:read"
CONSENT_AUDIENCE = "b2b-order-processing-oauth-consent"
CHATGPT_CLIENT_HOST = "chatgpt.com"
CHATGPT_STABLE_CLIENT_ID = "https://chatgpt.com/oauth/client.json"
CHATGPT_STABLE_REDIRECT_URI = "https://chatgpt.com/connector_platform_oauth_redirect"
CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _now() -> int:
    return int(time.time())


def _is_chatgpt_client_id(client_id: str) -> bool:
    parsed = urlsplit(client_id)
    return (
        parsed.scheme == "https"
        and parsed.hostname == CHATGPT_CLIENT_HOST
        and parsed.query == ""
        and parsed.fragment == ""
        and parsed.path.startswith("/oauth/")
        and parsed.path.endswith("/client.json")
    )


def _is_chatgpt_redirect(uri: str) -> bool:
    parsed = urlsplit(uri)
    if parsed.scheme != "https" or parsed.hostname != CHATGPT_CLIENT_HOST or parsed.query or parsed.fragment:
        return False
    return parsed.path == "/connector_platform_oauth_redirect" or parsed.path.startswith("/connector/oauth/")


class StoredAuthorizationCode(AuthorizationCode):
    record_id: str
    auth_version: int


class StoredRefreshToken(RefreshToken):
    record_id: str
    family_id: str
    auth_version: int
    resource: str
    revoked: bool


class ChatGptClientAuthenticator:
    """Authenticate ChatGPT's CIMD client with private_key_jwt or a public test client."""

    def __init__(self, provider: "ChatGptOAuthProvider"):
        self.provider = provider

    async def authenticate_request(self, request) -> OAuthClientInformationFull:
        form = await request.form()
        client_id = form.get("client_id")
        if not isinstance(client_id, str) or not client_id:
            raise AuthenticationError("Missing client_id")
        client = await self.provider.get_client(client_id)
        if client is None:
            raise AuthenticationError("Invalid client_id")
        if form.get("resource") != settings.mcp_resource_url:
            raise AuthenticationError("The token request resource is invalid")

        method = client.token_endpoint_auth_method or "none"
        if method == "none":
            return client
        if method != "private_key_jwt":
            raise AuthenticationError("Unsupported client authentication method")

        assertion_type = form.get("client_assertion_type")
        assertion = form.get("client_assertion")
        if assertion_type != CLIENT_ASSERTION_TYPE or not isinstance(assertion, str):
            raise AuthenticationError("A signed client assertion is required")
        await self.provider.verify_client_assertion(client, assertion)
        return client


class ChatGptOAuthProvider:
    def __init__(self) -> None:
        self._client_cache: dict[str, tuple[float, OAuthClientInformationFull]] = {}
        self._jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def _get_json(self, url: str, *, max_bytes: int = 131_072) -> dict[str, Any]:
        async with httpx.AsyncClient(follow_redirects=False, timeout=10, trust_env=False) as client:
            response = await client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        if len(response.content) > max_bytes:
            raise ValueError("Remote OAuth metadata is too large")
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("Remote OAuth metadata must be a JSON object")
        return value

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        if not _is_chatgpt_client_id(client_id):
            return None
        cached = self._client_cache.get(client_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            metadata = await self._get_json(client_id)
            client = OAuthClientInformationFull.model_validate(metadata)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Unable to validate ChatGPT OAuth client metadata: %s", exc)
            return None
        if client.client_id != client_id:
            return None
        if client.token_endpoint_auth_method not in {"none", "private_key_jwt"}:
            return None
        if not {"authorization_code", "refresh_token"}.issubset(set(client.grant_types)):
            return None
        if not client.redirect_uris or any(not _is_chatgpt_redirect(str(uri)) for uri in client.redirect_uris):
            return None
        if client.token_endpoint_auth_method == "private_key_jwt":
            if not client.jwks_uri or urlsplit(str(client.jwks_uri)).hostname != CHATGPT_CLIENT_HOST:
                return None
        client = client.model_copy(update={"scope": READ_SCOPE})
        self._client_cache[client_id] = (time.monotonic() + 300, client)
        return client

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        raise NotImplementedError("Dynamic client registration is disabled; ChatGPT CIMD is required")

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        scopes = params.scopes or [READ_SCOPE]
        if scopes != [READ_SCOPE] and set(scopes) != {READ_SCOPE}:
            raise AuthorizeError("invalid_scope", "Only read-only order access is available")
        resource = params.resource or settings.mcp_resource_url
        if resource != settings.mcp_resource_url:
            raise AuthorizeError("invalid_target", "The requested resource is not this MCP server")
        now = _now()
        request_token = jwt.encode(
            {
                "iss": settings.token_issuer,
                "aud": CONSENT_AUDIENCE,
                "iat": now,
                "nbf": now,
                "exp": now + 600,
                "jti": secrets.token_urlsafe(16),
                "token_type": "oauth_consent",
                "client_id": client.client_id,
                "client_name": client.client_name or "ChatGPT",
                "redirect_uri": str(params.redirect_uri),
                "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
                "code_challenge": params.code_challenge,
                "scopes": scopes,
                "resource": resource,
                "state": params.state,
            },
            settings.secret_key,
            algorithm=ALGORITHM,
        )
        return f"{settings.frontend_url.rstrip('/')}/oauth/authorize?request={request_token}"

    def _decode_consent(self, request_token: str) -> dict[str, Any]:
        payload = jwt.decode(
            request_token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            issuer=settings.token_issuer,
            audience=CONSENT_AUDIENCE,
            options={"require_exp": True, "require_iat": True},
        )
        if payload.get("token_type") != "oauth_consent":
            raise JWTError("Invalid OAuth consent request")
        return payload

    async def complete_authorization(self, request_token: str, user: User, approved: bool) -> str:
        try:
            payload = self._decode_consent(request_token)
        except JWTError as exc:
            raise ValueError("This authorization request is invalid or expired") from exc
        client = await self.get_client(payload.get("client_id", ""))
        if client is None:
            raise ValueError("The ChatGPT client could not be verified")
        redirect_uri = payload.get("redirect_uri")
        if not isinstance(redirect_uri, str) or not client.redirect_uris:
            raise ValueError("The authorization request has an invalid redirect URI")
        if redirect_uri not in {str(uri) for uri in client.redirect_uris}:
            raise ValueError("The authorization request has an unregistered redirect URI")
        state = payload.get("state")
        if not approved:
            return construct_redirect_uri(
                redirect_uri,
                error="access_denied",
                error_description="The user declined read-only order access",
                state=state,
                iss=settings.oauth_issuer_url,
            )
        if payload.get("resource") != settings.mcp_resource_url or payload.get("scopes") != [READ_SCOPE]:
            raise ValueError("The authorization request has an invalid resource or scope")

        raw_code = secrets.token_urlsafe(48)
        with SessionLocal() as db:
            db.add(
                OAuthAuthorizationCode(
                    code_hash=_digest(raw_code),
                    client_id=client.client_id,
                    user_id=user.id,
                    auth_version=user.auth_version,
                    redirect_uri=redirect_uri,
                    code_challenge=payload["code_challenge"],
                    scopes=[READ_SCOPE],
                    resource=settings.mcp_resource_url,
                    expires_at=_now() + 300,
                    used=False,
                )
            )
            db.commit()
        logger.info("OAuth read-only MCP access approved: user_id=%s client_id=%s", user.id, client.client_id)
        return construct_redirect_uri(
            redirect_uri,
            code=raw_code,
            state=state,
            iss=settings.oauth_issuer_url,
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> StoredAuthorizationCode | None:
        with SessionLocal() as db:
            record = db.scalar(
                select(OAuthAuthorizationCode).where(
                    OAuthAuthorizationCode.code_hash == _digest(authorization_code),
                    OAuthAuthorizationCode.client_id == client.client_id,
                    OAuthAuthorizationCode.used.is_(False),
                )
            )
            if record is None:
                return None
            return StoredAuthorizationCode(
                code=authorization_code,
                scopes=list(record.scopes),
                expires_at=record.expires_at,
                client_id=record.client_id,
                code_challenge=record.code_challenge,
                redirect_uri=record.redirect_uri,
                redirect_uri_provided_explicitly=True,
                resource=record.resource,
                subject=record.user_id,
                record_id=record.id,
                auth_version=record.auth_version,
            )

    def _new_refresh_record(
        self,
        *,
        raw_token: str,
        family_id: str,
        client_id: str,
        user: User,
        scopes: list[str],
        resource: str,
    ) -> OAuthRefreshToken:
        return OAuthRefreshToken(
            token_hash=_digest(raw_token),
            family_id=family_id,
            client_id=client_id,
            user_id=user.id,
            auth_version=user.auth_version,
            scopes=scopes,
            resource=resource,
            expires_at=_now() + 30 * 24 * 60 * 60,
            revoked=False,
        )

    def _oauth_tokens(
        self,
        *,
        client_id: str,
        user: User,
        scopes: list[str],
        resource: str,
        refresh_token: str,
    ) -> OAuthToken:
        access_token = create_access_token(
            user.id,
            user.role,
            user.auth_version,
            client_id=client_id,
            scopes=scopes,
            resource=resource,
        )
        return OAuthToken(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
            scope=" ".join(scopes),
            refresh_token=refresh_token,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: StoredAuthorizationCode
    ) -> OAuthToken:
        raw_refresh = secrets.token_urlsafe(64)
        with SessionLocal() as db:
            record = db.scalar(
                select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.id == authorization_code.record_id).with_for_update()
            )
            user = db.get(User, authorization_code.subject)
            if (
                record is None
                or record.used
                or record.expires_at < _now()
                or user is None
                or not user.is_active
                or user.must_change_password
                or record.auth_version != user.auth_version
            ):
                raise TokenError("invalid_grant", "The authorization code is invalid, expired, or revoked")
            record.used = True
            family_id = secrets.token_urlsafe(24)
            db.add(
                self._new_refresh_record(
                    raw_token=raw_refresh,
                    family_id=family_id,
                    client_id=client.client_id,
                    user=user,
                    scopes=list(record.scopes),
                    resource=record.resource,
                )
            )
            db.commit()
            tokens = self._oauth_tokens(
                client_id=client.client_id,
                user=user,
                scopes=list(record.scopes),
                resource=record.resource,
                refresh_token=raw_refresh,
            )
        logger.info("OAuth authorization code exchanged: user_id=%s client_id=%s", user.id, client.client_id)
        return tokens

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> StoredRefreshToken | None:
        with SessionLocal() as db:
            record = db.scalar(
                select(OAuthRefreshToken).where(
                    OAuthRefreshToken.token_hash == _digest(refresh_token),
                    OAuthRefreshToken.client_id == client.client_id,
                )
            )
            if record is None:
                return None
            return StoredRefreshToken(
                token=refresh_token,
                client_id=record.client_id,
                scopes=list(record.scopes),
                expires_at=record.expires_at,
                subject=record.user_id,
                record_id=record.id,
                family_id=record.family_id,
                auth_version=record.auth_version,
                resource=record.resource,
                revoked=record.revoked,
            )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: StoredRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        raw_refresh = secrets.token_urlsafe(64)
        with SessionLocal() as db:
            record = db.scalar(
                select(OAuthRefreshToken).where(OAuthRefreshToken.id == refresh_token.record_id).with_for_update()
            )
            user = db.get(User, refresh_token.subject)
            if record is not None and record.revoked:
                db.execute(
                    update(OAuthRefreshToken)
                    .where(OAuthRefreshToken.family_id == record.family_id)
                    .values(revoked=True)
                )
                db.commit()
                raise TokenError("invalid_grant", "Refresh token reuse was detected; reconnect ChatGPT")
            if (
                record is None
                or record.expires_at < _now()
                or user is None
                or not user.is_active
                or user.must_change_password
                or record.auth_version != user.auth_version
            ):
                raise TokenError("invalid_grant", "The refresh token is invalid, expired, or revoked")
            record.revoked = True
            db.add(
                self._new_refresh_record(
                    raw_token=raw_refresh,
                    family_id=record.family_id,
                    client_id=client.client_id,
                    user=user,
                    scopes=scopes,
                    resource=record.resource,
                )
            )
            db.commit()
            tokens = self._oauth_tokens(
                client_id=client.client_id,
                user=user,
                scopes=scopes,
                resource=record.resource,
                refresh_token=raw_refresh,
            )
        logger.info("OAuth refresh token rotated: user_id=%s client_id=%s", user.id, client.client_id)
        return tokens

    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_token(token)
        except JWTError:
            return None
        scopes = str(payload.get("scope", "")).split()
        if payload.get("resource") != settings.mcp_resource_url or READ_SCOPE not in scopes:
            return None
        return AccessToken(
            token=token,
            client_id=payload.get("client_id", ""),
            scopes=scopes,
            expires_at=payload.get("exp"),
            resource=payload.get("resource"),
            subject=payload.get("sub"),
            claims=payload,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if not isinstance(token, StoredRefreshToken):
            return
        with SessionLocal() as db:
            db.execute(
                update(OAuthRefreshToken)
                .where(OAuthRefreshToken.family_id == token.family_id)
                .values(revoked=True)
            )
            db.commit()

    async def _get_jwks(self, client: OAuthClientInformationFull) -> dict[str, Any]:
        if client.jwks is not None:
            return client.jwks
        jwks_uri = str(client.jwks_uri)
        parsed = urlsplit(jwks_uri)
        if parsed.scheme != "https" or parsed.hostname != CHATGPT_CLIENT_HOST or not parsed.path.startswith("/oauth/"):
            raise AuthenticationError("The client JWKS URI is not trusted")
        cached = self._jwks_cache.get(jwks_uri)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            jwks = await self._get_json(jwks_uri)
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthenticationError("The client signing keys could not be loaded") from exc
        self._jwks_cache[jwks_uri] = (time.monotonic() + 300, jwks)
        return jwks

    async def verify_client_assertion(self, client: OAuthClientInformationFull, assertion: str) -> None:
        try:
            header = jwt.get_unverified_header(assertion)
            if header.get("alg") != "RS256" or not header.get("kid"):
                raise JWTError("Unsupported client assertion signature")
            jwks = await self._get_jwks(client)
            key = next((candidate for candidate in jwks.get("keys", []) if candidate.get("kid") == header["kid"]), None)
            if key is None:
                raise JWTError("Unknown client signing key")
            claims = jwt.decode(
                assertion,
                key,
                algorithms=["RS256"],
                audience=f"{settings.oauth_issuer_url}/token",
                issuer=client.client_id,
                options={"require_exp": True, "require_iat": True, "require_jti": True, "require_sub": True},
            )
            if claims.get("sub") != client.client_id:
                raise JWTError("Client assertion subject mismatch")
            issued_at = int(claims["iat"])
            expires_at = int(claims["exp"])
            now = _now()
            if issued_at > now + 60 or expires_at <= now or expires_at - issued_at > 300:
                raise JWTError("Client assertion lifetime is invalid")
            jti = str(claims["jti"])
        except (JWTError, KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("Invalid client assertion") from exc

        try:
            with SessionLocal() as db:
                db.execute(delete(OAuthClientAssertion).where(OAuthClientAssertion.expires_at < now))
                db.add(OAuthClientAssertion(jti_hash=_digest(jti), client_id=client.client_id, expires_at=expires_at))
                db.commit()
        except IntegrityError as exc:
            raise AuthenticationError("The client assertion has already been used") from exc


oauth_provider = ChatGptOAuthProvider()
oauth_client_authenticator = ChatGptClientAuthenticator(oauth_provider)
