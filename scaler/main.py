import sys
import os
import time
import logging
import threading
from concurrent import futures
import requests

import grpc

# Add proto directory to path so imports resolve correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'proto')))

import externalscaler_pb2 as pb
import externalscaler_pb2_grpc as pb_grpc

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class ExternalScaler(pb_grpc.ExternalScalerServicer):
    def __init__(self, backend_url: str):
        self.backend_url = backend_url

    def _get_forecast(self, metric_name: str) -> float:
        """Fetch the predicted load from the FastAPI backend."""
        try:
            # We fetch a 5-minute forecast
            response = requests.get(f"{self.backend_url}/api/forecast", params={"horizon_minutes": 5}, timeout=5)
            response.raise_for_status()
            data = response.json()
            predictions = data.get("predictions", [])
            if not predictions:
                logging.warning("No predictions returned from backend.")
                return 0.0
            
            # The forecast returns a list of future steps. We want the peak load
            # over the next 5 minutes to scale proactively.
            peak_cpu = max([p["cpu_util"] for p in predictions])
            return float(peak_cpu)
        except Exception as e:
            logging.error(f"Failed to fetch forecast from backend: {e}")
            return 0.0

    def IsActive(self, request, context):
        """Returns True if scaling is needed."""
        forecast = self._get_forecast(request.name)
        # We consider the scaler active if the predicted CPU is above 0 (always active).
        # We let the target scaling metrics handle the actual pod counts.
        is_active = forecast > 0.0
        logging.info(f"IsActive check: predicted_cpu={forecast:.2f} -> active={is_active}")
        return pb.IsActiveResponse(result=is_active)

    def StreamIsActive(self, request, context):
        """Streams active status."""
        while True:
            yield self.IsActive(request, context)
            time.sleep(15)

    def GetMetricSpec(self, request, context):
        """Returns the metric specification."""
        # We extract target utilization from the KEDA ScaledObject metadata
        target_value = float(request.scalerMetadata.get("targetCpuUtil", "60.0"))
        
        logging.info(f"GetMetricSpec returning targetValueFloat: {target_value}")
        return pb.GetMetricSpecResponse(
            metricSpecs=[
                pb.MetricSpec(
                    metricName=request.name,
                    targetSizeFloat=target_value
                )
            ]
        )

    def GetMetrics(self, request, context):
        """Returns the actual metric value based on ML predictions."""
        forecast = self._get_forecast(request.metricName)
        logging.info(f"GetMetrics for {request.metricName}: returning value={forecast:.2f}")
        return pb.GetMetricsResponse(
            metricValues=[
                pb.MetricValue(
                    metricName=request.metricName,
                    metricValueFloat=forecast
                )
            ]
        )

def serve():
    port = os.environ.get("GRPC_PORT", "50051")
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_ExternalScalerServicer_to_server(ExternalScaler(backend_url), server)
    server.add_insecure_port(f'[::]:{port}')
    
    logging.info(f"Starting KEDA External Scaler (Python) on port {port}")
    logging.info(f"Connecting to ML backend at {backend_url}")
    
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
