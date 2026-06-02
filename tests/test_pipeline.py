# PROMPT: Write tests for retail store event ingestion pipeline.
# Test schema validation, idempotency, batch processing, and edge cases
# like re-entry detection and staff flagging.
# CHANGES MADE: Moved DB setup to conftest.py, updated to use
# event_metadata field, added camera_id to all events, fixed
# idempotency test to check DB directly.

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main import app
from conftest import TestingSessionLocal
from database import EventModel

client = TestClient(app)

def make_event(
    visitor_id="VIS_001",
    event_type="ENTRY",
    camera_id="CAM_ENTRY_00",
    zone_id=None,
    is_staff=False,
    confidence=0.91
):
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": "STORE_BLR_001",
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id": zone_id,
        "dwell_ms": 0,
        "is_staff": is_staff,
        "confidence": confidence,
        "event_metadata": {
            "queue_depth": None,
            "sku_zone": zone_id,
            "session_seq": 1
        }
    }

def test_basic_ingest():
    """Single event ingest sahi hona chahiye"""
    event = make_event()
    response = client.post("/events/ingest", json=[event])
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 1
    assert data["rejected"] == 0

def test_batch_ingest():
    """100 events ek saath ingest ho sakein"""
    events = [make_event(f"VIS_{i:03d}") for i in range(100)]
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 100
    assert data["rejected"] == 0

def test_idempotency():
    """Same event_id dobara bhejo — duplicate nahi hona chahiye"""
    event = make_event()
    client.post("/events/ingest", json=[event])
    client.post("/events/ingest", json=[event])
    db = TestingSessionLocal()
    count = db.query(EventModel).filter(
        EventModel.event_id == event["event_id"]
    ).count()
    db.close()
    assert count == 1

def test_all_event_types():
    """Saare valid event types accept hone chahiye"""
    event_types = [
        "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT",
        "ZONE_DWELL", "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON", "REENTRY"
    ]
    for i, et in enumerate(event_types):
        event = make_event(f"VIS_{i:03d}", et)
        if et in ["ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL"]:
            event["zone_id"] = "KOREAN_SKINCARE"
        response = client.post("/events/ingest", json=[event])
        assert response.status_code == 200

def test_staff_flagging():
    """Staff events store hone chahiye is_staff=True ke saath"""
    event = make_event("STAFF_001", is_staff=True)
    client.post("/events/ingest", json=[event])
    db = TestingSessionLocal()
    staff_event = db.query(EventModel).filter(
        EventModel.visitor_id == "STAFF_001"
    ).first()
    db.close()
    assert staff_event is not None
    assert staff_event.is_staff == True

def test_reentry_event():
    """REENTRY event properly store hona chahiye"""
    events = [
        make_event("VIS_001", "ENTRY"),
        make_event("VIS_001", "EXIT"),
        make_event("VIS_001", "REENTRY"),
    ]
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 3

def test_confidence_stored():
    """Low confidence events bhi store hone chahiye"""
    event = make_event(confidence=0.35)
    client.post("/events/ingest", json=[event])
    db = TestingSessionLocal()
    stored = db.query(EventModel).filter(
        EventModel.event_id == event["event_id"]
    ).first()
    db.close()
    assert stored is not None
    assert abs(stored.confidence - 0.35) < 0.01

def test_empty_batch():
    """Empty batch — crash nahi hona chahiye"""
    response = client.post("/events/ingest", json=[])
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 0

def test_invalid_event_type():
    """Invalid event type — 422 aana chahiye"""
    event = make_event()
    event["event_type"] = "INVALID_TYPE"
    response = client.post("/events/ingest", json=[event])
    assert response.status_code == 422

def test_funnel_endpoint():
    """Funnel endpoint sahi response de"""
    response = client.get("/stores/STORE_BLR_001/funnel")
    assert response.status_code == 200
    data = response.json()
    assert "funnel" in data
    assert len(data["funnel"]) == 4
    stages = [f["stage"] for f in data["funnel"]]
    assert "Entry" in stages
    assert "Zone Visit" in stages
    assert "Billing Queue" in stages
    assert "Purchase" in stages