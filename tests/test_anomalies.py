# PROMPT: Write tests for anomaly detection in retail store API.
# Test queue spike detection, conversion drop, and dead zone detection.
# Include severity levels INFO/WARN/CRITICAL.
# CHANGES MADE: Moved DB setup to conftest.py, adjusted queue thresholds
# to match implementation (3+ = WARN, 5+ = CRITICAL), used real store
# zone names, fixed timestamp with minutes_ago helper.

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main import app

client = TestClient(app)

def make_event(
    visitor_id="VIS_test",
    event_type="ENTRY",
    camera_id="CAM_ENTRY_00",
    zone_id=None,
    queue_depth=None,
    is_staff=False,
    minutes_ago=5
):
    timestamp = (
        datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "event_id": str(uuid.uuid4()),
        "store_id": "STORE_BLR_001",
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": 0,
        "is_staff": is_staff,
        "confidence": 0.91,
        "event_metadata": {
            "queue_depth": queue_depth,
            "sku_zone": zone_id,
            "session_seq": 1
        }
    }

def ingest(events):
    return client.post("/events/ingest", json=events)

def test_no_anomalies_empty_store():
    """Empty store — ALL_CLEAR hona chahiye"""
    response = client.get("/stores/STORE_BLR_001/anomalies")
    assert response.status_code == 200
    data = response.json()
    types = [a["type"] for a in data["anomalies"]]
    assert "ALL_CLEAR" in types

def test_queue_spike_warn():
    """3-4 log billing mein — WARN hona chahiye"""
    events = [
        make_event(f"VIS_00{i}", "BILLING_QUEUE_JOIN",
                   camera_id="CAM_05",
                   zone_id="CASH_COUNTER",
                   queue_depth=i+1,
                   minutes_ago=3)
        for i in range(3)
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/anomalies")
    data = response.json()
    types = [a["type"] for a in data["anomalies"]]
    severities = {a["type"]: a["severity"] for a in data["anomalies"]}
    assert "BILLING_QUEUE_SPIKE" in types
    assert severities["BILLING_QUEUE_SPIKE"] == "WARN"

def test_queue_spike_critical():
    """5+ log billing mein — CRITICAL hona chahiye"""
    events = [
        make_event(f"VIS_00{i}", "BILLING_QUEUE_JOIN",
                   camera_id="CAM_05",
                   zone_id="CASH_COUNTER",
                   queue_depth=i+1,
                   minutes_ago=3)
        for i in range(6)
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/anomalies")
    data = response.json()
    severities = {a["type"]: a["severity"] for a in data["anomalies"]}
    assert severities.get("BILLING_QUEUE_SPIKE") == "CRITICAL"

def test_dead_zone_detection():
    """Zone 30 min se visit nahi hua — DEAD_ZONE hona chahiye"""
    events = [
        make_event("VIS_001", "ZONE_ENTER",
                   camera_id="CAM_01",
                   zone_id="KOREAN_SKINCARE",
                   minutes_ago=40)
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/anomalies")
    data = response.json()
    types = [a["type"] for a in data["anomalies"]]
    assert "DEAD_ZONE" in types

def test_anomaly_has_suggested_action():
    """Har anomaly mein suggested_action hona chahiye"""
    events = [
        make_event(f"VIS_00{i}", "BILLING_QUEUE_JOIN",
                   camera_id="CAM_05",
                   zone_id="CASH_COUNTER",
                   queue_depth=i+1,
                   minutes_ago=3)
        for i in range(5)
    ]
    ingest(events)
    response = client.get("/stores/STORE_BLR_001/anomalies")
    data = response.json()
    for anomaly in data["anomalies"]:
        assert "suggested_action" in anomaly
        assert len(anomaly["suggested_action"]) > 0

def test_anomaly_structure():
    """Anomaly response sahi structure mein hona chahiye"""
    response = client.get("/stores/STORE_BLR_001/anomalies")
    data = response.json()
    assert "store_id" in data
    assert "anomalies" in data
    assert "checked_at" in data
    for a in data["anomalies"]:
        assert "type" in a
        assert "severity" in a
        assert "message" in a
        assert "suggested_action" in a