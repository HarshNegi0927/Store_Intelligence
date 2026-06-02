import uuid
from datetime import datetime, timezone

STORE_ID = "STORE_BLR_001"

def build_event(
    camera_id: str,
    visitor_id: str,
    event_type: str,
    timestamp: datetime,
    zone_id: str = None,
    dwell_ms: int = 0,
    is_staff: bool = False,
    confidence: float = 0.9,
    queue_depth: int = None,
    seq: int = 1
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": STORE_ID,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": round(confidence, 2),
        "event_metadata": {
            "queue_depth": queue_depth,
            "sku_zone": zone_id,
            "session_seq": seq
        }
    }