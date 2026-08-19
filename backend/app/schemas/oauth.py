from pydantic import BaseModel


class OAuthAuthorizationDecision(BaseModel):
    request_token: str
    approved: bool


class OAuthAuthorizationRedirect(BaseModel):
    redirect_url: str
