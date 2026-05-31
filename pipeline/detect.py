import cv2
import uuid
import requests
from datetime import datetime, timezone
from pathlib import Path
from ultralytics import YOLO

# ─── Config ───────────────────────────────────────────────
STORE_ID = "STORE_BLR_001"
API_URL = "http://127.0.0.1:8000/events/ingest"
VIDEO_DIR = r"C:\Users\himansu\OneDrive\Desktop\PurplleVideos\CCTV Footage"

CAMERA_MAP = {
    "CAM 1.mp4": "CAM_01",
    "CAM 2.mp4": "CAM_02",
    "CAM 3.mp4": "CAM_ENTRY_00",
    "CAM 4.mp4": "CAM_04",
    "CAM 5.mp4": "CAM_05",
}

ZONE_MAP = {
    "CAM_01": {
        "left":   "KOREAN_SKINCARE",
        "center": "GOOD_VIBES",
        "right":  "MINIMALIST"
    },
    "CAM_02": {
        "left":   "ALPS",
        "center": "LAKME",
        "right":  "MAYBELLINE"
    },
    "CAM_05": {
        "left":   "CASH_COUNTER",
        "center": "CASH_COUNTER",
        "right":  "ACCESSORIES"
    },
    "CAM_04": {
        "left":   "WAREHOUSE",
        "center": "WAREHOUSE",
        "right":  "WAREHOUSE"
    }
}

# ─── Load Model ───────────────────────────────────────────
print("🔄 Loading YOLOv8 model...")
model = YOLO("yolov8n.pt")
print("✅ Model loaded!")

# ─── Global Tracking ──────────────────────────────────────
visitor_registry = {}
session_seq = {}
active_frames = {}
exited_visitors = set()

def get_visitor_id(track_id: int, camera_id: str) -> str:
    key = f"{camera_id}_{track_id}"
    if key not in visitor_registry:
        visitor_registry[key] = f"VIS_{uuid.uuid4().hex[:6]}"
        session_seq[visitor_registry[key]] = 0
        active_frames[key] = 0
    return visitor_registry[key]

def get_next_seq(visitor_id: str) -> int:
    session_seq[visitor_id] = session_seq.get(visitor_id, 0) + 1
    return session_seq[visitor_id]

def increment_frames(track_id: int, camera_id: str):
    key = f"{camera_id}_{track_id}"
    active_frames[key] = active_frames.get(key, 0) + 1

def get_presence_ratio(track_id: int, camera_id: str, total_frames: int) -> float:
    key = f"{camera_id}_{track_id}"
    return active_frames.get(key, 0) / max(total_frames, 1)

def get_zone(camera_id: str, center_x: float, frame_width: float) -> str:
    if camera_id not in ZONE_MAP:
        return None
    zones = ZONE_MAP[camera_id]
    ratio = center_x / frame_width
    if ratio < 0.33:
        return zones["left"]
    elif ratio < 0.66:
        return zones["center"]
    else:
        return zones["right"]

def detect_direction(prev_y: float, curr_y: float) -> str:
    threshold = 15
    if curr_y < prev_y - threshold:
        return "ENTRY"
    elif curr_y > prev_y + threshold:
        return "EXIT"
    return None

def build_event(
    camera_id, visitor_id, event_type,
    timestamp, zone_id=None, dwell_ms=0,
    staff=False, confidence=0.9,
    queue_depth=None, seq=1
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": STORE_ID,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": staff,
        "confidence": round(confidence, 2),
        "event_metadata": {
            "queue_depth": queue_depth,
            "sku_zone": zone_id,
            "session_seq": seq
        }
    }

def emit_events(events: list):
    if not events:
        return
    try:
        response = requests.post(API_URL, json=events, timeout=5)
        result = response.json()
        print(f"  📤 Emitted {len(events)} → accepted:{result.get('accepted')} rejected:{result.get('rejected')}")
    except Exception as e:
        print(f"  ❌ Emit failed: {e}")

