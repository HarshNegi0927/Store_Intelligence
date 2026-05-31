from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid

class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: int = 1

class StoreEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: Literal[
        "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT",
        "ZONE_DWELL", "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON", "REENTRY"
    ]
    timestamp: datetime
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float
    event_metadata: EventMetadata = Field(default_factory=EventMetadata)

class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    errors: list = []