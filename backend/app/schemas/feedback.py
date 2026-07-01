from datetime import datetime

from pydantic import BaseModel


class FeedbackIssueCreate(BaseModel):
    order_id: str | None = None
    category: str
    title: str
    description: str


class FeedbackIssueOut(BaseModel):
    id: str
    order_id: str | None
    category: str
    title: str
    description: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
