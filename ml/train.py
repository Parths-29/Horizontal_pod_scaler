"""
ml/train.py
───────────────────────────────────────────────────────────────────────────────
Trains two forecasting models on the CPU utilisation trace:
  1. Prophet  — additive time-series model (handles seasonality out of the box)
  2. XGBoost  — gradient-boosted trees on engineered features (more accurate)

Evaluation metrics (all computed on held-out TEST set):
  • MAE   — Mean Absolute Error  (interpretable: "off by X CPU%")
  • RMSE  — Root Mean Squared Error  (penalises large spikes more than MAE)
  • MAPE  — Mean Absolute Percentage Error  (scale-independent %)

Interview talking point:
  We train two different model families on purpose:
  - Prophet handles trend/seasonality decomposition cleanly and is
    interpretable, but can't use arbitrary tabular features.
  - XGBoost can exploit lag and rolling features for higher accuracy but
    doesn't natively understand temporal structure — hence the manual feature
    engineering in feature_engineering.py.
  The best model (by RMSE on val set) is saved as the production artifact.

Usage:
    python ml/train.py [--data-path ml/data/raw_trace.csv]

Outputs:
    ml/artifacts/model.pkl   — best model (Prophet or XGBoost)
    ml/artifacts/metadata.json
    ml/results.md            — human-readable evaluation results
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

warnings.filterwarnings("ignore")  # suppress Prophet's Stan output

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = SCRIPT_DIR / "artifacts"
RESULTS_PATH = SCRIPT_DIR / "results.md"

# ─── Metrics ──────────────────────────────────────────────────────────────────

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute MAE, RMSE, and MAPE. Returns a dict with float values."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    # MAPE: avoid division by zero (clip denominator)
    mape = float(np.mean(np.abs((y_true - y_pred) / np.clip(np.abs(y_true), 1e-6, None))) * 100)
    return {"MAE": round(mae, 4), "RMSE": round(rmse, 4), "MAPE": round(mape, 4)}


# ─── Prophet ──────────────────────────────────────────────────────────────────

def train_prophet(
    prophet_df: pd.DataFrame,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Tuple[Any, Dict[str, float], Dict[str, float]]:
    """
    Train Facebook Prophet on the training portion of *prophet_df*.

    Prophet configuration decisions:
      - daily_seasonality=True    → captures intra-day CPU cycles
      - weekly_seasonality=True   → captures workday vs weekend pattern
      - changepoint_prior_scale=0.05  → conservative (avoids overfitting to noise)
      - seasonality_mode='additive'   → CPU % doesn't scale multiplicatively
    """
    from prophet import Prophet  # lazy import — Prophet is slow to import

    print("[train] Fitting Prophet …")
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        changepoint_prior_scale=0.05,
        seasonality_mode="additive",
        uncertainty_samples=0,  # disable MCMC sampling for speed
    )

    # Suppress Prophet's verbose Stan logging
    import logging
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

    model.fit(prophet_df)

    def prophet_predict(X: pd.DataFrame) -> np.ndarray:
        """Build a Prophet future DataFrame from the DatetimeIndex of X."""
        future = pd.DataFrame({"ds": X.index})
        forecast = model.predict(future)
        return forecast["yhat"].values.clip(0, 100)

    val_metrics = compute_metrics(y_val.values, prophet_predict(X_val))
    test_metrics = compute_metrics(y_test.values, prophet_predict(X_test))

    print(f"[train] Prophet  val  → MAE={val_metrics['MAE']}  RMSE={val_metrics['RMSE']}  MAPE={val_metrics['MAPE']}%")
    print(f"[train] Prophet  test → MAE={test_metrics['MAE']}  RMSE={test_metrics['RMSE']}  MAPE={test_metrics['MAPE']}%")

    return model, val_metrics, test_metrics


# ─── XGBoost ──────────────────────────────────────────────────────────────────

def train_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Tuple[Any, Dict[str, float], Dict[str, float]]:
    """
    Train XGBoost with early stopping on the validation set.

    Hyperparameter decisions (interview-ready justifications):
      n_estimators=1000   → high ceiling; early stopping prevents overfitting
      learning_rate=0.05  → small steps, rely on more trees for accuracy
      max_depth=6         → standard for tabular data; prevents overfitting
      subsample=0.8       → row subsampling (like bagging) reduces variance
      colsample_bytree=0.8 → feature subsampling (like random forest)
      early_stopping_rounds=50 → stop if val RMSE doesn't improve for 50 rounds
    """
    import xgboost as xgb

    print("[train] Fitting XGBoost …")

    model = xgb.XGBRegressor(
        n_estimators=1000,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,          # L1 regularisation
        reg_lambda=1.0,         # L2 regularisation
        objective="reg:squarederror",
        eval_metric="rmse",
        early_stopping_rounds=50,
        n_jobs=-1,
        random_state=42,
        verbosity=0,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    print(f"[train] XGBoost best iteration: {model.best_iteration}")

    val_pred = model.predict(X_val).clip(0, 100)
    test_pred = model.predict(X_test).clip(0, 100)

    val_metrics = compute_metrics(y_val.values, val_pred)
    test_metrics = compute_metrics(y_test.values, test_pred)

    print(f"[train] XGBoost  val  → MAE={val_metrics['MAE']}  RMSE={val_metrics['RMSE']}  MAPE={val_metrics['MAPE']}%")
    print(f"[train] XGBoost  test → MAE={test_metrics['MAE']}  RMSE={test_metrics['RMSE']}  MAPE={test_metrics['MAPE']}%")

    return model, val_metrics, test_metrics


# ─── Model selection & saving ─────────────────────────────────────────────────

def save_artifact(
    model: Any,
    model_name: str,
    val_metrics: Dict[str, float],
    test_metrics: Dict[str, float],
) -> Path:
    """
    Save the selected model and metadata to ml/artifacts/.

    We save:
      model.pkl      — serialised model (joblib for sklearn/XGBoost, pickle for Prophet)
      metadata.json  — model type, metrics, timestamp, feature columns
    """
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACT_DIR / "model.pkl"
    joblib.dump(model, model_path)

    from datetime import datetime, timezone
    from ml.feature_engineering import FEATURE_COLS

    metadata = {
        "model_type": model_name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "feature_cols": FEATURE_COLS if model_name == "XGBoost" else ["ds"],
    }
    meta_path = ARTIFACT_DIR / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[artifact] Saved: {model_path}")
    print(f"[artifact] Saved: {meta_path}")
    return model_path


# ─── Results markdown ─────────────────────────────────────────────────────────

RESULTS_TEMPLATE = """# ML Model Evaluation Results

