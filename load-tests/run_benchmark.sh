#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# load-tests/run_benchmark.sh
# Orchestrates the load testing comparison between baseline HPA and KEDA.
# MUST be run from the Jenkins EC2 instance (or an environment inside the VPC
# with kubectl configured and k6 installed).
# ─────────────────────────────────────────────────────────────────────────────

RESULTS_DIR="results"

# ─── Cleanup Trap ─────────────────────────────────────────────────────────────
cleanup_jobs() {
  if [ -n "$PF_PID" ] && kill -0 "$PF_PID" 2>/dev/null; then
    kill "$PF_PID" 2>/dev/null || true
  fi
  if [ -n "$TRACK_PID" ] && kill -0 "$TRACK_PID" 2>/dev/null; then
    kill "$TRACK_PID" 2>/dev/null || true
  fi
  pkill -f "port-forward.*5000" 2>/dev/null || true
}
trap cleanup_jobs EXIT INT TERM

# ─── Pre-flight System & Cluster Checks ──────────────────────────────────────

check_cluster_connection() {
  echo "[benchmark] Checking Kubernetes cluster connectivity..."
  if ! kubectl get nodes --request-timeout='10s' >/dev/null 2>&1; then
    echo "[ERROR] Cannot reach Kubernetes cluster! Check AWS credentials / kubeconfig."
    exit 1
  fi
  echo "[benchmark] Kubernetes cluster connection OK."
}

check_disk_space() {
  echo "[benchmark] Checking available disk space..."
  mkdir -p "$RESULTS_DIR"
  local free_mb
  free_mb=$(df -m "$RESULTS_DIR" | awk 'NR==2 {print $4}')
  echo "[benchmark] Available disk space: ${free_mb} MB"
  if [ "$free_mb" -lt 2048 ]; then
    echo "[ERROR] Insufficient disk space! Need at least 2048 MB free, found ${free_mb} MB."
    exit 1
  fi
}

