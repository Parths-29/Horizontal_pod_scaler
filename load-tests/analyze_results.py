#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# load-tests/analyze_results.py
# Parses the k6 JSON outputs and replica CSVs to generate a final Markdown report.
# ─────────────────────────────────────────────────────────────────────────────

import json
import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
DOCS_DIR = Path("../docs")

SCENARIOS = ["gradual_ramp", "sudden_spike", "daily_cycle"]
AUTOSCALERS = ["hpa", "keda"]

def parse_k6_json(filepath: Path):
    """
    K6 json output has one JSON object per line.
    We need to extract the final summary metrics.
    Actually, `k6 run --out json=...` dumps every single metric data point.
    A simpler way is to just grep the final summary or parse the metrics at the end.
    But since k6 dumps point-by-point, we can aggregate.
    Actually, k6 writes a 'Metric' type line and 'Point' type lines.
    To avoid huge memory usage parsing raw k6 JSON, let's just parse the 
    aggregate metrics if we use a different k6 plugin, OR we can just read the 
    points and compute P95 ourselves.
    
    For simplicity, let's read the JSON file line by line and aggregate `http_req_duration` and `http_reqs`.
    """
    if not filepath.exists():
        return None

    reqs = 0
    failed_reqs = 0
    durations = []

    with open(filepath, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                if data["type"] == "Point":
                    metric = data["metric"]
                    if metric == "http_reqs":
                        reqs += data["data"]["value"]
                    elif metric == "http_req_failed":
                        failed_reqs += data["data"]["value"]
                    elif metric == "http_req_duration":
                        durations.append(data["data"]["value"])
            except:
                pass

    durations.sort()
    count = len(durations)
    
    p50 = durations[int(count * 0.50)] if count > 0 else 0
    p95 = durations[int(count * 0.95)] if count > 0 else 0
    p99 = durations[int(count * 0.99)] if count > 0 else 0

    return {
        "Total Requests": reqs,
        "Failed Requests": failed_reqs,
        "P50 Latency (ms)": f"{p50:.2f}",
        "P95 Latency (ms)": f"{p95:.2f}",
        "P99 Latency (ms)": f"{p99:.2f}",
    }

def analyze_replicas(filepath: Path):
    if not filepath.exists():
        return None
    df = pd.read_csv(filepath)
    if len(df) == 0:
        return None
    max_replicas = df["replicas"].max()
    avg_replicas = df["replicas"].mean()
    return {
        "Max Replicas": max_replicas,
        "Avg Replicas": f"{avg_replicas:.1f}"
    }

def main():
    if not DOCS_DIR.exists():
        DOCS_DIR.mkdir()

    md_content = "# Phase 6: Autoscaling Benchmark Results\n\n"
    md_content += "> ⚠️ **Note:** These metrics were captured by running k6 load tests from within the AWS VPC (Jenkins EC2) to eliminate internet latency jitter.\n\n"

    for scenario in SCENARIOS:
        md_content += f"## Scenario: {scenario.replace('_', ' ').title()}\n\n"
        md_content += "| Metric | Baseline (HPA) | Predictive (KEDA) |\n"
        md_content += "|--------|----------------|-------------------|\n"

        hpa_k6 = parse_k6_json(RESULTS_DIR / f"hpa_{scenario}.json")
        keda_k6 = parse_k6_json(RESULTS_DIR / f"keda_{scenario}.json")
        
        hpa_rep = analyze_replicas(RESULTS_DIR / f"hpa_{scenario}_replicas.csv")
        keda_rep = analyze_replicas(RESULTS_DIR / f"keda_{scenario}_replicas.csv")

        if not hpa_k6 or not keda_k6:
            md_content += "| *Data missing* | - | - |\n\n"
            continue

        metrics = list(hpa_k6.keys())
        if hpa_rep and keda_rep:
            metrics.extend(list(hpa_rep.keys()))

        for m in metrics:
            h_val = hpa_k6.get(m) or (hpa_rep.get(m) if hpa_rep else "N/A")
            k_val = keda_k6.get(m) or (keda_rep.get(m) if keda_rep else "N/A")
            
            # Format row
            if m == "Failed Requests":
                # Highlight if KEDA had fewer dropped requests
                md_content += f"| **{m}** | {h_val} | **{k_val}** |\n"
            elif m == "P95 Latency (ms)":
                md_content += f"| {m} | {h_val} | **{k_val}** |\n"
            else:
                md_content += f"| {m} | {h_val} | {k_val} |\n"
        
        md_content += "\n"

    report_path = DOCS_DIR / "benchmark-results.md"
    with open(report_path, "w") as f:
        f.write(md_content)

    print(f"✅ Generated {report_path}")

if __name__ == "__main__":
    main()
