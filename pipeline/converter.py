import uuid
import json
import sys
import requests
from datetime import datetime

# ─── Config ───────────────────────────────────────────────
API_URL = "http://127.0.0.1:8000/events/ingest"
DEFAULT_STORE_ID = "STORE_BLR_001"

STORE_CODE_MAP = {
    "store_1076": "STORE_BLR_001",
    "store_1008": "STORE_BLR_001",
    "ST1008":     "STORE_BLR_001",
    "ST1076":     "STORE_BLR_001",
}

EVENT_TYPE_MAP = {
    "entry":           "ENTRY",
    "exit":            "EXIT",
    "zone_entered":    "ZONE_ENTER",
    "zone_exited":     "ZONE_EXIT",
    "queue_completed": "BILLING_QUEUE_JOIN",
    "queue_abandoned": "BILLING_QUEUE_ABANDON",
}

# ─── Store ID Resolver ─────────────────────────────────────
def resolve_store_id(raw: dict) -> str:
    raw_store = (
        raw.get("store_id") or
        raw.get("store_code") or ""
    ).strip()

    if raw_store in STORE_CODE_MAP:
        return STORE_CODE_MAP[raw_store]

    if raw_store:
        normalized = raw_store.upper()
        normalized = normalized.replace("STORE_", "").replace("ST", "")
        return f"STORE_{normalized}"

    return DEFAULT_STORE_ID

# ─── Camera ID — Event type se assign karo ────────────────
def resolve_camera_id(raw: dict, event_type: str) -> str:
    """
    Event type ke hisaab se sahi camera ID assign karo
    Metrics.py specific cameras expect karta hai
    """
    if event_type in ["ENTRY", "EXIT", "REENTRY"]:
        return "CAM_ENTRY_00"

    elif event_type in ["BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON"]:
        return "CAM_05"

    else:
        # Zone events — zone name se CAM_01 ya CAM_02
        zone = (raw.get("zone_name") or raw.get("zone_id") or "").upper()
        cam02_zones = ["ALPS", "LAKME", "MAYBELLINE", "FACES", "SWISS", "STREAX"]
        if any(z in zone for z in cam02_zones):
            return "CAM_02"
        return "CAM_01"

# ─── Timestamp Normalizer ──────────────────────────────────
def normalize_timestamp(ts: str) -> str:
    if not ts:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    ts = str(ts).strip().replace(" ", "T")

    try:
        if "T" in ts:
            time_part = ts.split("T")[1].split(".")[0].replace("Z", "")
        else:
            time_part = "12:00:00"
    except:
        time_part = "12:00:00"

    # Aaj ki date + original time
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return f"{today}T{time_part}Z"

# ─── Main Converter ───────────────────────────────────────
def convert_event(raw: dict) -> dict:
    raw_type = raw.get("event_type", "").lower().strip()
    event_type = EVENT_TYPE_MAP.get(raw_type)

    if not event_type:
        return None

    visitor_id = (
        raw.get("id_token") or
        raw.get("track_id") or
        f"VIS_{uuid.uuid4().hex[:6]}"
    )

    if not str(visitor_id).startswith("VIS_"):
        visitor_id = f"VIS_{visitor_id}"

    zone_id = raw.get("zone_name") or raw.get("zone_id") or None

    if event_type in ["ENTRY", "EXIT", "REENTRY"]:
        zone_id = None

    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   resolve_store_id(raw),
        "camera_id":  resolve_camera_id(raw, event_type),
        "visitor_id": str(visitor_id),
        "event_type": event_type,
        "timestamp":  normalize_timestamp(
            raw.get("event_timestamp") or raw.get("event_time")
        ),
        "zone_id":    zone_id,
        "dwell_ms":   0,
        "is_staff":   bool(raw.get("is_staff", False)),
        "confidence": 0.9,
        "event_metadata": {
            "queue_depth": None,
            "sku_zone":    zone_id,
            "session_seq": 1,
            "gender":      raw.get("gender_pred") or raw.get("gender"),
            "age_bucket":  raw.get("age_bucket"),
            "group_id":    raw.get("group_id"),
            "group_size":  raw.get("group_size"),
        }
    }

# ─── JSONL File Converter ─────────────────────────────────
def convert_jsonl_file(filepath: str) -> list:
    events = []
    errors = []

    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                converted = convert_event(raw)
                if converted:
                    events.append(converted)
                else:
                    errors.append(
                        f"Line {i}: Unknown event type '{raw.get('event_type')}'"
                    )
            except Exception as e:
                errors.append(f"Line {i}: {str(e)}")

    print(f"✅ Converted: {len(events)} events")
    if errors:
        print(f"⚠️  Skipped: {len(errors)}")
        for e in errors:
            print(f"   {e}")

    return events

# ─── Send to API ──────────────────────────────────────────
def send_to_api(events: list):
    if not events:
        print("No events to send!")
        return

    try:
        r = requests.get("http://127.0.0.1:8000/health", timeout=5)
        print("✅ API healthy!\n")
    except Exception as e:
        print(f"❌ API not running: {e}")
        return

    batch_size = 50
    total_accepted = 0
    total_rejected = 0

    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        try:
            r = requests.post(API_URL, json=batch, timeout=10)

            if r.status_code == 200:
                result = r.json()
                accepted = result.get("accepted", 0) or 0
                rejected = result.get("rejected", 0) or 0
                total_accepted += accepted
                total_rejected += rejected
                print(f"📤 Batch {i//batch_size + 1}: accepted={accepted} rejected={rejected}")

            elif r.status_code == 422:
                print(f"❌ Validation error!")
                print(r.json())

            else:
                print(f"❌ HTTP {r.status_code}: {r.text}")

        except Exception as e:
            print(f"❌ Error: {e}")

    print(f"\n✅ Done!")
    print(f"   Accepted: {total_accepted}")
    print(f"   Rejected: {total_rejected}")

# ─── Main ─────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python converter.py <path_to_events.jsonl>")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"🔄 Converting: {filepath}\n")

    events = convert_jsonl_file(filepath)

    if events:
        print(f"\n📤 Sending {len(events)} events to API...")
        send_to_api(events)
        store_ids = list(set(e["store_id"] for e in events))
        print(f"\n📊 Check metrics:")
        for sid in store_ids:
            print(f"   http://127.0.0.1:8000/stores/{sid}/metrics")