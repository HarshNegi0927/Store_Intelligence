from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from database import get_db, EventModel

router = APIRouter()

# ─── GET /health ───────────────────────────────────────────
@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    
    now = datetime.utcnow()
    
    try:
        # ── DB Check ───────────────────────────────────────
        # DB alive hai?
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": "Database unavailable",
            "checked_at": now.isoformat()
        }

    # ── Per Store Last Event ───────────────────────────────
    # Har store ka last event kab aaya
    store_feeds = db.query(
        EventModel.store_id,
        func.max(EventModel.timestamp).label("last_event")
    ).group_by(EventModel.store_id).all()

    stores_status = {}
    for store in store_feeds:
        last_event = store.last_event
        
        # 10 min se zyada purana? STALE_FEED!
        diff_minutes = (now - last_event).total_seconds() / 60
        
        if diff_minutes > 10:
            feed_status = "STALE_FEED"
        else:
            feed_status = "OK"

        stores_status[store.store_id] = {
            "last_event": last_event.isoformat(),
            "minutes_ago": round(diff_minutes, 1),
            "feed_status": feed_status
        }

    # ── Overall Status ─────────────────────────────────────
    has_stale = any(
        v["feed_status"] == "STALE_FEED"
        for v in stores_status.values()
    )

    return {
        "status": "healthy",
        "db_status": db_status,
        "checked_at": now.isoformat(),
        "stores": stores_status,
        "overall_feed_status": "STALE_FEED" if has_stale else "OK"
    }