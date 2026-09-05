#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# load-tests/run_benchmark.sh
# Orchestrates the load testing comparison between baseline HPA and KEDA.
# MUST be run from the Jenkins EC2 instance (or an environment inside the VPC
# with kubectl configured and k6 installed).
# ─────────────────────────────────────────────────────────────────────────────

set -e

RESULTS_DIR="results"
mkdir -p $RESULTS_DIR

# ─── Helper Functions ────────────────────────────────────────────────────────

wait_for_replicas() {
  local target=$1
  echo "[benchmark] Waiting for demo-app replicas to stabilize at $target..."
  while true; do
    current=$(kubectl get deploy demo-app -o jsonpath='{.status.readyReplicas}')
    if [[ "$current" == "$target" ]]; then
      echo "[benchmark] Replicas stabilized at $target."
      break
    fi
    sleep 5
  done
}

record_replicas() {
  local output_file=$1
  local duration=$2
  echo "timestamp,replicas" > "$output_file"
  
  local end=$((SECONDS + duration))
  while [ $SECONDS -lt $end ]; do
    current=$(kubectl get deploy demo-app -o jsonpath='{.status.readyReplicas}' || echo "0")
    if [[ -z "$current" ]]; then current="0"; fi
    echo "$(date +%s),$current" >> "$output_file"
    sleep 2
  done
}

run_test_suite() {
  local scaler_name=$1
  local script=$2
  local duration=$3

  echo "================================================================="
  echo "Running $script against $scaler_name..."
  echo "================================================================="

  # Start port-forwarding to the demo-app service in the background
  kubectl port-forward svc/demo-app-service 5000:80 > /dev/null 2>&1 &
  PF_PID=$!
  sleep 2 # wait for port-forward to establish

  # Start replica tracking in the background
  record_replicas "$RESULTS_DIR/${scaler_name}_${script}_replicas.csv" $duration &
  TRACK_PID=$!

  # Run k6
  k6 run --out json="$RESULTS_DIR/${scaler_name}_${script}.json" "$script.js"

  # Cleanup background jobs
  kill $PF_PID || true
  kill $TRACK_PID || true
  sleep 2
}

# ─── Main Execution ──────────────────────────────────────────────────────────

cd "$(dirname "$0")"

# 1. Test Baseline HPA
echo "[benchmark] Deploying Baseline HPA..."
kubectl delete -f ../demo-app/k8s/keda-scaledobject.yaml --ignore-not-found
kubectl apply -f ../demo-app/k8s/baseline-hpa.yaml
wait_for_replicas 1

# Note: The durations here should match the total stages duration in the k6 scripts
run_test_suite "hpa" "gradual_ramp" 420
run_test_suite "hpa" "sudden_spike" 185
run_test_suite "hpa" "daily_cycle" 600

# 2. Test Predictive KEDA
echo "[benchmark] Swapping to Predictive KEDA..."
kubectl delete -f ../demo-app/k8s/baseline-hpa.yaml --ignore-not-found
kubectl apply -f ../demo-app/k8s/keda-scaledobject.yaml
wait_for_replicas 1

run_test_suite "keda" "gradual_ramp" 420
run_test_suite "keda" "sudden_spike" 185
run_test_suite "keda" "daily_cycle" 600

echo "[benchmark] Tests complete! Results saved to $RESULTS_DIR/"
