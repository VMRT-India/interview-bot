import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserAPIKeyCreate(BaseModel):
    provider: str
    api_key: str
    model_name: str | None = None
    base_url: str | None = None  # required for providers other than groq/gemini/openai


class UserAPIKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    model_name: str | None
    base_url: str | None
    created_at: datetime
    updated_at: datetime
    # Deliberately no key/encrypted_key field — never return the secret once stored
