from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date

from database import get_db, EventModel

router = APIRouter()

@router.get("/stores/{store_id}/metrics")
def get_metrics(store_id: str, db: Session = Depends(get_db)):

    today = date.today()

    base = db.query(EventModel).filter(
        EventModel.store_id == store_id,
        EventModel.is_staff == False,
        func.date(EventModel.timestamp) == today
    )

    # ── 1. Unique Visitors ─────────────────────────────────
    unique_visitors = base.filter(
        EventModel.event_type == "ENTRY"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # ── 2. Converted Visitors ──────────────────────────────
    converted_visitors = base.filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    conversion_rate = round(
        (converted_visitors / unique_visitors * 100), 2
    ) if unique_visitors > 0 else 0.0

    # ── 3. Avg Dwell Per Zone ──────────────────────────────
    zone_dwell = db.query(
        EventModel.zone_id,
        func.avg(EventModel.dwell_ms).label("avg_dwell_ms")
    ).filter(
        EventModel.store_id == store_id,
        EventModel.is_staff == False,
        EventModel.event_type == "ZONE_DWELL",
        EventModel.zone_id != None,
        func.date(EventModel.timestamp) == today
    ).group_by(EventModel.zone_id).all()

    avg_dwell_per_zone = {
        row.zone_id: round(row.avg_dwell_ms / 1000, 1)
        for row in zone_dwell
    }

    # ── 4. Queue Depth ─────────────────────────────────────
    latest_queue = base.filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN"
    ).order_by(
        EventModel.timestamp.desc()
    ).first()

    queue_depth = 0
    if latest_queue and latest_queue.event_metadata:
        queue_depth = latest_queue.event_metadata.get("queue_depth", 0) or 0

    # ── 5. Abandonment Rate ────────────────────────────────
    abandoned = base.filter(
        EventModel.event_type == "BILLING_QUEUE_ABANDON"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    abandonment_rate = round(
        (abandoned / converted_visitors * 100), 2
    ) if converted_visitors > 0 else 0.0

    # ── Zero Traffic ───────────────────────────────────────
    if unique_visitors == 0:
        return {
            "store_id": store_id,
            "date": str(today),
            "unique_visitors": 0,
            "conversion_rate": 0.0,
            "converted_visitors": 0,
            "avg_dwell_per_zone": {},
            "queue_depth": 0,
            "abandonment_rate": 0.0,
            "data_note": "No visitor data for today"
        }

    return {
        "store_id": store_id,
        "date": str(today),
        "unique_visitors": unique_visitors,
        "conversion_rate": conversion_rate,
        "converted_visitors": converted_visitors,
        "avg_dwell_per_zone": avg_dwell_per_zone,
        "queue_depth": queue_depth,
        "abandonment_rate": abandonment_rate
    }