prepare_results_dir() {
  mkdir -p "$RESULTS_DIR"
  local json_count
  json_count=$(ls -1 "$RESULTS_DIR"/*.json 2>/dev/null | wc -l)
  if [ "$json_count" -gt 0 ]; then
    local archive_dir="${RESULTS_DIR}/archive_$(date +%Y%m%d_%H%M%S)"
    echo "[benchmark] Prior benchmark outputs found. Archiving to $archive_dir..."
    mkdir -p "$archive_dir"
    mv "$RESULTS_DIR"/*.json "$archive_dir/" 2>/dev/null || true
    mv "$RESULTS_DIR"/*.csv "$archive_dir/" 2>/dev/null || true
  fi
  echo "[benchmark] Results directory is clean and ready for a fresh run."
}

check_metrics_server() {
  echo "[benchmark] Checking for metrics-server deployment in cluster..."
  if ! kubectl get deployment metrics-server -n kube-system >/dev/null 2>&1; then
    echo "[benchmark] metrics-server missing! Installing via official release manifest..."
    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml || true
  fi
  echo "[benchmark] Ensuring metrics-server is rollout ready..."
  kubectl rollout status deployment metrics-server -n kube-system --timeout=60s || true
}

# ─── Autoscaler Lifecycle & Verification Helpers ─────────────────────────────

clean_autoscalers() {
  echo "[benchmark] Cleaning up all existing autoscalers (HPA & ScaledObject)..."
  
  # Delete manifests
  kubectl delete -f ../demo-app/k8s/baseline-hpa.yaml --ignore-not-found 2>/dev/null || true
  kubectl delete -f ../demo-app/k8s/keda-scaledobject.yaml --ignore-not-found 2>/dev/null || true

  # Explicitly delete any residual HPA and ScaledObject resources
  kubectl delete hpa demo-app-hpa-baseline keda-hpa-demo-app-scaledobject --ignore-not-found 2>/dev/null || true
  kubectl delete scaledobject demo-app-scaledobject --ignore-not-found 2>/dev/null || true

  # Wait loop: ensure no HPA remains active targeting demo-app
  echo "[benchmark] Waiting for all HPA resources to be fully terminated..."
  local count=30
  while [ $count -gt 0 ]; do
    local hpa_count
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
  kubectl scale deployment demo-app --replicas=1 2>/dev/null || true
  wait_for_replicas 1

  # Allow metrics and cluster state to settle
  echo "[benchmark] Settle delay (10s)..."
  sleep 10
}

verify_single_hpa() {
  local expected_name=$1
  echo "[benchmark] Verifying active HPA: expected '$expected_name'..."
  local retries=20
  while [ $retries -gt 0 ]; do
    local hpas
    hpas=$(kubectl get hpa -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    local count
    count=$(echo $hpas | wc -w)
    
    if [ "$count" -eq 1 ] && [ "$hpas" == "$expected_name" ]; then
      echo "[benchmark] Verification passed: exactly 1 HPA active ('$expected_name')."
      return 0
    fi
    
    echo "[benchmark] Waiting for HPA state to match '$expected_name' (currently: '$hpas' [count=$count])..."
    sleep 3
    retries=$((retries - 1))
  done

  echo "[ERROR] HPA verification failed! Expected '$expected_name', found: '$hpas'"
  kubectl get hpa
  exit 1
}

wait_for_replicas() {
  local target=$1
  echo "[benchmark] Waiting for demo-app replicas to stabilize at $target..."
  local timeout=90
  while [ $timeout -gt 0 ]; do
    local current
    current=$(kubectl get deploy demo-app -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$current" == "$target" ]; then
      echo "[benchmark] Replicas stabilized at $target."
      return 0
    fi
    sleep 3
    timeout=$((timeout - 3))
  done
  echo "[benchmark] Warning: replicas did not reach target $target within timeout (current: ${current:-0}). Continuing..."
}

# ─── Port-Forward & Test Execution Helpers ────────────────────────────────────

start_port_forward() {
  echo "[benchmark] Establishing port-forward to svc/demo-app-service (5000 -> 80)..."
  pkill -f "port-forward.*5000" 2>/dev/null || true
  sleep 1

  kubectl port-forward svc/demo-app-service 5000:80 > /tmp/k8s_pf.log 2>&1 &
  PF_PID=$!

  local ready=0
  for i in $(seq 1 15); do
    if curl -s -m 2 http://localhost:5000/ >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done

  if [ $ready -ne 1 ]; then
    echo "[ERROR] Port-forward health check failed after 15s! Log:"
    cat /tmp/k8s_pf.log 2>/dev/null || true
    return 1
  fi

  echo "[benchmark] Port-forward confirmed healthy at http://localhost:5000/"
  return 0
}

record_replicas() {
  local output_file=$1
  local duration=$2
  echo "timestamp,replicas" > "$output_file"
  
  local end=$((SECONDS + duration))
  while [ $SECONDS -lt $end ]; do
    local current
    current=$(kubectl get deploy demo-app -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ -z "$current" ]; then current="0"; fi
    echo "$(date +%s),$current" >> "$output_file"

    # Watchdog: ensure port-forward process didn't silently exit
    if ! kill -0 "$PF_PID" 2>/dev/null; then
      echo "[benchmark] Watchdog: port-forward dropped! Re-establishing..."
      kubectl port-forward svc/demo-app-service 5000:80 > /tmp/k8s_pf.log 2>&1 &
      PF_PID=$!
    fi

    sleep 2
  done
}

run_test_suite() {
  local scaler_name=$1
  local script=$2
  local duration=$3

  echo "================================================================="
  echo "[benchmark] Scenario: $script against $scaler_name (duration: ~${duration}s)"
  echo "================================================================="

  # Ensure clean target files
  rm -f "$RESULTS_DIR/${scaler_name}_${script}.json" "$RESULTS_DIR/${scaler_name}_${script}_replicas.csv"

  # Start port-forwarding with health probe
  if ! start_port_forward; then
    echo "[ERROR] Could not establish port-forward for $script! Skipping scenario..."
    return 1
  fi

  # Start replica tracking in background
  record_replicas "$RESULTS_DIR/${scaler_name}_${script}_replicas.csv" "$duration" &
  TRACK_PID=$!

  # Run k6 — handle exit codes gracefully (threshold breaches return 99 and must NOT abort the suite)
  echo "[benchmark] Launching k6 $script.js..."
  k6 run --out json="$RESULTS_DIR/${scaler_name}_${script}.json" "$script.js"
  local k6_exit=$?

  if [ $k6_exit -eq 0 ]; then
    echo "[benchmark] Scenario $script completed successfully (all thresholds passed)."
  elif [ $k6_exit -eq 99 ]; then
    echo "[benchmark] Scenario $script completed with threshold breaches (k6 Exit 99)."
    echo "[benchmark] (Note: Threshold breaches are expected benchmark data under high load — continuing suite.)"
  else
    echo "[benchmark] Scenario $script exited with status $k6_exit. Continuing suite..."
  fi

  # Cleanup background jobs for this scenario
  if [ -n "$TRACK_PID" ]; then kill "$TRACK_PID" 2>/dev/null || true; fi
  if [ -n "$PF_PID" ]; then kill "$PF_PID" 2>/dev/null || true; fi
  pkill -f "port-forward.*5000" 2>/dev/null || true
  sleep 3
}

# ─── Main Execution Workflow ─────────────────────────────────────────────────

cd "$(dirname "$0")"

# Step 0: Pre-flight Verification
check_cluster_connection
check_disk_space
prepare_results_dir
check_metrics_server

# Step 1: Benchmark Phase 1 — Baseline HPA
echo ""
echo "================================================================="
echo "[benchmark] STARTING PHASE 1: BASELINE HPA BENCHMARK"
echo "================================================================="
clean_autoscalers
kubectl apply -f ../demo-app/k8s/baseline-hpa.yaml
verify_single_hpa "demo-app-hpa-baseline"
wait_for_replicas 1

run_test_suite "hpa" "gradual_ramp" 420
run_test_suite "hpa" "sudden_spike" 185
run_test_suite "hpa" "daily_cycle" 600

# Step 2: Benchmark Phase 2 — Predictive KEDA
echo ""
echo "================================================================="
echo "[benchmark] STARTING PHASE 2: PREDICTIVE KEDA BENCHMARK"
echo "================================================================="
clean_autoscalers
kubectl apply -f ../demo-app/k8s/keda-scaledobject.yaml
verify_single_hpa "keda-hpa-demo-app-scaledobject"
wait_for_replicas 1

run_test_suite "keda" "gradual_ramp" 420
run_test_suite "keda" "sudden_spike" 185
run_test_suite "keda" "daily_cycle" 600

# Step 3: Teardown
echo ""
echo "================================================================="
echo "[benchmark] BENCHMARK COMPLETE! CLEANING UP..."
echo "================================================================="
clean_autoscalers
echo "[benchmark] All 6 scenarios completed! Results saved to $RESULTS_DIR/"
