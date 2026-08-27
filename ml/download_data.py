"""
ml/download_data.py
───────────────────────────────────────────────────────────────────────────────
Downloads a workload-trace CSV used for training the predictive scaler.

Data source: Alibaba 2018 cluster-trace CPU-utilization (machine-level)
  - Hosted on GitHub as a representative subset for reproducibility.
  - Fallback: synthetic dataset generated via numpy so the training pipeline
    always works without network access.

Usage:
    python ml/download_data.py [--synthetic]

Outputs:
    ml/data/raw_trace.csv  — header: timestamp,cpu_util
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

# We serve a hosted 50k-row sample of the Alibaba cluster trace (CPU util %).
# The raw dataset is at https://github.com/alibaba/clusterdata — this sample
# is a representative 1-week subset extracted from machine_usage.csv.
PRIMARY_URL = (
    "https://raw.githubusercontent.com/Parths-29/Horizontal_pod_scaler/"
    "main/ml/data/raw_trace_sample.csv"
)

# Known SHA-256 of the hosted file (update after first successful download)
EXPECTED_SHA256 = ""  # left empty; will warn but not fail if not set

OUTPUT_FILE = DATA_DIR / "raw_trace.csv"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def sha256_of_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file (for reproducibility checks)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_with_progress(url: str, dest: Path) -> bool:
    """
    Stream-download *url* to *dest*, showing a tqdm progress bar.
    Returns True on success, False on HTTP error.
    """
    print(f"[download] Fetching: {url}")
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[download] ERROR: {exc}", file=sys.stderr)
        return False

    total = int(resp.headers.get("Content-Length", 0)) or None
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as f, tqdm(
        desc=dest.name,
        total=total,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))

    return True


# ─── Synthetic fallback ───────────────────────────────────────────────────────

def generate_synthetic_trace(n_rows: int = 50_000, seed: int = 42) -> pd.DataFrame:
    """
    Generate a realistic synthetic CPU-utilisation trace.

    Design:
      - Base sinusoidal daily cycle  (peak at midday, trough at night)
      - Superimposed weekly seasonality (workdays higher than weekends)
      - Gaussian noise + occasional traffic spikes
      - Values clipped to [0, 100] to represent CPU %

    This gives the ML models a signal they can actually learn from,
    even when the real dataset is unavailable.
    """
    rng = np.random.default_rng(seed)

    # One sample per minute, starting 2024-01-01
    timestamps = pd.date_range("2024-01-01", periods=n_rows, freq="min")
    t = np.arange(n_rows)

    # ── Daily cycle: peak around t=720 (noon), period = 1440 min ──────────────
    daily = 35 + 25 * np.sin(2 * np.pi * t / 1440 - np.pi / 2)

    # ── Weekly cycle: weekdays ~10% higher ────────────────────────────────────
    weekday = timestamps.dayofweek.values  # Mon=0 … Sun=6
    weekly_boost = np.where(weekday < 5, 8.0, -5.0)  # workday vs weekend

    # ── Gaussian noise ────────────────────────────────────────────────────────
    noise = rng.normal(0, 4, n_rows)

    # ── Occasional spikes (sudden load bursts, ~0.3% of minutes) ─────────────
    spike_mask = rng.random(n_rows) < 0.003
    spikes = spike_mask * rng.uniform(20, 45, n_rows)

    cpu_util = daily + weekly_boost + noise + spikes
    cpu_util = np.clip(cpu_util, 0, 100)

    return pd.DataFrame({"timestamp": timestamps, "cpu_util": cpu_util.round(2)})


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download or generate ML training data")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Skip download, generate synthetic trace instead (no network needed)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=50_000,
        help="Number of rows for synthetic dataset (default: 50000)",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.synthetic:
        print(f"[data] Generating synthetic trace ({args.rows:,} rows) …")
        df = generate_synthetic_trace(n_rows=args.rows)
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"[data] Saved → {OUTPUT_FILE}")
    else:
        success = download_with_progress(PRIMARY_URL, OUTPUT_FILE)

        if not success:
            print(
                "[data] Primary download failed. Falling back to synthetic dataset …",
                file=sys.stderr,
            )
            df = generate_synthetic_trace(n_rows=args.rows)
            df.to_csv(OUTPUT_FILE, index=False)
            print(f"[data] Saved (synthetic fallback) → {OUTPUT_FILE}")

    # ── Integrity check ───────────────────────────────────────────────────────
    digest = sha256_of_file(OUTPUT_FILE)
    print(f"\n[integrity] SHA-256: {digest}")
    if EXPECTED_SHA256 and digest != EXPECTED_SHA256:
        print(
            f"[integrity] WARNING: checksum mismatch!\n"
            f"  Expected: {EXPECTED_SHA256}\n"
            f"  Got:      {digest}",
            file=sys.stderr,
        )
    else:
        print("[integrity] ✓ Checksum verified (or no expected hash set)")

    # ── Quick sanity check ────────────────────────────────────────────────────
    df_check = pd.read_csv(OUTPUT_FILE, nrows=5)
    print(f"\n[sanity] Columns  : {list(df_check.columns)}")
    print(f"[sanity] First 5 rows:\n{df_check.to_string(index=False)}")
    total_rows = sum(1 for _ in open(OUTPUT_FILE)) - 1  # subtract header
    print(f"[sanity] Total rows: {total_rows:,}")


if __name__ == "__main__":
    main()
