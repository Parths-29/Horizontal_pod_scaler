import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feature_engineering import add_calendar_features, add_lag_features, temporal_split, TARGET_COL

@pytest.fixture
def sample_df():
    """Generates a dummy 100-row dataframe with hourly timestamps."""
    timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(100)]
    df = pd.DataFrame({
        TARGET_COL: np.random.uniform(10, 50, size=100)
    }, index=pd.DatetimeIndex(timestamps, name="timestamp"))
    return df

def test_add_calendar_features(sample_df):
    """Test that calendar features correctly extract datetime components."""
    df_feat = add_calendar_features(sample_df)
    
    # Check hour mapping
    assert "hour" in df_feat.columns
    assert df_feat["hour"].iloc[0] == 0  # 2024-01-01 00:00:00
    assert df_feat["hour"].iloc[12] == 12
    
    # Check cyclical encoding bounds
    assert df_feat["hour_sin"].max() <= 1.0
    assert df_feat["hour_sin"].min() >= -1.0

def test_add_lag_features(sample_df):
    """Test that lag features correctly shift the target column."""
    df_feat = add_lag_features(sample_df, lags=[1, 5])
    
    assert "lag_1" in df_feat.columns
    assert "lag_5" in df_feat.columns
    
    # Row 0 shouldn't have previous history
    assert pd.isna(df_feat["lag_1"].iloc[0])
    assert pd.isna(df_feat["lag_5"].iloc[4])
    
    # Row 5 should have lag_5 equal to target of row 0
    assert df_feat["lag_5"].iloc[5] == sample_df[TARGET_COL].iloc[0]

def test_temporal_split(sample_df):
    """Verify that temporal_split maintains chronological order (no random shuffling)."""
    train, val, test = temporal_split(sample_df, ratios=(0.7, 0.15, 0.15))
    
    assert len(train) == 70
    assert len(val) == 15
    assert len(test) == 15
    
    # Verify strict chronological order
    assert train.index.max() < val.index.min()
    assert val.index.max() < test.index.min()
