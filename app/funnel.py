from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from database import get_db, EventModel

router = APIRouter()

@router.get("/stores/{store_id}/funnel")
def get_funnel(store_id: str, db: Session = Depends(get_db)):

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

    # ── Stage 1: Footfall ──────────────────────────────────
    # Entry camera se — kitne log aaye
    total_entries = base_query("CAM_ENTRY_00").filter(
        EventModel.event_type == "ENTRY"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # ── Stage 2: Zone Visit ────────────────────────────────
    # Floor cameras se — kitne log browse kiye
    zone_visitors = base_query().filter(
        EventModel.event_type == "ZONE_ENTER",
        EventModel.camera_id.in_(["CAM_01", "CAM_02"])
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # ── Stage 3: Billing Queue ─────────────────────────────
    # Billing camera se — kitne log counter tak gaye
    billing_visitors = base_query("CAM_05").filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # ── Stage 4: Purchase ──────────────────────────────────
    # Billing - abandoned
    abandoned = base_query("CAM_05").filter(
        EventModel.event_type == "BILLING_QUEUE_ABANDON"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    purchases = max(0, billing_visitors - abandoned)

    # ── Dropoff % ──────────────────────────────────────────
    def dropoff(current, previous):
        if previous == 0:
            return 0.0
        return round(((previous - current) / previous) * 100, 2)

    # Funnel base — entry ya zone jo bhi bada ho
    funnel_base = max(total_entries, zone_visitors)

    return {
        "store_id": store_id,
        "date": str(today),
        "note": "Cross-camera Re-ID not implemented — each camera tracked independently",
        "funnel": [
            {
                "stage": "Entry",
                "count": total_entries,
                "dropoff_pct": 0.0
            },
            {
                "stage": "Zone Visit",
                "count": zone_visitors,
                "dropoff_pct": 0.0
            },
            {
                "stage": "Billing Queue",
                "count": billing_visitors,
                "dropoff_pct": dropoff(billing_visitors, zone_visitors)
            },
            {
                "stage": "Purchase",
                "count": purchases,
                "dropoff_pct": dropoff(purchases, billing_visitors)
            }
        ],
        "summary": {
            "total_entered": total_entries,
            "total_zone_visitors": zone_visitors,
            "total_purchased": purchases,
            "overall_conversion_pct": round(
                purchases / funnel_base * 100, 2
            ) if funnel_base > 0 else 0.0
        }
    }