import csv
import uuid
import json
import random
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Config ───────────────────────────────────────────────
STORE_ID = "STORE_BLR_001"
API_URL = "http://127.0.0.1:8000/events/ingest"
CSV_PATH = r"C:\Users\himansu\OneDrive\Desktop\PurplleVideos\Brigade_Bangalore_10_April_26 (1)bc6219c (1).csv"

# Zones available in store
BROWSING_ZONES = [
    "KOREAN_SKINCARE", "GOOD_VIBES", "MINIMALIST",
    "ALPS", "LAKME", "MAYBELLINE", "FRAGRANCE",
    "NAIL_UNIT", "ACCESSORIES"
]

# Category to zone mapping from CSV
CATEGORY_ZONE_MAP = {
    "skin":          ["KOREAN_SKINCARE", "MINIMALIST", "GOOD_VIBES"],
    "makeup":        ["MAYBELLINE", "LAKME", "ALPS"],
    "bath-and-body": ["GOOD_VIBES", "ALPS"],
    "hair":          ["ALPS", "MINIMALIST"],
    "fragrance":     ["FRAGRANCE"],
    "personal-care": ["KOREAN_SKINCARE", "GOOD_VIBES"],
}

def random_visitor_id():
    return f"VIS_{uuid.uuid4().hex[:6]}"

def build_event(
    visitor_id, event_type, timestamp,
    camera_id="CAM_01", zone_id=None,
    dwell_ms=0, is_staff=False,
    confidence=0.91, queue_depth=None,
    seq=1
):
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": STORE_ID,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": round(confidence, 2),
        "event_metadata": {
            "queue_depth": queue_depth,
            "sku_zone": zone_id,
            "session_seq": seq
        }
    }

def generate_visitor_session(
    transaction_time: datetime,
    categories: list,
    basket_value: float,
    will_purchase: bool = True
):
    """
    Ek visitor ka poora session generate karo
    Transaction se 15-30 min pehle entry
    """
    events = []
    visitor_id = random_visitor_id()
    seq = 0

    # Entry time — transaction se 15-30 min pehle
    minutes_before = random.randint(15, 30)
    entry_time = transaction_time - timedelta(minutes=minutes_before)

    # ── ENTRY ──────────────────────────────────────────────
    seq += 1
    events.append(build_event(
        visitor_id=visitor_id,
        event_type="ENTRY",
        timestamp=entry_time,
        camera_id="CAM_ENTRY_00",
        confidence=random.uniform(0.85, 0.97),
        seq=seq
    ))

    # ── ZONE BROWSING ──────────────────────────────────────
    # Category ke hisaab se zones choose karo
    visited_zones = set()
    for cat in categories:
        zones = CATEGORY_ZONE_MAP.get(cat, BROWSING_ZONES[:2])
        visited_zones.update(random.sample(zones, min(2, len(zones))))

    # 2-4 zones visit karo
    zones_to_visit = list(visited_zones)[:random.randint(2, 4)]
    current_time = entry_time + timedelta(minutes=2)

    for zone in zones_to_visit:
        cam = "CAM_01" if zone in [
            "KOREAN_SKINCARE", "GOOD_VIBES",
            "MINIMALIST", "FRAGRANCE", "NAIL_UNIT"
        ] else "CAM_02"

        # ZONE ENTER
        seq += 1
        events.append(build_event(
            visitor_id=visitor_id,
            event_type="ZONE_ENTER",
            timestamp=current_time,
            camera_id=cam,
            zone_id=zone,
            confidence=random.uniform(0.80, 0.95),
            seq=seq
        ))

        # Dwell time — 1 to 5 minutes
        dwell_minutes = random.randint(1, 5)
        dwell_ms = dwell_minutes * 60 * 1000

        # ZONE DWELL — agar 30 sec se zyada ruka
        if dwell_minutes >= 1:
            seq += 1
            events.append(build_event(
                visitor_id=visitor_id,
                event_type="ZONE_DWELL",
                timestamp=current_time + timedelta(seconds=30),
                camera_id=cam,
                zone_id=zone,
                dwell_ms=30000,
                confidence=random.uniform(0.80, 0.95),
                seq=seq
            ))

        current_time += timedelta(minutes=dwell_minutes)

        # ZONE EXIT
        seq += 1
        events.append(build_event(
            visitor_id=visitor_id,
            event_type="ZONE_EXIT",
            timestamp=current_time,
            camera_id=cam,
            zone_id=zone,
            dwell_ms=dwell_ms,
            confidence=random.uniform(0.80, 0.95),
            seq=seq
        ))

        current_time += timedelta(seconds=30)

    # ── BILLING ────────────────────────────────────────────
    if will_purchase:
        billing_time = transaction_time - timedelta(minutes=3)

        # BILLING QUEUE JOIN
        seq += 1
        queue_depth = random.randint(1, 4)
        events.append(build_event(
            visitor_id=visitor_id,
            event_type="BILLING_QUEUE_JOIN",
            timestamp=billing_time,
            camera_id="CAM_05",
            zone_id="CASH_COUNTER",
            queue_depth=queue_depth,
            confidence=random.uniform(0.85, 0.97),
            seq=seq
        ))

        # ZONE ENTER billing
        seq += 1
        events.append(build_event(
            visitor_id=visitor_id,
            event_type="ZONE_ENTER",
            timestamp=billing_time,
            camera_id="CAM_05",
            zone_id="CASH_COUNTER",
            confidence=random.uniform(0.85, 0.97),
            seq=seq
        ))

        # EXIT after purchase
        seq += 1
        events.append(build_event(
            visitor_id=visitor_id,
            event_type="EXIT",
            timestamp=transaction_time + timedelta(minutes=2),
            camera_id="CAM_ENTRY_00",
            confidence=random.uniform(0.85, 0.97),
            seq=seq
        ))

    else:
        # Visitor jo purchase nahi kiya — seedha exit
        seq += 1
        events.append(build_event(
            visitor_id=visitor_id,
            event_type="EXIT",
            timestamp=current_time + timedelta(minutes=2),
            camera_id="CAM_ENTRY_00",
            confidence=random.uniform(0.75, 0.90),
            seq=seq
        ))

    return events

