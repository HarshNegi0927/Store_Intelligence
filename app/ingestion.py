from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from database import get_db, EventModel
from models import StoreEvent, IngestResponse

router = APIRouter()


@router.post("/events/ingest", response_model=IngestResponse)
def ingest_events(events: List[StoreEvent], db: Session = Depends(get_db)):
    accepted = 0
    rejected = 0
    errors = []

    for event in events:
        try:

            existing = db.query(EventModel).filter(
                EventModel.event_id == event.event_id
            ).first()

            if existing:
                accepted += 1
                continue

            # DB mein save karo
            db_event = EventModel(
                event_id   = event.event_id,
                store_id   = event.store_id,
                camera_id  = event.camera_id,
                visitor_id = event.visitor_id,
                event_type = event.event_type,
                timestamp  = event.timestamp,
                zone_id    = event.zone_id,
                dwell_ms   = event.dwell_ms,
                is_staff   = event.is_staff,
                confidence = event.confidence,
                event_metadata = event.metadata.dict()
            )
            db.add(db_event)
            accepted += 1

        except Exception as e:
            rejected += 1
            errors.append({
                "event_id": event.event_id,
                "error": str(e)
            })

    db.commit()

    return IngestResponse(
        accepted=accepted,
        rejected=rejected,
        errors=errors
    )