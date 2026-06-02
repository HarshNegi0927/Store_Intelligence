10:49 am
Le bhai docs/DESIGN.md:

markdown
# Store Intelligence System — Design Document

## 1. System Overview

Store Intelligence is an end-to-end retail analytics platform that transforms raw CCTV footage into real-time business metrics. The system bridges the analytics gap between Purplle's mature online channel and its physical stores.

**North Star Metric:** Offline Store Conversion Rate
Conversion Rate = Visitors who purchased ÷ Total unique visitors


---

## 2. Architecture
📹 Raw CCTV Clips
│
▼
🔍 Detection Layer (pipeline/detect.py)
YOLOv8n + ByteTrack
• Person detection per frame
• Entry/Exit via Y-axis movement
• Zone classification via X-axis position
• Staff detection via presence ratio
• Cooldown-based deduplication
│
▼
⚡ Event Stream (pipeline/emit.py)
Structured JSONL events
• ENTRY / EXIT / REENTRY
• ZONE_ENTER / ZONE_EXIT / ZONE_DWELL
• BILLING_QUEUE_JOIN / BILLING_QUEUE_ABANDON
│
▼
🧠 Intelligence API (app/)
FastAPI + SQLite
• POST /events/ingest — idempotent ingestion
• GET /stores/{id}/metrics — real-time KPIs
• GET /stores/{id}/funnel — conversion funnel
• GET /stores/{id}/heatmap — zone popularity
• GET /stores/{id}/anomalies — operational alerts
• GET /health — system status
│
▼
📊 Synthetic Data Layer (pipeline/generate_events.py)
POS CSV correlation
• Real transaction timestamps
• Realistic visitor sessions
• 40% non-converted visitors


---

## 3. Component Decisions

### Detection Model — YOLOv8n
YOLOv8 nano chosen for CPU compatibility. The system runs on standard retail hardware without GPU. Confidence threshold set at 0.3 to capture partial occlusions while flagging low-confidence detections rather than dropping them.

### Tracking Strategy
Per-camera tracking using YOLOv8's built-in ByteTrack. Each camera maintains its own track registry. Cross-camera Re-ID was evaluated but not implemented due to complexity — this is documented as a known limitation and future improvement opportunity.

### Zone Classification
Rather than a complex computer vision zone classifier, zones are determined by X-axis position within each camera frame. Frame width is divided into three equal sections (left/center/right), each mapped to a store zone from `store_layout.json`. This approach is deterministic, explainable, and requires no additional model.

### Staff Detection
Staff are identified by presence ratio — if a person appears in more than 60% of processed frames, they are classified as staff. This works well for longer video clips where staff movement patterns differ from customers. For the 2-minute test clips, this threshold was noted as a limitation.

### Entry/Exit Detection
Y-axis movement of bounding box center determines direction. A 2-second cooldown prevents the same person from generating multiple ENTRY/EXIT events due to natural body movement near the threshold. Threshold of 15 pixels filters minor jitter.

### POS Correlation
A visitor in the CASH_COUNTER zone within 5 minutes before a POS transaction timestamp is counted as a converted visitor. This window was chosen based on typical retail checkout time observations.

---

## 4. Data Architecture

### Event Schema Design
Events follow a flat schema with a nested `event_metadata` object for optional fields. This allows:
- Schema validation via Pydantic
- Idempotency via `event_id` (UUID v4)
- Flexible metadata without breaking the core schema

### Storage
SQLite chosen for development and evaluation. The `DATABASE_URL` environment variable allows zero-code migration to PostgreSQL for production. Indexed columns: `store_id`, `visitor_id`, `event_type`, `timestamp`.

### Idempotency
`POST /events/ingest` checks for existing `event_id` before inserting. Duplicate events are accepted (HTTP 200) but not stored. This makes the pipeline safe to replay.

---

## 5. Known Limitations

### Cross-Camera Re-ID
The same physical person gets different `visitor_id` values across cameras. This means funnel metrics use per-camera counts rather than unified visitor journeys. A production system would use appearance-based Re-ID (OSNet/torchreid) to unify identities.

### Short Clip Detection
The provided 2-minute clips were insufficient for meaningful detection analytics. Staff detection, entry counting, and dwell time measurement all improve significantly with longer footage. The system was validated using synthetic events generated from real POS transaction data.

### Conversion Rate Calculation
Due to cross-camera Re-ID limitation, conversion rate is calculated as:
Billing visitors (CAM_05) ÷ Entry footfall (CAM_ENTRY_00)

Rather than true session-level conversion. This is noted in API responses.

---

## 6. AI-Assisted Decisions

### Decision 1 — Zone Classification Approach
**What AI suggested:** Use a Vision Language Model (GPT-4V or Claude Vision) to classify which zone a person is standing in by analyzing the frame content and matching against store layout.

**What we chose:** Rule-based X-axis position mapping.

**Why we overrode:** VLM inference per frame would be too slow for real-time processing on CPU hardware, and would add API cost per frame. The X-axis approach is deterministic, fast, and explainable. For a production system with GPU, VLM zone classification would be worth exploring.

---

### Decision 2 — Staff Detection Strategy
**What AI suggested:** Train a custom classifier on staff uniforms using few-shot learning, or use CLIP embeddings to match against a reference image of staff uniform.

**What we chose:** Presence ratio heuristic (>60% frames = staff).

**Why we partially agreed:** The uniform-based approach is more accurate but requires labelled training data we don't have. The presence ratio approach works well for longer clips and requires zero training data. We agreed with AI that a production system should use appearance-based classification, and documented this as a future improvement.

---

### Decision 3 — Synthetic Data Generation
**What AI suggested:** Use the real POS transaction CSV to generate realistic visitor sessions for API validation, since 2-minute clips are insufficient for meaningful analytics.

**What we chose:** Implemented exactly as suggested.

**Why we agreed:** This is standard practice in data engineering — synthetic data generation for testing and validation. The approach uses real transaction timestamps and categories, making the generated sessions realistic. We documented this decision transparently in CHOICES.md.

---

## 7. Production Considerations

### Scalability
At 40 live stores with real-time feeds, the current SQLite + single FastAPI instance would bottleneck at ingestion. Production path:
- PostgreSQL with connection pooling
- Separate ingest workers (Celery/Redis)
- Time-series partitioning on `timestamp`

### Observability
Every API request logs: `trace_id`, `endpoint`, `store_id`, `latency_ms`, `status_code`. The `/health` endpoint monitors feed staleness per store with `STALE_FEED` warnings for feeds silent >10 minutes.

### Graceful Degradation
Database unavailability returns HTTP 503 with structured error body. No raw stack traces are exposed in API responses. Partial batch failures return per-event error details without failing the entire batch.