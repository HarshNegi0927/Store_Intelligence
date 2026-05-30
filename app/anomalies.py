from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta

from database import get_db, EventModel

router = APIRouter()

# ─── GET /stores/{store_id}/anomalies ─────────────────────
@router.get("/stores/{store_id}/anomalies")
def get_anomalies(store_id: str, db: Session = Depends(get_db)):

    today = date.today()
    now = datetime.utcnow()
    anomalies = []

    # Base query
    base = db.query(EventModel).filter(
        EventModel.store_id == store_id,
        EventModel.is_staff == False,
        func.date(EventModel.timestamp) == today
    )

    # ── Anomaly 1: BILLING_QUEUE_SPIKE ────────────────────
    # Last 10 min mein kitne log queue mein join hue
    ten_min_ago = now - timedelta(minutes=10)
    recent_queue = base.filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN",
        EventModel.timestamp >= ten_min_ago
    ).count()

    if recent_queue >= 5:
        anomalies.append({
            "type": "BILLING_QUEUE_SPIKE",
            "severity": "CRITICAL",
            "message": f"{recent_queue} customers joined billing queue in last 10 minutes",
            "suggested_action": "Open additional billing counter or call more staff to billing area"
        })
    elif recent_queue >= 3:
        anomalies.append({
            "type": "BILLING_QUEUE_SPIKE",
            "severity": "WARN",
            "message": f"{recent_queue} customers in billing queue recently",
            "suggested_action": "Monitor billing queue — may need additional staff soon"
        })

    # ── Anomaly 2: CONVERSION_DROP ────────────────────────
    # Aaj ki conversion rate nikalo
    total_visitors = base.filter(
        EventModel.event_type == "ENTRY"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    billing_visitors = base.filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    abandoned = base.filter(
        EventModel.event_type == "BILLING_QUEUE_ABANDON"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    purchases = max(0, billing_visitors - abandoned)

    today_conversion = (
        purchases / total_visitors * 100
    ) if total_visitors > 0 else 0.0

    # 7 day average se compare karo
    seven_days_ago = now - timedelta(days=7)
    historical = db.query(EventModel).filter(
        EventModel.store_id == store_id,
        EventModel.is_staff == False,
        EventModel.timestamp >= seven_days_ago,
        EventModel.timestamp < datetime.combine(today, datetime.min.time())
    )

    hist_visitors = historical.filter(
        EventModel.event_type == "ENTRY"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    hist_billing = historical.filter(
        EventModel.event_type == "BILLING_QUEUE_JOIN"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    hist_abandoned = historical.filter(
        EventModel.event_type == "BILLING_QUEUE_ABANDON"
    ).with_entities(
        func.count(func.distinct(EventModel.visitor_id))
    ).scalar() or 0

    hist_purchases = max(0, hist_billing - hist_abandoned)
    hist_conversion = (
        hist_purchases / hist_visitors * 100
    ) if hist_visitors > 0 else 0.0

    # 20% se zyada drop hua?
    if hist_conversion > 0:
        drop_pct = ((hist_conversion - today_conversion) / hist_conversion) * 100
        if drop_pct >= 30:
            anomalies.append({
                "type": "CONVERSION_DROP",
                "severity": "CRITICAL",
                "message": f"Conversion rate dropped {round(drop_pct, 1)}% vs 7-day average ({round(hist_conversion,1)}% → {round(today_conversion,1)}%)",
                "suggested_action": "Check staff availability, promotions, and product display — immediate review needed"
            })
        elif drop_pct >= 20:
            anomalies.append({
                "type": "CONVERSION_DROP",
                "severity": "WARN",
                "message": f"Conversion rate dropped {round(drop_pct, 1)}% vs 7-day average",
                "suggested_action": "Review floor staff engagement and current promotions"
            })

    # ── Anomaly 3: DEAD_ZONE ───────────────────────────────
    # Koi zone 30 min se kisi ne visit nahi kiya
    thirty_min_ago = now - timedelta(minutes=30)

    # Saare zones jo aaj visit hue
    all_zones = base.filter(
        EventModel.event_type == "ZONE_ENTER",
        EventModel.zone_id != None
    ).with_entities(
        func.distinct(EventModel.zone_id)
    ).all()

    all_zone_ids = [z[0] for z in all_zones]

    # Last 30 min mein kaunse zones visit hue
    recent_zones = base.filter(
        EventModel.event_type == "ZONE_ENTER",
        EventModel.timestamp >= thirty_min_ago,
        EventModel.zone_id != None
    ).with_entities(
        func.distinct(EventModel.zone_id)
    ).all()

    recent_zone_ids = [z[0] for z in recent_zones]

    # Jo zones pehle active the but ab nahi
    dead_zones = [z for z in all_zone_ids if z not in recent_zone_ids]

    for zone in dead_zones:
        anomalies.append({
            "type": "DEAD_ZONE",
            "severity": "INFO",
            "message": f"Zone '{zone}' has had no visitors in the last 30 minutes",
            "suggested_action": f"Check display and product availability in {zone} zone"
        })

    # ── No Anomalies ───────────────────────────────────────
    if not anomalies:
        anomalies.append({
            "type": "ALL_CLEAR",
            "severity": "INFO",
            "message": "No anomalies detected",
            "suggested_action": "Continue monitoring"
        })

    return {
        "store_id": store_id,
        "checked_at": now.isoformat(),
        "anomalies": anomalies
    }