def emit_events(events: list):
    if not events:
        return
    try:
        response = requests.post(API_URL, json=events, timeout=5)
        result = response.json()
        print(f"  📤 Emitted {len(events)} → accepted:{result.get('accepted')} rejected:{result.get('rejected')}")
    except Exception as e:
        print(f"  ❌ Failed: {e}")

def load_transactions():
    """CSV se transactions load karo"""
    transactions = []
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(row)
    return transactions

def main():
    print("🚀 Synthetic Event Generator")
    print(f"📁 CSV: {CSV_PATH}")
    print(f"🔗 API: {API_URL}\n")

    # API alive check
    try:
        r = requests.get("http://127.0.0.1:8000/health")
        print("✅ API healthy!\n")
    except:
        print("❌ API not running!")
        exit(1)

    # Transactions load karo
    transactions = load_transactions()
    print(f"📊 Total transactions: {len(transactions)}")

    # Unique orders group karo
    orders = {}
    for row in transactions:
        order_id = row.get('order_id') or row.get('Order ID') or row.get('id')
        if order_id not in orders:
            orders[order_id] = {
                'time': row.get('order_time') or row.get('created_at'),
                'date': row.get('order_date'),
                'categories': [],
                'basket': 0
            }
        cat = row.get('dep_name') or row.get('category')
        if cat:
            orders[order_id]['categories'].append(cat)
        try:
            orders[order_id]['basket'] += float(
                row.get('GMV') or row.get('amount') or 0
            )
        except:
            pass

    print(f"📦 Unique orders: {len(orders)}")

    # Date fix karo — aaj ki date use karo
    today = datetime.now(timezone.utc).date()
    print(f"📅 Using date: {today}\n")

    all_events = []
    converted_count = 0
    non_converted_count = 0

    for order_id, order in orders.items():
        # Time parse karo
        try:
            time_str = order['time']
            # Format: HH:MM:SS
            t = datetime.strptime(time_str, "%H:%M:%S")
            transaction_time = datetime(
                today.year, today.month, today.day,
                t.hour, t.minute, t.second,
                tzinfo=timezone.utc
            )
        except Exception as e:
            print(f"⚠️ Time parse error for {order_id}: {e}")
            continue

        # Converted visitor session banao
        events = generate_visitor_session(
            transaction_time=transaction_time,
            categories=order['categories'],
            basket_value=order['basket'],
            will_purchase=True
        )
        all_events.extend(events)
        converted_count += 1

    # Non-converted visitors bhi banao — 40% extra
    non_converted = int(len(orders) * 0.4)
    print(f"👥 Adding {non_converted} non-converted visitors...")

    for i in range(non_converted):
        # Random time during store hours
        hour = random.randint(11, 20)
        minute = random.randint(0, 59)
        random_time = datetime(
            today.year, today.month, today.day,
            hour, minute, 0,
            tzinfo=timezone.utc
        )

        events = generate_visitor_session(
            transaction_time=random_time,
            categories=random.sample(list(CATEGORY_ZONE_MAP.keys()), 2),
            basket_value=0,
            will_purchase=False
        )
        all_events.extend(events)
        non_converted_count += 1

    print(f"\n📊 Summary:")
    print(f"  Converted visitors: {converted_count}")
    print(f"  Non-converted visitors: {non_converted_count}")
    print(f"  Total events: {len(all_events)}")
    print(f"\n📤 Sending to API...\n")

    # Batch mein bhejo
    batch_size = 100
    for i in range(0, len(all_events), batch_size):
        batch = all_events[i:i+batch_size]
        emit_events(batch)

    print(f"\n✅ Done!")
    print(f"📊 Check: http://127.0.0.1:8000/stores/{STORE_ID}/metrics")
    print(f"🔍 Funnel: http://127.0.0.1:8000/stores/{STORE_ID}/funnel")

if __name__ == "__main__":
    main()