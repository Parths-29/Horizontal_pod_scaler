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

# ─── Verification & Teardown Helpers ─────────────────────────────────────────

check_metrics_server() {
  echo "[benchmark] Checking for metrics-server deployment in cluster..."
  if ! kubectl get deployment metrics-server -n kube-system >/dev/null 2>&1; then
    echo "[benchmark] metrics-server missing! Installing via official release manifest..."
    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
  fi
  echo "[benchmark] Waiting for metrics-server to be ready..."
  kubectl rollout status deployment metrics-server -n kube-system --timeout=60s || true
}

clean_autoscalers() {
  echo "[benchmark] Cleaning up all existing autoscalers (HPA & ScaledObject)..."
  
  # Delete manifests
  kubectl delete -f ../demo-app/k8s/baseline-hpa.yaml --ignore-not-found
  kubectl delete -f ../demo-app/k8s/keda-scaledobject.yaml --ignore-not-found

  # Explicitly delete any residual HPA and ScaledObject resources
  kubectl delete hpa demo-app-hpa-baseline keda-hpa-demo-app-scaledobject --ignore-not-found
  kubectl delete scaledobject demo-app-scaledobject --ignore-not-found

  # Wait loop: ensure no HPA remains active targeting demo-app
  echo "[benchmark] Waiting for all HPA resources to be fully terminated..."
  local count=30
  while [ $count -gt 0 ]; do
    hpa_count=$(kubectl get hpa -o jsonpath='{len(.items)}' 2>/dev/null || echo "0")
    if [ "$hpa_count" -eq 0 ]; then
      echo "[benchmark] All HPA resources terminated."
      break
    fi
    sleep 2
    count=$((count - 1))
  done

  # Reset deployment to 1 replica and wait for stabilization
  echo "[benchmark] Resetting demo-app to baseline 1 replica..."
  kubectl scale deployment demo-app --replicas=1
  wait_for_replicas 1

  # Allow metrics and cluster state to settle
  echo "[benchmark] Settle delay (10s)..."
  sleep 10
}

verify_single_hpa() {
  local expected_name=$1
  echo "[benchmark] Verifying active HPA: expected '$expected_name'..."
  local retries=15
  while [ $retries -gt 0 ]; do
    local hpas=$(kubectl get hpa -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    local count=$(echo $hpas | wc -w)
    
    if [ "$count" -eq 1 ] && [ "$hpas" == "$expected_name" ]; then
      echo "[benchmark] Verification passed: exactly 1 HPA active ('$expected_name')."
      return 0
    fi
    
    echo "[benchmark] Waiting for HPA state to match '$expected_name' (currently: '$hpas' [count=$count])..."
    sleep 3
    retries=$((retries - 1))
  done

  echo "[ERROR] HPA verification failed! Expected '$expected_name', found: '$hpas'"
  exit 1
}

wait_for_replicas() {
  local target=$1
  echo "[benchmark] Waiting for demo-app replicas to stabilize at $target..."
  while true; do
    current=$(kubectl get deploy demo-app -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [[ "$current" == "$target" ]]; then
      echo "[benchmark] Replicas stabilized at $target."
      break
    fi
    sleep 3
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

# 0. Ensure Cluster Prerequisites
check_metrics_server

# 1. Test Baseline HPA
echo "[benchmark] Setting up Phase 1: Baseline HPA..."
clean_autoscalers
kubectl apply -f ../demo-app/k8s/baseline-hpa.yaml
verify_single_hpa "demo-app-hpa-baseline"
wait_for_replicas 1

run_test_suite "hpa" "gradual_ramp" 420
run_test_suite "hpa" "sudden_spike" 185
run_test_suite "hpa" "daily_cycle" 600

# 2. Test Predictive KEDA
echo "[benchmark] Setting up Phase 2: Predictive KEDA..."
clean_autoscalers
kubectl apply -f ../demo-app/k8s/keda-scaledobject.yaml
verify_single_hpa "keda-hpa-demo-app-scaledobject"
wait_for_replicas 1

run_test_suite "keda" "gradual_ramp" 420
run_test_suite "keda" "sudden_spike" 185
run_test_suite "keda" "daily_cycle" 600

# 3. Teardown & Clean Restoration
echo "[benchmark] Benchmark complete! Cleaning up autoscalers..."
clean_autoscalers
echo "[benchmark] Tests complete! Results saved to $RESULTS_DIR/"