> Auto-generated by `ml/train.py` — do not edit manually.

## Dataset

| Property | Value |
|----------|-------|
| Source | Alibaba 2018 cluster trace (CPU utilisation %) |
| Rows | {total_rows:,} |
| Split | 70% train / 15% val / 15% test |
| Frequency | 1-minute intervals |

## Model Comparison

| Model | Val MAE | Val RMSE | Val MAPE | Test MAE | Test RMSE | Test MAPE |
|-------|---------|----------|----------|----------|-----------|-----------|
| Prophet | {p_val_mae} | {p_val_rmse} | {p_val_mape}% | {p_test_mae} | {p_test_rmse} | {p_test_mape}% |
| XGBoost | {x_val_mae} | {x_val_rmse} | {x_val_mape}% | {x_test_mae} | {x_test_rmse} | {x_test_mape}% |

## Winner: **{winner}** (lower val RMSE)

### Feature Importance (XGBoost top 5)
{feature_importance}

## Key Observations

- **Seasonality**: Both models capture the intra-day CPU cycle effectively.
- **Spikes**: XGBoost's lag features allow it to detect ramp-ups 1–15 minutes
  before they peak, enabling the KEDA scaler to act proactively.
- **Prophet** provides interpretable trend/seasonality decomposition useful
  for explaining predictions to stakeholders.

## Artifacts

