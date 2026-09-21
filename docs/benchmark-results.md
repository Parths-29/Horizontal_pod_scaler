# Phase 6: Autoscaling Benchmark Results

> ⚠️ **Note:** These metrics were captured by running k6 load tests from within the AWS VPC (Jenkins EC2) to eliminate internet latency jitter.

## Scenario: Gradual Ramp

| Metric | Baseline (HPA) | Predictive (KEDA) |
|--------|----------------|-------------------|
| Total Requests | 25799 | 25799 |
| **Failed Requests** | None | **1** |
| P50 Latency (ms) | 3.76 | 3.58 |
| P95 Latency (ms) | 13.86 | **12.55** |
| P99 Latency (ms) | 107.54 | 95.47 |
| Max Replicas | 1 | 1 |
| Avg Replicas | 1.0 | 1.0 |

## Scenario: Sudden Spike

| Metric | Baseline (HPA) | Predictive (KEDA) |
|--------|----------------|-------------------|
| Total Requests | 34758 | 34682 |
| **Failed Requests** | None | **None** |
| P50 Latency (ms) | 3.41 | 3.84 |
| P95 Latency (ms) | 14.61 | **18.76** |
| P99 Latency (ms) | 209.13 | 429.25 |
| Max Replicas | 1 | 1 |
| Avg Replicas | 1.0 | 1.0 |

## Scenario: Daily Cycle

| Metric | Baseline (HPA) | Predictive (KEDA) |
|--------|----------------|-------------------|
| Total Requests | 40800 | 40799 |
| **Failed Requests** | 39546 | **None** |
| P50 Latency (ms) | 0.00 | 4.11 |
| P95 Latency (ms) | 0.00 | **16.56** |
| P99 Latency (ms) | 11.52 | 621.05 |
| Max Replicas | 1 | 1 |
| Avg Replicas | 1.0 | 1.0 |

