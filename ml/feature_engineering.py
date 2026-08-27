"""
ml/feature_engineering.py
───────────────────────────────────────────────────────────────────────────────
Transforms raw CPU-utilisation trace into a feature matrix ready for XGBoost
and a Prophet-compatible DataFrame.

Interview talking point:
  Time-series forecasting requires *temporal* features that encode seasonality
  (hour-of-day, day-of-week) and autocorrelation (lags, rolling averages).
  Without these, a model can't distinguish "this is a Monday morning ramp-up"
  from "this is a random spike".

Input:
    ml/data/raw_trace.csv  — columns: timestamp, cpu_util

Outputs (returned as tuple):
    X_train, X_val, X_test   — feature DataFrames for XGBoost
    y_train, y_val, y_test   — target Series
    prophet_df               — DataFrame with 'ds' and 'y' columns (for Prophet)

Split ratio: 70 / 15 / 15
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DATA_PATH = SCRIPT_DIR / "data" / "raw_trace.csv"

# ─── Constants ────────────────────────────────────────────────────────────────
SPLIT_RATIOS = (0.70, 0.15, 0.15)  # train / val / test
TARGET_COL = "cpu_util"


# ─── Core feature engineering ─────────────────────────────────────────────────

def load_and_parse(path: Path = RAW_DATA_PATH) -> pd.DataFrame:
    """
    Load the raw trace CSV, parse timestamps, sort chronologically.

    The output has a DatetimeIndex and a single numeric column 'cpu_util'.
    """
    print(f"[feature_engineering] Loading: {path}")
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.set_index("timestamp")

    # Drop exact duplicate timestamps (can occur in real cluster traces)
    df = df[~df.index.duplicated(keep="first")]

    # Forward-fill short gaps (up to 5 consecutive minutes)
    df = df.resample("min").mean()
    df[TARGET_COL] = df[TARGET_COL].fillna(method="ffill", limit=5)
    df = df.dropna(subset=[TARGET_COL])

    print(f"[feature_engineering] Loaded {len(df):,} rows  "
          f"({df.index.min()} → {df.index.max()})")
    return df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Encode temporal context so models can learn seasonality.

    Features added:
      hour          — 0-23 (daily cycle)
      day_of_week   — 0=Monday … 6=Sunday (weekly cycle)
      month         — 1-12 (monthly seasonality, if data spans months)
      is_weekend    — binary flag (0/1)
      hour_sin/cos  — circular encoding of hour (avoids 0 vs 23 discontinuity)
      dow_sin/cos   — circular encoding of day-of-week
    """
    df = df.copy()
    idx = df.index

    df["hour"] = idx.hour.astype(np.int8)
    df["day_of_week"] = idx.dayofweek.astype(np.int8)
    df["month"] = idx.month.astype(np.int8)
    df["is_weekend"] = (idx.dayofweek >= 5).astype(np.int8)

    # Circular (sin/cos) encoding prevents models treating hour 23 as far from 0
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

    return df


def add_lag_features(df: pd.DataFrame, lags: list[int] = [1, 5, 15]) -> pd.DataFrame:
    """
    Autocorrelation features — value at t-k predicts value at t.

    lags=[1, 5, 15] captures:
      - 1 min ago  → very recent trend
      - 5 min ago  → short-term pattern
      - 15 min ago → medium-term trend
    """
    df = df.copy()
    for lag in lags:
        df[f"lag_{lag}"] = df[TARGET_COL].shift(lag)
    return df


def add_rolling_features(
    df: pd.DataFrame,
    windows: list[int] = [5, 15, 30],
) -> pd.DataFrame:
    """
    Rolling statistics smooth noise and capture trend direction.

    Windows (in minutes):
      5  → very short-term average (reduces noise)
      15 → medium-term trend
      30 → long-term baseline
    """
    df = df.copy()
    for w in windows:
        df[f"rolling_mean_{w}"] = (
            df[TARGET_COL].shift(1).rolling(window=w, min_periods=1).mean()
        )
        df[f"rolling_std_{w}"] = (
            df[TARGET_COL].shift(1).rolling(window=w, min_periods=1).std().fillna(0)
        )
    return df


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all feature transformations in order, then drop NaN rows
    created by lag/rolling operations.
    """
    df = add_calendar_features(df)
    df = add_lag_features(df)
    df = add_rolling_features(df)
    df = df.dropna()  # drop early rows where lags/rolling don't have enough history
    return df


# ─── Train / val / test split ─────────────────────────────────────────────────

def temporal_split(
    df: pd.DataFrame,
    ratios: tuple[float, float, float] = SPLIT_RATIOS,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split chronologically — never shuffle time series data.

    Shuffling would leak future information into training and inflate metrics.
    Temporal split mirrors real-world deployment: train on past, predict future.
    """
    n = len(df)
    train_end = int(n * ratios[0])
    val_end = train_end + int(n * ratios[1])

    train = df.iloc[:train_end]
    val = df.iloc[train_end:val_end]
    test = df.iloc[val_end:]

    print(
        f"[feature_engineering] Split Date Ranges:\n"
        f"  Train: {train.index.min()} → {train.index.max()} ({len(train):,} rows)\n"
        f"  Val:   {val.index.min()} → {val.index.max()} ({len(val):,} rows)\n"
        f"  Test:  {test.index.min()} → {test.index.max()} ({len(test):,} rows)"
    )
    return train, val, test


# ─── Public API ───────────────────────────────────────────────────────────────

# Features used by XGBoost (excludes the target column)
FEATURE_COLS = [
    "hour", "day_of_week", "month", "is_weekend",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "lag_1", "lag_5", "lag_15",
    "rolling_mean_5", "rolling_mean_15", "rolling_mean_30",
    "rolling_std_5", "rolling_std_15", "rolling_std_30",
]


def get_train_val_test(
    path: Path = RAW_DATA_PATH,
) -> Tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame,  # X splits
    pd.Series, pd.Series, pd.Series,           # y splits
    pd.DataFrame,                              # prophet_df
]:
    """
    Full pipeline: load → engineer → split.

    Returns:
        X_train, X_val, X_test  — feature matrices (pd.DataFrame)
        y_train, y_val, y_test  — target vectors (pd.Series)
        prophet_df              — {ds, y} DataFrame for Prophet (on train+val)
    """
    raw = load_and_parse(path)
    feat = build_feature_matrix(raw)

    train, val, test = temporal_split(feat)

    X_train, y_train = train[FEATURE_COLS], train[TARGET_COL]
    X_val,   y_val   = val[FEATURE_COLS],   val[TARGET_COL]
    X_test,  y_test  = test[FEATURE_COLS],  test[TARGET_COL]

    # Prophet needs the full train+val range for cross-validation
    prophet_df = feat[[TARGET_COL]].iloc[: len(train) + len(val)].copy()
    prophet_df = prophet_df.reset_index().rename(
        columns={"timestamp": "ds", TARGET_COL: "y"}
    )

    return X_train, X_val, X_test, y_train, y_val, y_test, prophet_df


# ─── CLI for quick inspection ──────────────────────────────────────────────────

if __name__ == "__main__":
    X_tr, X_v, X_te, y_tr, y_v, y_te, p_df = get_train_val_test()
    print("\n[feature_engineering] Feature matrix preview:")
    print(X_tr.describe().round(2).to_string())
    print(f"\n[feature_engineering] Prophet df shape: {p_df.shape}")
    print(p_df.head())
