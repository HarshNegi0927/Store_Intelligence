from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from database import get_db, EventModel

router = APIRouter()

@router.get("/stores/{store_id}/metrics")
def get_metrics(store_id: str, db: Session = Depends(get_db)):

    today = date.today()

    def base_query(camera_id=None):
        q = db.query(EventModel).filter(
            EventModel.store_id == store_id,
            EventModel.is_staff == False,
            func.date(EventModel.timestamp) == today
        )
        if camera_id:
            q = q.filter(EventModel.camera_id == camera_id)
        return q

    # ── 1. Footfall — Entry camera se ─────────────────────
    # Sirf CAM_ENTRY_00 se ENTRY events
    footfall = base_query("CAM_ENTRY_00").filter(
        EventModel.event_type == "ENTRY"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # ── 2. Zone Visitors — Floor cameras se ───────────────
    # CAM_01 + CAM_02 se unique visitors
    zone_visitors = base_query().filter(
        EventModel.event_type == "ZONE_ENTER",
        EventModel.camera_id.in_(["CAM_01", "CAM_02"])
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # ── 3. Billing Visitors — CAM_05 se ───────────────────
    billing_visitors = base_query("CAM_05").filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # ── 4. Conversion Rate ─────────────────────────────────
    # Billing / Footfall
    # Footfall best proxy hai total visitors ka
    unique_visitors = footfall if footfall > 0 else zone_visitors

    conversion_rate = round(
        (billing_visitors / unique_visitors * 100), 2
    ) if unique_visitors > 0 else 0.0

    # ── 5. Avg Dwell Per Zone ──────────────────────────────
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

    # ── 6. Queue Depth ─────────────────────────────────────
    latest_queue = base_query("CAM_05").filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN"
    ).order_by(
        EventModel.timestamp.desc()
    ).first()

    queue_depth = 0
    if latest_queue and latest_queue.event_metadata:
        queue_depth = latest_queue.event_metadata.get("queue_depth", 0) or 0

    # ── 7. Abandonment Rate ────────────────────────────────
    abandoned = base_query("CAM_05").filter(
        EventModel.event_type == "BILLING_QUEUE_ABANDON"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    abandonment_rate = round(
        (abandoned / billing_visitors * 100), 2
    ) if billing_visitors > 0 else 0.0

    # ── Zero Traffic ───────────────────────────────────────
    if unique_visitors == 0:
        return {
            "store_id": store_id,
            "date": str(today),
            "unique_visitors": 0,
            "footfall": 0,
            "zone_visitors": 0,
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
        "footfall": footfall,
        "zone_visitors": zone_visitors,
        "conversion_rate": conversion_rate,
        "converted_visitors": billing_visitors,
        "avg_dwell_per_zone": avg_dwell_per_zone,
        "queue_depth": queue_depth,
        "abandonment_rate": abandonment_rate
    }