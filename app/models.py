"""Pydantic models for request/response validation."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re


class WebhookRequest(BaseModel):
    """Request model for POST /webhook."""
    message_id: str = Field(..., min_length=1)
    from_: str = Field(..., alias="from")
    to: str
    ts: str
    text: Optional[str] = Field(None, max_length=4096)
    
    @field_validator("from_", "to")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate E.164-like phone number format."""
        if not v.startswith("+") or not v[1:].isdigit():
            raise ValueError("Phone number must be in E.164 format (start with +, followed by digits)")
        return v
    
    @field_validator("ts")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate ISO-8601 UTC timestamp with Z suffix."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Timestamp must be in ISO-8601 UTC format with Z suffix")
        if not v.endswith("Z"):
            raise ValueError("Timestamp must end with Z")
        return v
    
    class Config:
        populate_by_name = True


class WebhookResponse(BaseModel):
    """Response model for POST /webhook."""
    status: str


class MessageResponse(BaseModel):
    """Message item in GET /messages response."""
    message_id: str
    from_: str = Field(..., alias="from")
    to: str
    ts: str
    text: Optional[str] = None
    
    class Config:
        populate_by_name = True


class MessagesListResponse(BaseModel):
    """Response model for GET /messages."""
    data: List[MessageResponse]
    total: int
    limit: int
    offset: int


class SenderStats(BaseModel):
    """Sender statistics in GET /stats response."""
    from_: str = Field(..., alias="from")
    count: int
    
    class Config:
        populate_by_name = True


class StatsResponse(BaseModel):
    """Response model for GET /stats."""
    total_messages: int
    senders_count: int
    messages_per_sender: List[SenderStats]
    first_message_ts: Optional[str] = None
    last_message_ts: Optional[str] = None

