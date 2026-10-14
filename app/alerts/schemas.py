from pydantic import BaseModel, HttpUrl, EmailStr, field_validator
from uuid import UUID
from typing import Literal, Union, Annotated
from pydantic import Field


# ---------------------------------------------------------------------------
# Per-channel config schemas (validated on input)
# ---------------------------------------------------------------------------

class SlackConfig(BaseModel):
    webhook_url: HttpUrl

    model_config = {"extra": "forbid"}


class DiscordConfig(BaseModel):
    webhook_url: HttpUrl

    model_config = {"extra": "forbid"}


class EmailConfig(BaseModel):
    to: EmailStr

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Request schemas — discriminated by channel_type
# ---------------------------------------------------------------------------

class AlertChannelCreateSlack(BaseModel):
    channel_type: Literal["slack"]
    config: SlackConfig

    model_config = {"extra": "forbid"}


class AlertChannelCreateDiscord(BaseModel):
    channel_type: Literal["discord"]
    config: DiscordConfig

    model_config = {"extra": "forbid"}


class AlertChannelCreateEmail(BaseModel):
    channel_type: Literal["email"]
    config: EmailConfig

    model_config = {"extra": "forbid"}


# Union with discriminator on channel_type
AlertChannelCreate = Annotated[
    Union[AlertChannelCreateSlack, AlertChannelCreateDiscord, AlertChannelCreateEmail],
    Field(discriminator="channel_type"),
]


# ---------------------------------------------------------------------------
# Response schema — masks sensitive config values
# ---------------------------------------------------------------------------

def _mask_config(raw: dict) -> dict:
    """Return a copy of config with sensitive values masked."""
    masked = {}
    for k, v in raw.items():
        if isinstance(v, str) and len(v) > 8:
            # Show first 8 chars then ***
            masked[k] = v[:8] + "***"
        else:
            masked[k] = v
    return masked


class AlertChannelResponse(BaseModel):
    id: UUID
    monitor_id: UUID
    channel_type: str
    config: dict

    model_config = {"from_attributes": True}

    @field_validator("config", mode="before")
    @classmethod
    def mask_sensitive(cls, v: dict) -> dict:
        return _mask_config(v)
