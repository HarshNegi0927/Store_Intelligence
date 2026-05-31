from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from database import get_db, EventModel

router = APIRouter()

# ─── GET /stores/{store_id}/heatmap ───────────────────────
@router.get("/stores/{store_id}/heatmap")
def get_heatmap(store_id: str, db: Session = Depends(get_db)):

    today = date.today()

    # ── Zone Visit Count ───────────────────────────────────
    zone_visits = db.query(
        EventModel.zone_id,
        func.count(EventModel.visitor_id).label("visit_count"),
        func.avg(EventModel.dwell_ms).label("avg_dwell_ms")
    ).filter(
        EventModel.store_id == store_id,
        EventModel.is_staff == False,
        EventModel.event_type == "ZONE_ENTER",
        EventModel.zone_id != None,
        func.date(EventModel.timestamp) == today
    ).group_by(EventModel.zone_id).all()

    if not zone_visits:
        return {
            "store_id": store_id,
            "date": str(today),
            "data_confidence": "LOW",
            "note": "No zone visit data for today",
            "heatmap": []
        }

    # ── Normalize 0-100 ────────────────────────────────────
    # Max values nikalo normalization ke liye
    max_visits = max(row.visit_count for row in zone_visits)
    max_dwell = max(row.avg_dwell_ms or 0 for row in zone_visits)

    heatmap = []
    for row in zone_visits:
        # Visit score — 60% weightage
        visit_score = (row.visit_count / max_visits * 100) if max_visits > 0 else 0

        # Dwell score — 40% weightage
        dwell_score = (
            (row.avg_dwell_ms or 0) / max_dwell * 100
        ) if max_dwell > 0 else 0

        # Combined score
        combined_score = round(
            (visit_score * 0.6) + (dwell_score * 0.4), 1
        )

        heatmap.append({
            "zone_id": row.zone_id,
            "visit_count": row.visit_count,
            "avg_dwell_seconds": round((row.avg_dwell_ms or 0) / 1000, 1),
            "score": combined_score,
            "label": get_label(combined_score)
        })

    # Score se sort karo — highest first
    heatmap.sort(key=lambda x: x["score"], reverse=True)

    # Total sessions check — confidence flag
    total_sessions = db.query(
        func.count(func.distinct(EventModel.visitor_id))
    ).filter(
        EventModel.store_id == store_id,
        EventModel.is_staff == False,
        func.date(EventModel.timestamp) == today
    ).scalar() or 0

    data_confidence = "LOW" if total_sessions < 20 else "HIGH"

    return {
        "store_id": store_id,
        "date": str(today),
        "data_confidence": data_confidence,
        "total_sessions": total_sessions,
        "heatmap": heatmap
    }

# ── Helper — Score to Label ────────────────────────────────
def get_label(score: float) -> str:
    if score >= 75:
        return "HOT"       # Bahut popular
    elif score >= 50:
        return "WARM"      # Average
    elif score >= 25:
        return "COOL"      # Low traffic
    else:
        return "COLD"      # Dead zone