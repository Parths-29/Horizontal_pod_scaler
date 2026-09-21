#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# load-tests/analyze_results.py
# Parses the k6 JSON outputs and replica CSVs to generate a final Markdown report.
# ─────────────────────────────────────────────────────────────────────────────

import json
import csv
from pathlib import Path

RESULTS_DIR = Path("results")
DOCS_DIR = Path("../docs")

SCENARIOS = ["gradual_ramp", "sudden_spike", "daily_cycle"]
AUTOSCALERS = ["hpa", "keda"]

def parse_k6_json(filepath: Path):
    """
    K6 json output has one JSON object per line.
    Extracts total requests, failed requests, and computes latency percentiles.
    """
    if not filepath.exists():
        return None

    reqs = 0
    failed_reqs = 0
    durations = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("type") == "Point":
                    metric = data.get("metric")
                    if metric == "http_reqs":
                        reqs += data["data"]["value"]
                    elif metric == "http_req_failed":
                        failed_reqs += data["data"]["value"]
                    elif metric == "http_req_duration":
                        durations.append(data["data"]["value"])
            except Exception:
                pass

    durations.sort()
    count = len(durations)

    if count > 0:
        p50 = f"{durations[int(count * 0.50)]:.2f}"
        p95 = f"{durations[int(count * 0.95)]:.2f}"
        p99 = f"{durations[int(count * 0.99)]:.2f}"
    else:
        p50 = "N/A"
        p95 = "N/A"
        p99 = "N/A"

    failure_pct = f"{(failed_reqs / reqs * 100):.1f}%" if reqs > 0 else "0.0%"

    return {
        "Total Requests": reqs,
        "Failed Requests": f"{int(failed_reqs)} ({failure_pct})",
        "P50 Latency (ms)": p50,
        "P95 Latency (ms)": p95,
        "P99 Latency (ms)": p99,
    }

def analyze_replicas(filepath: Path):
    if not filepath.exists():
        return None
    replicas = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get("replicas")
            if val is not None and val.strip().isdigit():
                replicas.append(int(val.strip()))
    if not replicas:
        return None
    max_replicas = max(replicas)
    avg_replicas = sum(replicas) / len(replicas)
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
                md_content += f"| **{m}** | {h_val} | **{k_val}** |\n"
            elif m == "P95 Latency (ms)":
                md_content += f"| {m} | {h_val} | **{k_val}** |\n"
            else:
                md_content += f"| {m} | {h_val} | {k_val} |\n"
        
        md_content += "\n"

    report_path = DOCS_DIR / "benchmark-results.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✅ Generated {report_path}")

if __name__ == "__main__":
    main()
