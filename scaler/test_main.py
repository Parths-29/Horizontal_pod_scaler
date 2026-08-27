import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Ensure we can import the scaler
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scaler.main import ExternalScaler
from scaler.proto import externalscaler_pb2 as pb

@pytest.fixture
def scaler():
    return ExternalScaler("http://fake-backend:8000")

def test_get_forecast_success(scaler):
    """Test _get_forecast returns the peak CPU from the API response."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "predictions": [
                {"cpu_util": 10.5},
                {"cpu_util": 15.0},
                {"cpu_util": 12.0}
            ]
        }
        mock_get.return_value = mock_response
        
        result = scaler._get_forecast("demo-app")
        assert result == 15.0  # Peak

def test_get_forecast_empty(scaler):
    """Test _get_forecast handles empty predictions."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"predictions": []}
        mock_get.return_value = mock_response
        
        result = scaler._get_forecast("demo-app")
        assert result == 0.0

def test_get_metrics(scaler):
    """Test GetMetrics returns correct protobuf structure."""
    with patch.object(scaler, '_get_forecast', return_value=45.5):
        req = pb.GetMetricsRequest(metricName="cpu")
        resp = scaler.GetMetrics(req, None)
        
        assert len(resp.metricValues) == 1
        assert resp.metricValues[0].metricName == "cpu"
        assert resp.metricValues[0].metricValueFloat == 45.5

def test_is_active(scaler):
    """Test IsActive returns true when forecast > 0."""
    with patch.object(scaler, '_get_forecast', return_value=1.5):
        req = MagicMock()
        req.name = "cpu"
        resp = scaler.IsActive(req, None)
        assert resp.result == True

    with patch.object(scaler, '_get_forecast', return_value=0.0):
        req = MagicMock()
        req.name = "cpu"
        resp = scaler.IsActive(req, None)
        assert resp.result == False
