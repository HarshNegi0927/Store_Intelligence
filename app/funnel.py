from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from database import get_db, EventModel

router = APIRouter()

@router.get("/stores/{store_id}/funnel")
def get_funnel(store_id: str, db: Session = Depends(get_db)):

    today = date.today()

    base = db.query(EventModel).filter(
        EventModel.store_id == store_id,
        EventModel.is_staff == False,
        func.date(EventModel.timestamp) == today
    )

    # Stage 1 — Entry
    total_entries = base.filter(
        EventModel.event_type == "ENTRY"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # Stage 2 — Zone visits — seedha count
    zone_visitors = base.filter(
        EventModel.event_type == "ZONE_ENTER"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # Stage 3 — Billing
    billing_visitors = base.filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    # Stage 4 — Purchases
    abandoned = base.filter(
        EventModel.event_type == "BILLING_QUEUE_ABANDON"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    purchases = max(0, billing_visitors - abandoned)

    def dropoff(current, previous):
        if previous == 0:
            return 0.0
        lost = previous - current
        return round((lost / previous) * 100, 2)

    return {
        "store_id": store_id,
        "date": str(today),
        "funnel": [
            {
                "stage": "Entry",
                "count": total_entries,
                "dropoff_pct": 0.0
            },
            {
                "stage": "Zone Visit",
                "count": zone_visitors,
                "dropoff_pct": dropoff(zone_visitors, total_entries)
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
            "total_purchased": purchases,
            "overall_conversion_pct": round(
                purchases / total_entries * 100, 2
            ) if total_entries > 0 else 0.0
        }
    }