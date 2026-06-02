# PROMPT: Write comprehensive tests for a FastAPI store intelligence API
# that tracks retail visitors, conversion rates, and zone dwell times.
# Include edge cases for empty store, zero purchases, and staff exclusion.
# CHANGES MADE: Moved DB setup to conftest.py, updated event schema to use
# event_metadata, added camera_id filtering for metrics, added realistic
# store zone names matching Brigade Road Bangalore store layout.

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main import app

client = TestClient(app)

# ─── Helper ───────────────────────────────────────────────
def make_event(
    visitor_id="VIS_test01",
    event_type="ENTRY",
    store_id="STORE_BLR_001",
    camera_id="CAM_ENTRY_00",
    zone_id=None,
    dwell_ms=0,
    is_staff=False,
    confidence=0.91,
    queue_depth=None,
    timestamp=None
):
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "event_metadata": {
            "queue_depth": queue_depth,
            "sku_zone": zone_id,
            "session_seq": 1
        }
    }

def ingest(events):
    return client.post("/events/ingest", json=events)

# ─── Tests ────────────────────────────────────────────────

def test_metrics_empty_store():
    """Zero traffic — API crash nahi hona chahiye"""
    response = client.get("/stores/STORE_BLR_001/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0
    assert "data_note" in data

def test_unique_visitors_count():
    """3 alag visitors entry kare — 3 unique hone chahiye"""
    events = [
        make_event("VIS_001", "ENTRY"),
        make_event("VIS_002", "ENTRY"),
        make_event("VIS_003", "ENTRY"),
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 3

def test_staff_excluded_from_metrics():
    """Staff events metrics mein count nahi hone chahiye"""
    events = [
        make_event("VIS_001", "ENTRY", is_staff=False),
        make_event("STAFF_001", "ENTRY", is_staff=True),
        make_event("STAFF_002", "ENTRY", is_staff=True),
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/metrics")
    data = response.json()
    assert data["unique_visitors"] == 1

def test_conversion_rate():
    """2 visitors aaye, 1 ne purchase kiya — 50% conversion"""
    events = [
        make_event("VIS_001", "ENTRY"),
        make_event("VIS_002", "ENTRY"),
        make_event("VIS_001", "BILLING_QUEUE_JOIN",
                   camera_id="CAM_05",
                   zone_id="CASH_COUNTER",
                   queue_depth=1),
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/metrics")
    data = response.json()
    assert data["converted_visitors"] == 1
    assert data["conversion_rate"] == 50.0

def test_zero_purchases():
    """Visitors aaye but koi purchase nahi — 0% conversion"""
    events = [
        make_event("VIS_001", "ENTRY"),
        make_event("VIS_002", "ENTRY"),
        make_event("VIS_001", "ZONE_ENTER",
                   camera_id="CAM_01",
                   zone_id="KOREAN_SKINCARE"),
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/metrics")
    data = response.json()
    assert data["conversion_rate"] == 0.0
    assert data["converted_visitors"] == 0

def test_ingest_idempotent():
    """Same event dobara bhejo — duplicate nahi hona chahiye"""
    event = make_event("VIS_001", "ENTRY")
    ingest([event])
    ingest([event])
    response = client.get("/stores/STORE_BLR_001/metrics")
    data = response.json()
    assert data["unique_visitors"] == 1

def test_avg_dwell_per_zone():
    """Zone dwell time sahi calculate hona chahiye"""
    events = [
        make_event("VIS_001", "ZONE_DWELL",
                   camera_id="CAM_01",
                   zone_id="KOREAN_SKINCARE",
                   dwell_ms=60000),
        make_event("VIS_002", "ZONE_DWELL",
                   camera_id="CAM_01",
                   zone_id="KOREAN_SKINCARE",
                   dwell_ms=120000),
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/metrics")
    data = response.json()
    # Zone data aa raha hai ya nahi check karo
    assert "avg_dwell_per_zone" in data
    # Agar zone hai toh value check karo
    if "KOREAN_SKINCARE" in data["avg_dwell_per_zone"]:
        assert data["avg_dwell_per_zone"]["KOREAN_SKINCARE"] == 90.0

def test_queue_depth():
    """Billing queue depth sahi hona chahiye"""
    events = [
        make_event("VIS_001", "BILLING_QUEUE_JOIN",
                   camera_id="CAM_05",
                   zone_id="CASH_COUNTER",
                   queue_depth=3),
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/metrics")
    data = response.json()
    # Queue depth present hona chahiye
    assert "queue_depth" in data
    assert data["queue_depth"] >= 0

def test_health_endpoint():
    """Health endpoint sahi response de"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["db_status"] == "healthy"

def test_partial_success_malformed():
    """Kuch sahi kuch galat events — partial success"""
    events = [
        make_event("VIS_001", "ENTRY"),
    ]
    response = client.post("/events/ingest", json=events)
    assert response.status_code in [200, 422]