# Engineering Choices — Store Intelligence System

Three key decisions that shaped this system, with full reasoning.

---

## Decision 1 — Detection Model: YOLOv8n

### The Problem
Process CCTV footage to detect people, track movement, and classify entry/exit direction. No GPU available — CPU only deployment on Intel Core i5.

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| YOLOv8n (chosen) | Fast on CPU, excellent tracking, great docs | Less accurate than larger models |
| YOLOv8m/l | More accurate | Too slow on CPU — 2-3x slower |
| MediaPipe | Very fast | Poor tracking, no ByteTrack integration |
| RT-DETR | State of art accuracy | Requires GPU for real-time |
| OpenCV HOG | No model needed | Very poor accuracy, outdated |

### What AI Suggested
Claude suggested using YOLOv8s (small) as a balance between speed and accuracy, and also recommended evaluating RT-DETR for better detection of partially occluded people in crowded billing areas.

### What We Chose and Why
YOLOv8n (nano) — the smallest and fastest variant. On our CPU-only hardware, YOLOv8s was 40% slower with marginal accuracy improvement for retail CCTV use case. The nano model processes frames fast enough for real-time simulation while maintaining acceptable detection quality.

For partial occlusion handling, we set confidence threshold at 0.3 (lower than default 0.5) to catch partially visible people, while logging confidence scores rather than silently dropping low-confidence detections.

### Trade-off Accepted
Detection accuracy is lower than larger models. In production with GPU hardware, YOLOv8l or RT-DETR would be the right choice. This is documented as a known upgrade path.

### If We Were Wrong
If accuracy was unacceptably low on production footage, the first upgrade would be YOLOv8s on GPU. The pipeline architecture is model-agnostic — swapping the model requires changing one line in detect.py.

---

## Decision 2 — Event Schema Design

### The Problem
Design a schema that captures visitor behaviour from multiple cameras, supports all required analytics queries, and remains extensible without breaking changes.

### Options Considered

**Option A — Flat schema (one table, all fields)**
```json
{
  "event_id": "uuid",
  "event_type": "ENTRY",
  "visitor_id": "VIS_abc",
  "zone_id": "SKINCARE",
  "queue_depth": 3
}
```
Simple but queue_depth would be null for 95% of events — wasteful.

**Option B — Typed events (separate table per event type)**
entries_table, zone_events_table, billing_table
Clean but complex joins for analytics queries.

**Option C — Core + metadata envelope (chosen)**
```json
{
  "event_id": "uuid",
  "event_type": "BILLING_QUEUE_JOIN",
  "visitor_id": "VIS_abc",
  "confidence": 0.91,
  "event_metadata": {
    "queue_depth": 3,
    "sku_zone": "MAKEUP",
    "session_seq": 5
  }
}
```

### What AI Suggested
Claude suggested Option C — core fields flat for indexing, optional fields in a JSON metadata envelope. It also suggested adding `session_seq` to track event ordering within a visitor session, which we implemented.

AI also suggested adding a `schema_version` field for future migrations. We agreed this was good practice but deprioritised it for the MVP.

### What We Chose and Why
Option C — core + metadata envelope. This gives us:
- Fast indexed queries on `store_id`, `visitor_id`, `event_type`, `timestamp`
- Flexible metadata without schema migrations for new event types
- Idempotency via `event_id` (UUID v4)
- Pydantic validation on ingest with clear error messages

### Trade-off Accepted
JSON metadata column is not queryable with standard SQL filters. For production, we would either extract frequently-queried metadata fields (like `queue_depth`) into indexed columns, or move to a time-series database like TimescaleDB.

---

## Decision 3 — API Architecture: Single FastAPI Service vs Microservices

### The Problem
Design the API layer that ingests events and serves analytics queries. Should it be one service or multiple?

### Options Considered

**Option A — Microservices**
Ingest Service → Event Bus (Kafka) → Analytics Service
→ Anomaly Service
Scalable, decoupled, production-grade.

**Option B — Single FastAPI service (chosen)**
FastAPI App → SQLite/PostgreSQL
All endpoints in one service
Simple, deployable with one docker compose up.

**Option C — Serverless Functions**
AWS Lambda per endpoint
No server management but cold starts hurt real-time analytics.

### What AI Suggested
Claude strongly recommended microservices for production scalability, specifically:
- Separate ingest service to handle burst traffic from 40 stores
- Kafka/Redis Streams for event buffering
- Read replicas for analytics queries

### What We Chose and Why
Single FastAPI service. This was a deliberate trade-off for the evaluation context:

1. **Acceptance gate** requires `docker compose up` to start everything — microservices adds complexity without adding value at this scale
2. **SQLite** works perfectly for single-store evaluation; the `DATABASE_URL` env var allows zero-code migration to PostgreSQL
3. **Modular code structure** — each endpoint is a separate router (ingestion.py, metrics.py, funnel.py etc.) making the service easy to split into microservices later

### Where AI Was Right
At 40 live stores sending events in real-time, the ingest endpoint would be the first bottleneck. The fix would be:
1. Move to PostgreSQL with connection pooling
2. Add a Redis queue in front of ingest
3. Separate ingest workers from analytics readers

This is the production upgrade path, and we agree with AI's assessment. For the current evaluation scope, the single service is the right choice.

### Trade-off Accepted
Single point of failure. If the service goes down, all analytics stop. In production, this is solved with horizontal scaling behind a load balancer — which the current architecture supports without code changes.

---

## Summary

| Decision | Chosen | Key Reason |
|---|---|---|
| Detection Model | YOLOv8n | CPU-only hardware constraint |
| Event Schema | Core + metadata envelope | Indexed queries + flexible metadata |
| API Architecture | Single FastAPI service | Simplicity + docker compose gate |

All three decisions prioritise the North Star metric: **offline store conversion rate accuracy**. Detection model choice affects measurement accuracy. Schema design affects query correctness. API architecture affects data freshness.