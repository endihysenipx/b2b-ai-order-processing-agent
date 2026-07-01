from pydantic import BaseModel


class ClientOut(BaseModel):
    id: str
    client_name: str
    customer_number: str
    default_email: str | None
    email_domain: str
    extraction_prompt: str
    required_fields: list[str]
    validation_rules: dict
    is_active: bool

    model_config = {"from_attributes": True}
