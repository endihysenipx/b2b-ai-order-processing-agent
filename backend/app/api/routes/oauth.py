from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.models.user import User
from app.oauth.provider import oauth_provider
from app.schemas.oauth import OAuthAuthorizationDecision, OAuthAuthorizationRedirect

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.post("/authorize/complete", response_model=OAuthAuthorizationRedirect)
async def complete_oauth_authorization(
    payload: OAuthAuthorizationDecision,
    current_user: User = Depends(get_current_user),
) -> OAuthAuthorizationRedirect:
    try:
        redirect_url = await oauth_provider.complete_authorization(
            payload.request_token,
            current_user,
            payload.approved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return OAuthAuthorizationRedirect(redirect_url=redirect_url)
