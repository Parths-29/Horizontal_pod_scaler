# ML Pipeline

This directory contains the full ML pipeline for the predictive scaler:

| File | Purpose |
|------|---------|
| `download_data.py` | Downloads Alibaba/Zenodo cluster traces into `data/` |
| `feature_engineering.py` | Builds time-series features (lags, rolling averages) |
| `train.py` | Trains Prophet + XGBoost, evaluates both, saves best model |
| `upload_model.py` | Uploads trained model artifact to S3 |
| `predict_service.py` | Lightweight FastAPI dev server for the predict endpoint |
| `results.md` | Model evaluation results (MAE, RMSE, MAPE) |
| `tests/` | Unit tests for feature engineering and model output shape |

## Data

Raw data is **not committed to git** (size/licensing reasons). Run `download_data.py` to fetch it.
Model artifacts in `artifacts/` are also gitignored — they live in S3.
