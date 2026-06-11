# 🏪 Store Intelligence System
### Real-time Retail Analytics from CCTV Footage

A complete end-to-end retail analytics platform built for **Purplle's physical stores** — transforms raw CCTV footage into real-time business intelligence.

**North Star Metric:** Offline Store Conversion Rate = Visitors who purchased ÷ Total unique visitors

---

## 🚀 Quick Start (5 commands)

```bash
git clone https://github.com/HarshNegi0927/Store_Intelligence.git
cd Store_Intelligence
docker compose up --build
```

API: http://localhost:8000/docs  
Dashboard: Open `dashboard/index.html` in browser

---

## 📊 What It Does

| Business Question | Answer |
|---|---|
| How many customers visited today? | `/stores/{id}/metrics` → `unique_visitors` |
| How many actually bought? | `/stores/{id}/metrics` → `conversion_rate` |
| Where are we losing customers? | `/stores/{id}/funnel` → drop-off % |
| Which zones get attention but no sales? | `/stores/{id}/heatmap` → dwell vs funnel |
| Is a queue building right now? | `/stores/{id}/anomalies` → `BILLING_QUEUE_SPIKE` |
| Is any camera feed stale? | `/health` → `STALE_FEED` warning |

---

## 🏗️ Architecture

```
📹 Raw CCTV Clips
       │
       ▼
🔍 Detection Layer  (YOLOv8n + ByteTrack)
   • Person detection per frame
   • Entry/Exit via Y-axis movement  
   • Zone classification via X-axis position
   • Staff detection via presence ratio
   • 2-second cooldown deduplication
       │
       ▼
⚡ Event Stream  (Structured JSON)
   ENTRY / EXIT / REENTRY
   ZONE_ENTER / ZONE_EXIT / ZONE_DWELL
   BILLING_QUEUE_JOIN / BILLING_QUEUE_ABANDON
       │
       ▼
🧠 Intelligence API  (FastAPI + PostgreSQL)
   POST /events/ingest     → Idempotent batch ingestion
   GET  /stores/{id}/metrics   → Real-time KPIs
   GET  /stores/{id}/funnel    → Conversion funnel
   GET  /stores/{id}/heatmap   → Zone popularity
   GET  /stores/{id}/anomalies → Operational alerts
   GET  /health            → System status
       │
       ▼
📊 Live Dashboard  (React)
   Real-time metrics updating every 5 seconds
```

---

## 🎥 Running Detection Pipeline

### Option 1 — Real CCTV Videos:
```bash
cd pipeline
pip install ultralytics opencv-python requests supervision
```

Place videos in `data/clips/` folder:
```
data/clips/
├── CAM 1.mp4   # Top wall — Korean skincare brands
├── CAM 2.mp4   # Bottom wall — Makeup brands  
├── CAM 3.mp4   # Entry/Exit threshold
├── CAM 4.mp4   # Warehouse (auto-skipped)
└── CAM 5.mp4   # Billing counter
```

Update path in `pipeline/detect.py`:
```python
VIDEO_DIR = r"path/to/your/videos"
```

Run:
```bash
python pipeline/detect.py
```

### Option 2 — Synthetic Data from POS (Recommended for testing):
```bash
python pipeline/generate_events.py
```
Generates realistic visitor sessions from real POS transaction data.  
**Result: 33 visitors, 72.73% conversion rate, full funnel analytics**

### Option 3 — Purplle Native Event Format:
```bash
python pipeline/converter.py path/to/events.jsonl
```
Converts Purplle's internal event schema to our API format.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/events/ingest` | Batch ingest (up to 500 events), idempotent |
| `GET` | `/stores/{id}/metrics` | Unique visitors, conversion rate, dwell time |
| `GET` | `/stores/{id}/funnel` | Entry → Zone → Billing → Purchase funnel |
| `GET` | `/stores/{id}/heatmap` | Zone popularity scores (0-100) |
| `GET` | `/stores/{id}/anomalies` | Queue spikes, conversion drops, dead zones |
| `GET` | `/health` | Service health + stale feed detection |

---

## 🧠 Tech Stack

| Layer | Technology |
|---|---|
| Detection | YOLOv8n + ByteTrack |
| API | FastAPI + PostgreSQL |
| ORM | SQLAlchemy |
| Validation | Pydantic v2 |
| Dashboard | React (CDN) |
| Container | Docker Compose |
| Testing | Pytest — 82% coverage, 26 tests |

---

## 🧪 Running Tests

```bash
pip install pytest pytest-cov httpx
pytest tests/ -v --cov=app --cov-report=term-missing
```

**Result: 26 passed, 82% coverage**

---

## 📁 Project Structure

```
store-intelligence/
├── pipeline/
│   ├── detect.py          # YOLOv8 detection + tracking
│   ├── tracker.py         # Re-ID / tracking logic
│   ├── emit.py            # Event schema + emission
│   ├── generate_events.py # Synthetic data from POS CSV
│   └── converter.py       # Purplle native schema adapter
├── app/
│   ├── main.py            # FastAPI entrypoint
│   ├── models.py          # Pydantic event schema
│   ├── database.py        # SQLAlchemy + PostgreSQL
│   ├── ingestion.py       # Ingest + deduplication
│   ├── metrics.py         # Real-time KPI computation
│   ├── funnel.py          # Conversion funnel logic
│   ├── anomalies.py       # Anomaly detection engine
│   ├── heatmap.py         # Zone heatmap scoring
│   └── health.py          # Health check endpoint
├── tests/
│   ├── conftest.py
│   ├── test_metrics.py
│   ├── test_anomalies.py
│   └── test_pipeline.py
├── docs/
│   ├── DESIGN.md          # Architecture + AI decisions
│   └── CHOICES.md         # Tech decision rationale
├── dashboard/
│   └── index.html         # Live React dashboard
├── data/
│   └── store_layout.json  # Brigade Road, Bangalore store
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 🔑 Key Engineering Decisions

**Detection:** YOLOv8n chosen for CPU-only compatibility. Confidence threshold 0.3 to handle partial occlusions.

**Zone Classification:** X-axis position mapping (left/center/right per camera) — deterministic, fast, no additional model needed.

**Staff Detection:** Presence ratio heuristic (>60% frames = staff) — works well on longer footage.

**Idempotency:** Event ingestion checks `event_id` before insert — safe to replay pipeline.

**Cross-camera Re-ID:** Known limitation — each camera tracked independently. Future improvement: OSNet appearance-based Re-ID.

---

## 📝 Documentation

- [`DESIGN.md`](docs/DESIGN.md) — Full architecture + AI-assisted decisions
- [`CHOICES.md`](docs/CHOICES.md) — Detection model, schema, API architecture rationale

---

## 👨‍💻 Author

**Harsh Negi** — MNNIT Allahabad  
[GitHub](https://github.com/HarshNegi0927)

---

*Built for Purplle Engineering Hiring Challenge 2026 — Round 2*