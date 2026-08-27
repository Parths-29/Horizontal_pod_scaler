"""
backend/main.py
───────────────────────────────────────────────────────────────────────────────
FastAPI backend — serves the ML model predictions and benchmark results to:
  • The KEDA external scaler (gRPC scaler calls /predict internally)
  • The React frontend dashboard (REST API)

Endpoints:
  GET  /health                  → liveness probe
  POST /predict                 → load prediction from ML model
  GET  /api/forecast            → predicted vs actual time series (for chart)
  GET  /api/benchmark/results   → saved benchmark comparison (HPA vs KEDA)
  GET  /api/metrics/live        → SSE stream of current replica counts

Model loading strategy (interview talking point):
  The model is loaded ONCE at startup from S3 (or local fallback) and cached
  in memory. This avoids per-request S3 latency (~50-200ms) and keeps p99
  latency low for the scaler's hot path. If the model file changes in S3,
  the pod must be restarted (handled by a rolling update in the Helm chart).

CORS is open for local dev; in production, lock it to the ingress hostname.

Usage (local):
    pip install -r backend/requirements.txt
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import AsyncGenerator, List, Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ─── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Horizontal Pod Scaler — Prediction API",
    description="Serves ML-based load predictions and benchmark results for the KEDA external scaler.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to ingress hostname in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Model loading ────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_MODEL_PATH = SCRIPT_DIR.parent / "ml" / "artifacts" / "model.pkl"
LOCAL_META_PATH = SCRIPT_DIR.parent / "ml" / "artifacts" / "metadata.json"

# Global model cache — loaded once at startup
_model = None
_model_meta: dict = {}
_feature_cols: List[str] = []


def _load_model_from_s3() -> object:
    """
    Download latest model from S3 into memory and deserialise.
    First downloads metadata.json to find the latest versioned model key.
    """
    import boto3

    bucket = os.environ["S3_BUCKET"]
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    s3 = boto3.client("s3", region_name=region)

    meta_key = "models/metadata.json"
    try:
        logger.info(f"Fetching metadata from s3://{bucket}/{meta_key} to find latest model...")
        meta_buf = io.BytesIO()
        s3.download_fileobj(bucket, meta_key, meta_buf)
        meta_buf.seek(0)
        s3_meta = json.load(meta_buf)
        key = s3_meta.get("s3_key", "models/model.pkl")
    except Exception as exc:
        logger.warning(f"Failed to fetch metadata.json from S3 ({exc}), falling back to default key")
        key = os.environ.get("S3_MODEL_KEY", "models/model.pkl")

    logger.info(f"Downloading latest model from s3://{bucket}/{key}")
    buf = io.BytesIO()
    s3.download_fileobj(bucket, key, buf)
    buf.seek(0)
    return joblib.load(buf)


def _load_model_local() -> object:
    """Load model from local filesystem (for local dev / tests)."""
    logger.info(f"Loading model from local path: {LOCAL_MODEL_PATH}")
    if not LOCAL_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {LOCAL_MODEL_PATH}. "
            "Run `python ml/train.py` first, or set S3_BUCKET to load from S3."
        )
    return joblib.load(LOCAL_MODEL_PATH)


@app.on_event("startup")
async def load_model() -> None:
    """
    Load model at startup so the first prediction request isn't slow.
    Tries S3 first (production), falls back to local file (dev).
    """
    global _model, _model_meta, _feature_cols

    if os.environ.get("S3_BUCKET"):
        try:
            _model = _load_model_from_s3()
            logger.info("✓ Model loaded from S3")
        except Exception as exc:
            logger.warning(f"S3 load failed ({exc}), trying local fallback …")
            _model = _load_model_local()
    else:
        _model = _load_model_local()

    # Load metadata (feature columns, model type, metrics)
    if LOCAL_META_PATH.exists():
        with open(LOCAL_META_PATH) as f:
            _model_meta = json.load(f)
        _feature_cols = _model_meta.get("feature_cols", [])
        logger.info(f"Model type: {_model_meta.get('model_type', 'unknown')}")
    else:
        logger.warning("metadata.json not found — feature columns may not be set")


# ─── Request / response schemas ───────────────────────────────────────────────

class PredictRequest(BaseModel):
    """
    Input to /predict.

    recent_metrics: last N CPU utilisation readings (1-minute intervals, newest last)
    horizon_minutes: how many minutes into the future to forecast
    """
    recent_metrics: List[float] = Field(
        ...,
        min_items=15,
        description="Recent CPU utilisation readings (%), newest last. Minimum 15 required for lag features.",
    )
    horizon_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Forecast horizon in minutes (1-60)",
    )


class PredictResponse(BaseModel):
    predicted_load: float = Field(..., description="Predicted CPU utilisation (%) at horizon")
    confidence_interval: List[float] = Field(..., description="[lower, upper] 80% CI")
    model_type: str
    horizon_minutes: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_type: Optional[str]


# ─── Feature builder (mirrors feature_engineering.py) ─────────────────────────

def _build_features_from_recent(
    recent_metrics: List[float],
    horizon: int,
    future_dt: pd.Timestamp,
) -> pd.DataFrame:
    """
    Construct the feature vector for a single prediction point.

    We replicate the same feature engineering used during training so that
    the model sees data in exactly the same format. This is a key source of
    training–serving skew bugs in real ML systems — keeping it in one shared
    place (feature_engineering.py) is the production solution.
    """
    metrics = np.array(recent_metrics, dtype=float)

    row = {
        # Calendar features
        "hour": future_dt.hour,
        "day_of_week": future_dt.dayofweek,
        "month": future_dt.month,
        "is_weekend": int(future_dt.dayofweek >= 5),
        "hour_sin": np.sin(2 * np.pi * future_dt.hour / 24),
        "hour_cos": np.cos(2 * np.pi * future_dt.hour / 24),
        "dow_sin": np.sin(2 * np.pi * future_dt.dayofweek / 7),
        "dow_cos": np.cos(2 * np.pi * future_dt.dayofweek / 7),
        # Lag features (index from end of recent_metrics)
        "lag_1": float(metrics[-1]),
        "lag_5": float(metrics[-5]) if len(metrics) >= 5 else float(metrics[0]),
        "lag_15": float(metrics[-15]) if len(metrics) >= 15 else float(metrics[0]),
        # Rolling statistics
        "rolling_mean_5": float(np.mean(metrics[-5:])),
        "rolling_mean_15": float(np.mean(metrics[-15:])),
        "rolling_mean_30": float(np.mean(metrics[-30:])) if len(metrics) >= 30 else float(np.mean(metrics)),
        "rolling_std_5": float(np.std(metrics[-5:])),
        "rolling_std_15": float(np.std(metrics[-15:])),
        "rolling_std_30": float(np.std(metrics[-30:])) if len(metrics) >= 30 else float(np.std(metrics)),
    }

    cols = _feature_cols if _feature_cols else list(row.keys())
    return pd.DataFrame([row])[cols]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe — returns 200 if the model is loaded."""
    return HealthResponse(
        status="ok",
        model_loaded=_model is not None,
        model_type=_model_meta.get("model_type"),
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest) -> PredictResponse:
    """
    Predict future CPU load from recent observations.

    The KEDA external scaler calls this endpoint to decide how many replicas
    to provision. The gRPC scaler translates the returned *predicted_load*
    into a KEDA metric value.

    Confidence interval heuristic:
      We don't have full probabilistic output from XGBoost, so we use
      ±1.5 * rolling standard deviation of recent metrics as a proxy for
      uncertainty. This is a reasonable approximation for a portfolio project;
      in production, use quantile regression or conformal prediction.
    """
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet. Retry in a moment.")

    model_type = _model_meta.get("model_type", "unknown")
    now = pd.Timestamp.utcnow()
    future_dt = now + pd.Timedelta(minutes=req.horizon_minutes)

    if model_type == "XGBoost":
        features = _build_features_from_recent(req.recent_metrics, req.horizon_minutes, future_dt)
        prediction = float(np.clip(_model.predict(features)[0], 0, 100))
    elif model_type == "Prophet":
        future_df = pd.DataFrame({"ds": [future_dt]})
        forecast = _model.predict(future_df)
        prediction = float(np.clip(forecast["yhat"].iloc[0], 0, 100))
    else:
        # Generic sklearn-compatible fallback
        features = _build_features_from_recent(req.recent_metrics, req.horizon_minutes, future_dt)
        prediction = float(np.clip(_model.predict(features)[0], 0, 100))

    # Confidence interval (heuristic ±1.5σ of recent window)
    std = float(np.std(req.recent_metrics[-15:]))
    ci_lower = max(0.0, round(prediction - 1.5 * std, 2))
    ci_upper = min(100.0, round(prediction + 1.5 * std, 2))

    return PredictResponse(
        predicted_load=round(prediction, 2),
        confidence_interval=[ci_lower, ci_upper],
        model_type=model_type,
        horizon_minutes=req.horizon_minutes,
    )