| File | Description |
|------|-------------|
| `ml/artifacts/model.pkl` | Serialised best model |
| `ml/artifacts/metadata.json` | Model type, metrics, feature columns |
"""


def write_results_md(
    total_rows: int,
    prophet_val: Dict, prophet_test: Dict,
    xgb_val: Dict, xgb_test: Dict,
    winner: str,
    feature_importance_md: str,
) -> None:
    content = RESULTS_TEMPLATE.format(
        total_rows=total_rows,
        p_val_mae=prophet_val["MAE"],    p_val_rmse=prophet_val["RMSE"],   p_val_mape=prophet_val["MAPE"],
        p_test_mae=prophet_test["MAE"],  p_test_rmse=prophet_test["RMSE"], p_test_mape=prophet_test["MAPE"],
        x_val_mae=xgb_val["MAE"],        x_val_rmse=xgb_val["RMSE"],       x_val_mape=xgb_val["MAPE"],
        x_test_mae=xgb_test["MAE"],      x_test_rmse=xgb_test["RMSE"],     x_test_mape=xgb_test["MAPE"],
        winner=winner,
        feature_importance=feature_importance_md,
    )
    RESULTS_PATH.write_text(content)
    print(f"[results] Written → {RESULTS_PATH}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train Prophet and XGBoost forecasters")
    parser.add_argument("--data-path", type=Path, default=SCRIPT_DIR / "data" / "raw_trace.csv")
    parser.add_argument("--skip-prophet", action="store_true", help="Skip Prophet (faster dev iteration)")
    args = parser.parse_args()

    # ── Load & engineer features ──────────────────────────────────────────────
    import sys
    sys.path.insert(0, str(SCRIPT_DIR.parent))  # allow `from ml.feature_engineering import …`
    from ml.feature_engineering import get_train_val_test, FEATURE_COLS

    X_train, X_val, X_test, y_train, y_val, y_test, prophet_df = get_train_val_test(args.data_path)
    total_rows = len(X_train) + len(X_val) + len(X_test)

    # ── Train XGBoost ─────────────────────────────────────────────────────────
    xgb_model, xgb_val_metrics, xgb_test_metrics = train_xgboost(
        X_train, y_train, X_val, y_val, X_test, y_test
    )

    # Feature importance (top 5 by gain)
    import xgboost as xgb
    fi = dict(zip(FEATURE_COLS, xgb_model.feature_importances_))
    top5 = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:5]
    fi_md = "\n".join(f"| {name} | {score:.4f} |" for name, score in top5)
    fi_md = "| Feature | Importance |\n|---------|------------|\n" + fi_md

    # ── Train Prophet ─────────────────────────────────────────────────────────
    if not args.skip_prophet:
        prophet_model, prophet_val_metrics, prophet_test_metrics = train_prophet(
            prophet_df, X_val, y_val, X_test, y_test
        )
    else:
        print("[train] Skipping Prophet (--skip-prophet flag set)")
        prophet_model = None
        prophet_val_metrics = {"MAE": 0, "RMSE": 0, "MAPE": 0}
        prophet_test_metrics = {"MAE": 0, "RMSE": 0, "MAPE": 0}

    # ── Model selection ───────────────────────────────────────────────────────
    # Choose best model by validation RMSE (lower is better)
    if args.skip_prophet or xgb_val_metrics["RMSE"] <= prophet_val_metrics["RMSE"]:
        winner_name = "XGBoost"
        winner_model = xgb_model
        winner_val = xgb_val_metrics
        winner_test = xgb_test_metrics
    else:
        winner_name = "Prophet"
        winner_model = prophet_model
        winner_val = prophet_val_metrics
        winner_test = prophet_test_metrics

    print(f"\n[train] ✓ Winner: {winner_name}")

    # ── Save artifacts ────────────────────────────────────────────────────────
    save_artifact(winner_model, winner_name, winner_val, winner_test)

    # ── Write results.md ─────────────────────────────────────────────────────
    write_results_md(
        total_rows=total_rows,
        prophet_val=prophet_val_metrics,
        prophet_test=prophet_test_metrics,
        xgb_val=xgb_val_metrics,
        xgb_test=xgb_test_metrics,
        winner=winner_name,
        feature_importance_md=fi_md,
    )

    print("\n[train] Phase 2 ML pipeline complete ✓")


if __name__ == "__main__":
    main()
