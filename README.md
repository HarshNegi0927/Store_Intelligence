# 🏪 Store Intelligence System

A complete **retail analytics platform** that transforms raw CCTV footage into real-time store intelligence — from people detection to live business metrics.

---

## 🎯 What This Does

Apex Retail operates 40 physical stores with zero offline analytics. This system bridges that gap:

| Business Question | Where It's Answered |
|---|---|
| How many customers visited today? | `/stores/{id}/metrics` → `unique_visitors` |
| How many actually bought something? | `/stores/{id}/metrics` → `conversion_rate` |
| Where are we losing customers? | `/stores/{id}/funnel` → drop-off % |
| Which zones get attention but no sales? | `/stores/{id}/heatmap` → dwell vs funnel |
| Is a queue building right now? | `/stores/{id}/anomalies` → `BILLING_QUEUE_SPIKE` |
| Is any camera feed stale? | `/health` → `STALE_FEED` warning |

---

## 🏗️ System Architecture

```
📹 Raw CCTV Clips
       │
       ▼
🔍 Detection Layer        (YOLOv8 + ByteTrack)
   • People detection
   • Entry / Exit tracking
   • Zone classification
   • Staff exclusion
   • Re-ID across cameras
       │
       ▼
⚡ Event Stream            (Structured JSONL)
   • ENTRY / EXIT events
   • ZONE_ENTER / ZONE_EXIT / ZONE_DWELL
   • BILLING_QUEUE_JOIN / ABANDON
   • REENTRY detection
       │
       ▼
🧠 Intelligence API        (FastAPI + PostgreSQL)
   • Real-time metric computation
   • Conversion funnel tracking
   • Anomaly detection
   • POS correlation
       │
       ▼
📊 Live Dashboard          (React)
   • Real-time visitor count
   • Live conversion rate
   • Queue depth monitor
   • Zone heatmap
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+

### 1. Clone the repo
```bash
git clone https://github.com/HarshNegi0927/Store_Intelligence.git
cd Store_Intelligence
```

### 2. Start the API
```bash
docker compose up --build
```

### 3. Run detection pipeline on clips
```bash
cd pipeline
pip install -r requirements.txt
python run.sh --input ../data/clips/ --store STORE_BLR_002
```

### 4. Open the dashboard
```
http://localhost:3000
```

### 5. Check API health
```
http://localhost:8000/health
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/events/ingest` | Ingest batch of detection events (up to 500) |
| `GET` | `/stores/{id}/metrics` | Real-time KPIs — visitors, conversion, dwell |
| `GET` | `/stores/{id}/funnel` | Conversion funnel with drop-off % |
| `GET` | `/stores/{id}/heatmap` | Zone visit frequency + avg dwell (0–100) |
| `GET` | `/stores/{id}/anomalies` | Active anomalies with severity + suggested action |
| `GET` | `/health` | Service status + stale feed detection |

---

## 📁 Project Structure

```
store-intelligence/
├── pipeline/
│   ├── detect.py          # YOLOv8 detection + tracking
│   ├── tracker.py         # Re-ID / ByteTrack logic
│   ├── emit.py            # Event schema + emission
│   └── run.sh             # One command to process all clips
├── app/
│   ├── main.py            # FastAPI entrypoint
│   ├── models.py          # Pydantic event schema
│   ├── ingestion.py       # Ingest + deduplication
│   ├── metrics.py         # Real-time metric computation
│   ├── funnel.py          # Funnel + session logic
│   ├── anomalies.py       # Anomaly detection engine
│   └── health.py          # Health check endpoint
├── tests/
│   ├── test_pipeline.py
│   ├── test_metrics.py
│   └── test_anomalies.py
├── docs/
│   ├── DESIGN.md          # Architecture + AI-assisted decisions
│   └── CHOICES.md         # Tech decision rationale
├── dashboard/             # React live dashboard
├── data/                  # CCTV clips + store layouts
├── docker-compose.yml
└── README.md
```

---

## 🧠 Tech Stack

| Layer | Technology |
|---|---|
| Detection | YOLOv8 + ByteTrack |
| Re-ID | OSNet / Bounding Box Trajectory |
| API | FastAPI (Python) |
| Database | PostgreSQL |
| Dashboard | React |
| Container | Docker Compose |
| Testing | Pytest (>70% coverage) |

---

## 📊 Key Features

- **Real-time people detection** — YOLOv8 on 1080p 15fps CCTV footage
- **Person Re-ID** — same visitor tracked across multiple cameras
- **Staff exclusion** — uniform detection excludes staff from customer metrics
- **Re-entry handling** — same person returning counted correctly
- **POS correlation** — visitor sessions correlated with transactions by time window
- **Anomaly detection** — queue spikes, conversion drops, dead zones
- **Idempotent ingestion** — safe to replay events without double counting
- **Graceful degradation** — structured errors, no raw stack traces

---

## 🧪 Running Tests

```bash
cd tests
pytest --cov=app --cov-report=term-missing
```

---

## 📝 Documentation

- [`DESIGN.md`](docs/DESIGN.md) — Full architecture overview + AI-assisted decisions
- [`CHOICES.md`](docs/CHOICES.md) — Detection model, schema, and API design rationale

---

## 👨‍💻 Author

**Harsh Negi**  
[GitHub](https://github.com/HarshNegi0927)

---

*Built as part of Purplle Engineering Hiring Challenge 2026*
