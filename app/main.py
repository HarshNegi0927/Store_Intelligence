from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
import logging

from database import create_tables
from ingestion import router as ingest_router
from metrics import router as metrics_router
from funnel import router as funnel_router
from anomalies import router as anomalies_router
from health import router as health_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Store Intelligence API",
    description="Real-time retail analytics from CCTV footage",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())[:8]
    store_id = request.path_params.get("store_id", "-")
    start = time.time()

    response = await call_next(request)

    latency = round((time.time() - start) * 1000, 2)
    logger.info(
        f"trace_id={trace_id} | "
        f"endpoint={request.url.path} | "
        f"store_id={store_id} | "
        f"latency_ms={latency} | "
        f"status={response.status_code}"
    )
    return response


app.include_router(ingest_router)
app.include_router(metrics_router)
app.include_router(funnel_router)
app.include_router(anomalies_router)
app.include_router(health_router)


@app.on_event("startup")
async def startup():
    create_tables()
    logger.info("Database tables created!")
    logger.info("Store Intelligence API started!")


@app.get("/")
def root():
    return {
        "service": "Store Intelligence API",
        "version": "1.0.0",
        "status": "running"
    }