def process_video(video_path: str, camera_id: str):
    print(f"\n{'='*50}")
    print(f"🎥 Camera: {camera_id}")
    print(f"{'='*50}")

    if camera_id == "CAM_04":
        print("⚠️  Warehouse — skipping!")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Cannot open: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"📊 FPS:{fps:.1f} | Frames:{total_frames}")

    frame_count = 0
    events_batch = []
    is_entry_cam = camera_id == "CAM_ENTRY_00"

    # Aaj ki date — dynamic
    clip_start = datetime.now(timezone.utc).replace(
        hour=14, minute=0, second=0, microsecond=0
    )

    prev_positions = {}
    zone_entry_times = {}
    zone_current = {}
    billing_visitors = set()
    last_dwell_emit = {}
    last_event_frame = {}  # ← Cooldown tracking

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % 5 != 0:
            continue

        frame_time = clip_start.timestamp() + (frame_count / fps)
        timestamp = datetime.fromtimestamp(
            frame_time, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        results = model.track(
            frame,
            persist=True,
            classes=[0],
            verbose=False,
            conf=0.3
        )

        if results[0].boxes is None:
            continue

        current_track_ids = set()

        for box in results[0].boxes:
            if box.id is None:
                continue

            track_id = int(box.id.item())
            confidence = float(box.conf.item())
            current_track_ids.add(track_id)

            visitor_id = get_visitor_id(track_id, camera_id)
            increment_frames(track_id, camera_id)

            staff = get_presence_ratio(
                track_id, camera_id, frame_count
            ) > 0.6

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            center_y = (y1 + y2) / 2
            center_x = (x1 + x2) / 2

            # ── Entry Camera ───────────────────────────────
            if is_entry_cam:
                if track_id in prev_positions:
                    direction = detect_direction(
                        prev_positions[track_id], center_y
                    )
                    if direction:
                        # 2 second cooldown check ← NEW
                        frames_since = frame_count - last_event_frame.get(track_id, 0)
                        cooldown = fps * 2

                        if frames_since >= cooldown:
                            last_event_frame[track_id] = frame_count

                            if direction == "ENTRY" and visitor_id in exited_visitors:
                                event_type = "REENTRY"
                                exited_visitors.discard(visitor_id)
                            else:
                                event_type = direction

                            if direction == "EXIT":
                                exited_visitors.add(visitor_id)

                            events_batch.append(build_event(
                                camera_id=camera_id,
                                visitor_id=visitor_id,
                                event_type=event_type,
                                timestamp=timestamp,
                                staff=staff,
                                confidence=confidence,
                                seq=get_next_seq(visitor_id)
                            ))

                prev_positions[track_id] = center_y

            # ── Floor / Billing Camera ─────────────────────
            else:
                current_zone = get_zone(camera_id, center_x, frame_width)

                if zone_current.get(track_id) != current_zone:

                    # Zone exit
                    if track_id in zone_current and zone_current[track_id]:
                        old_zone = zone_current[track_id]
                        frames_in = frame_count - zone_entry_times.get(track_id, frame_count)
                        dwell_ms = int((frames_in / fps) * 1000)

                        events_batch.append(build_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="ZONE_EXIT",
                            timestamp=timestamp,
                            zone_id=old_zone,
                            dwell_ms=dwell_ms,
                            staff=staff,
                            confidence=confidence,
                            seq=get_next_seq(visitor_id)
                        ))

                        # Billing abandon
                        if old_zone == "CASH_COUNTER" and visitor_id in billing_visitors:
                            billing_visitors.discard(visitor_id)
                            events_batch.append(build_event(
                                camera_id=camera_id,
                                visitor_id=visitor_id,
                                event_type="BILLING_QUEUE_ABANDON",
                                timestamp=timestamp,
                                zone_id="CASH_COUNTER",
                                staff=staff,
                                confidence=confidence,
                                seq=get_next_seq(visitor_id)
                            ))

                    # Zone enter
                    zone_current[track_id] = current_zone
                    zone_entry_times[track_id] = frame_count
                    last_dwell_emit[track_id] = frame_count

                    events_batch.append(build_event(
                        camera_id=camera_id,
                        visitor_id=visitor_id,
                        event_type="ZONE_ENTER",
                        timestamp=timestamp,
                        zone_id=current_zone,
                        staff=staff,
                        confidence=confidence,
                        seq=get_next_seq(visitor_id)
                    ))

                    # Billing queue join
                    if current_zone == "CASH_COUNTER":
                        billing_visitors.add(visitor_id)
                        if len(billing_visitors) > 1:
                            events_batch.append(build_event(
                                camera_id=camera_id,
                                visitor_id=visitor_id,
                                event_type="BILLING_QUEUE_JOIN",
                                timestamp=timestamp,
                                zone_id="CASH_COUNTER",
                                staff=staff,
                                confidence=confidence,
                                queue_depth=len(billing_visitors),
                                seq=get_next_seq(visitor_id)
                            ))

                # Zone dwell — har 30 sec
                else:
                    frames_since = frame_count - last_dwell_emit.get(track_id, frame_count)
                    if (frames_since / fps) >= 30:
                        frames_in = frame_count - zone_entry_times.get(track_id, frame_count)
                        dwell_ms = int((frames_in / fps) * 1000)
                        events_batch.append(build_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="ZONE_DWELL",
                            timestamp=timestamp,
                            zone_id=zone_current[track_id],
                            dwell_ms=dwell_ms,
                            staff=staff,
                            confidence=confidence,
                            seq=get_next_seq(visitor_id)
                        ))
                        last_dwell_emit[track_id] = frame_count

        # Track gone — zone exit
        for track_id in list(zone_current.keys()):
            if track_id not in current_track_ids:
                visitor_id = get_visitor_id(track_id, camera_id)
                old_zone = zone_current[track_id]
                frames_in = frame_count - zone_entry_times.get(track_id, frame_count)
                dwell_ms = int((frames_in / fps) * 1000)

                events_batch.append(build_event(
                    camera_id=camera_id,
                    visitor_id=visitor_id,
                    event_type="ZONE_EXIT",
                    timestamp=timestamp,
                    zone_id=old_zone,
                    dwell_ms=dwell_ms,
                    staff=get_presence_ratio(track_id, camera_id, frame_count) > 0.6,
                    confidence=0.7,
                    seq=get_next_seq(visitor_id)
                ))
                del zone_current[track_id]

        if len(events_batch) >= 10:
            emit_events(events_batch)
            events_batch = []

    if events_batch:
        emit_events(events_batch)

    cap.release()
    print(f"✅ {camera_id} done! | Frames: {frame_count}")

if __name__ == "__main__":
    video_dir = Path(VIDEO_DIR)

    print("🚀 Store Intelligence — Detection Pipeline")
    print(f"📁 {VIDEO_DIR}")
    print(f"🏪 {STORE_ID}\n")

    try:
        r = requests.get("http://127.0.0.1:8000/health")
        print("✅ API healthy!\n")
    except:
        print("❌ API not running! Start uvicorn first!")
        exit(1)

    for video_file, camera_id in CAMERA_MAP.items():
        video_path = video_dir / video_file
        if video_path.exists():
            process_video(str(video_path), camera_id)
        else:
            print(f"⚠️  Not found: {video_file} — skipping")

    print("\n" + "="*50)
    print("✅ Pipeline Complete!")
    print(f"📊 Metrics: http://127.0.0.1:8000/stores/{STORE_ID}/metrics")
    print(f"🔍 Funnel:  http://127.0.0.1:8000/stores/{STORE_ID}/funnel")
    print("="*50)