# ── Forecast time series (for frontend chart) ─────────────────────────────────

@app.get("/api/forecast")
async def get_forecast():
    """
    Return a 60-point time series of predicted vs actual CPU load.
    Used by the React dashboard's "Load Forecast" chart.

    In production, this would query Prometheus for actual metrics and the
    model for predictions. Here we return a representative demo dataset.
    """
    now = pd.Timestamp.utcnow().floor("min")
    times = [now + pd.Timedelta(minutes=i - 30) for i in range(60)]

    # Simulate a realistic trace with daily cycle
    t = np.arange(60)
    actual = 30 + 20 * np.sin(2 * np.pi * t / 1440 * 60) + np.random.normal(0, 3, 60)
    predicted = actual + np.random.normal(0, 2, 60)  # model tracks actual closely
    actual = np.clip(actual, 0, 100)
    predicted = np.clip(predicted, 0, 100)

    return {
        "timestamps": [ts.isoformat() for ts in times],
        "actual": [round(float(v), 2) for v in actual],
        "predicted": [round(float(v), 2) for v in predicted],
    }


# ── Benchmark results (for frontend summary cards) ─────────────────────────────

@app.get("/api/benchmark/results")
async def get_benchmark_results():
    """
    Return HPA vs KEDA benchmark comparison.
    Populated by Phase 6 load tests; returns demo data until then.
    """
    results_path = SCRIPT_DIR.parent / "load-tests" / "results.json"
    if results_path.exists():
        with open(results_path) as f:
            return json.load(f)

    # Demo data until real benchmarks are run
    return {
        "hpa": {
            "avg_replicas": 4.2,
            "p99_latency_ms": 487,
            "slo_violations": 23,
            "time_to_scale_s": 45,
            "cost_estimate_usd": 2.84,
        },
        "keda": {
            "avg_replicas": 3.8,
            "p99_latency_ms": 312,
            "slo_violations": 4,
            "time_to_scale_s": 12,
            "cost_estimate_usd": 2.31,
        },
        "improvement": {
            "cost_savings_pct": 18.7,
            "latency_reduction_pct": 35.9,
            "slo_violations_avoided": 19,
            "scale_speed_improvement_x": 3.75,
        },
        "note": "Demo data — run Phase 6 load tests to populate with real results.",
    }


# ── Live metrics SSE stream (for frontend live view) ──────────────────────────

async def _replica_event_generator() -> AsyncGenerator[str, None]:
    """
    Server-Sent Events stream — pushes simulated replica counts every 5 seconds.
    In production, this queries the Kubernetes API for actual replica counts.
    """
    base_hpa = 2
    base_keda = 2
    for _ in range(120):  # stream for up to 10 minutes
        # Simulate gradual load increase
        noise = np.random.randint(-1, 2)
        base_hpa = max(1, min(10, base_hpa + noise))
        base_keda = max(1, min(10, base_keda + (noise - 1)))  # KEDA scales ahead

        data = json.dumps({
            "timestamp": pd.Timestamp.utcnow().isoformat(),
            "hpa_replicas": base_hpa,
            "keda_replicas": base_keda,
        })
        yield f"data: {data}\n\n"
        await asyncio.sleep(5)


@app.get("/api/metrics/live")
async def live_metrics():
    """SSE endpoint — clients connect and receive replica count updates every 5s."""
    return StreamingResponse(
        _replica_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
