"""
ml/tests/test_feature_engineering.py
───────────────────────────────────────────────────────────────────────────────
Unit tests for the feature engineering pipeline.

Run with: pytest ml/tests/ -v
"""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path
import sys

# Add project root to path so we can import ml.*
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml.feature_engineering import (
    add_calendar_features,
    add_lag_features,
    add_rolling_features,
    build_feature_matrix,
    temporal_split,
    FEATURE_COLS,
    TARGET_COL,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """
    50-row synthetic CPU trace with a DatetimeIndex.
    Values follow a mild upward trend + noise.
    """
    n = 100
    timestamps = pd.date_range("2024-01-01 08:00", periods=n, freq="min")
    cpu = np.linspace(20, 60, n) + np.random.default_rng(0).normal(0, 2, n)
    cpu = np.clip(cpu, 0, 100)
    df = pd.DataFrame({TARGET_COL: cpu}, index=timestamps)
    df.index.name = "timestamp"
    return df


# ─── Calendar features ────────────────────────────────────────────────────────

class TestCalendarFeatures:
    def test_hour_range(self, sample_df):
        out = add_calendar_features(sample_df)
        assert out["hour"].between(0, 23).all(), "hour must be in [0, 23]"

    def test_day_of_week_range(self, sample_df):
        out = add_calendar_features(sample_df)
        assert out["day_of_week"].between(0, 6).all(), "day_of_week must be in [0, 6]"

    def test_circular_encoding_bounds(self, sample_df):
        out = add_calendar_features(sample_df)
        for col in ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]:
            assert out[col].between(-1.0, 1.0).all(), f"{col} must be in [-1, 1]"

    def test_is_weekend_binary(self, sample_df):
        out = add_calendar_features(sample_df)
        assert set(out["is_weekend"].unique()).issubset({0, 1}), "is_weekend must be 0 or 1"

    def test_no_new_nans(self, sample_df):
        out = add_calendar_features(sample_df)
        assert not out[["hour", "day_of_week", "hour_sin", "hour_cos"]].isna().any().any()


# ─── Lag features ─────────────────────────────────────────────────────────────

class TestLagFeatures:
    def test_lag_1_matches_shift(self, sample_df):
        out = add_lag_features(sample_df)
        expected = sample_df[TARGET_COL].shift(1)
        pd.testing.assert_series_equal(out["lag_1"], expected, check_names=False)

    def test_lag_creates_nans_at_start(self, sample_df):
        out = add_lag_features(sample_df, lags=[5])
        assert out["lag_5"].isna().sum() == 5, "lag_5 should have 5 NaN rows at start"

    def test_custom_lags(self, sample_df):
        out = add_lag_features(sample_df, lags=[2, 10])
        assert "lag_2" in out.columns
        assert "lag_10" in out.columns


# ─── Rolling features ─────────────────────────────────────────────────────────

class TestRollingFeatures:
    def test_rolling_mean_columns_exist(self, sample_df):
        out = add_rolling_features(sample_df, windows=[5, 15])
        assert "rolling_mean_5" in out.columns
        assert "rolling_mean_15" in out.columns

    def test_rolling_mean_within_cpu_range(self, sample_df):
        out = add_rolling_features(sample_df)
        for col in ["rolling_mean_5", "rolling_mean_15", "rolling_mean_30"]:
            assert out[col].dropna().between(0, 100).all(), f"{col} out of CPU range"

    def test_rolling_std_non_negative(self, sample_df):
        out = add_rolling_features(sample_df)
        for col in ["rolling_std_5", "rolling_std_15"]:
            assert (out[col].dropna() >= 0).all(), f"{col} must be ≥ 0"


# ─── Full feature matrix ──────────────────────────────────────────────────────

class TestBuildFeatureMatrix:
    def test_output_has_all_feature_cols(self, sample_df):
        out = build_feature_matrix(sample_df)
        for col in FEATURE_COLS:
            assert col in out.columns, f"Missing feature column: {col}"

    def test_no_nans_after_build(self, sample_df):
        out = build_feature_matrix(sample_df)
        assert not out[FEATURE_COLS].isna().any().any(), "Feature matrix contains NaNs"

    def test_target_col_present(self, sample_df):
        out = build_feature_matrix(sample_df)
        assert TARGET_COL in out.columns


# ─── Temporal split ───────────────────────────────────────────────────────────

class TestTemporalSplit:
    def test_split_sizes(self, sample_df):
        feat = build_feature_matrix(sample_df)
        train, val, test = temporal_split(feat, ratios=(0.7, 0.15, 0.15))
        n = len(feat)
        # Allow ±1 row for rounding
        assert abs(len(train) - int(n * 0.7)) <= 1
        assert len(train) + len(val) + len(test) == n

    def test_chronological_order(self, sample_df):
        feat = build_feature_matrix(sample_df)
        train, val, test = temporal_split(feat)
        assert train.index.max() < val.index.min(), "Train/val boundary violated"
        assert val.index.max() < test.index.min(), "Val/test boundary violated"

    def test_no_data_leakage(self, sample_df):
        """Ensure no timestamps appear in both train and test."""
        feat = build_feature_matrix(sample_df)
        train, val, test = temporal_split(feat)
        assert len(train.index.intersection(test.index)) == 0, "Data leakage: train ∩ test is non-empty"
