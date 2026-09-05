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

    contact_name: str | None = None
    phone: str | None = None
    approved_delivery_addresses: list[str] = []
    master_data_enabled: bool = False

    model_config = {"from_attributes": True}
