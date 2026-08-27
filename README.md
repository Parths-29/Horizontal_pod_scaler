# Horizontal Pod Scaler

> **A predictive Kubernetes autoscaling system that replaces reactive CPU-based HPA with ML-driven forecasting — benchmarked side-by-side on AWS EKS.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Go 1.22+](https://img.shields.io/badge/go-1.22+-00ADD8.svg)](https://go.dev/)
[![Terraform](https://img.shields.io/badge/terraform-1.7+-7B42BC.svg)](https://www.terraform.io/)

---

## Problem Statement

Standard Kubernetes HPA scales **reactively** — it waits for CPU to spike before adding pods, meaning traffic bursts experience high latency or dropped requests during the scale-up delay (typically 30–90 seconds). This project replaces that reactive loop with a **predictive ML scaler** that forecasts load 5–15 minutes ahead and scales proactively, keeping replicas ready before traffic arrives.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Cloud                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    EKS Cluster                         │ │
│  │                                                        │ │
│  │  demo-app (HPA)    demo-app (KEDA)                    │ │
│  │  ─────────────     ──────────────                      │ │
│  │  Reactive CPU  ←→  Predictive ML                       │ │
│  │  scaling           scaling                             │ │
│  │         ↑                  ↑                           │ │
│  │    K8s HPA           KEDA ScaledObject                 │ │
│  │                           ↑                            │ │
│  │                   External Scaler (gRPC/Go)            │ │
│  │                           ↑                            │ │
│  │                   FastAPI Backend ────→ S3 (model)     │ │
│  │                           ↑                            │ │
│  │                   Prometheus + Grafana                 │ │
│  └────────────────────────────────────────────────────────┘ │
│  ECR (images)    S3 (model + state)    DynamoDB (tf lock)   │
└─────────────────────────────────────────────────────────────┘
                         ↑
              React/Vite Dashboard (local or hosted)
```

> Full architecture diagram: [`docs/architecture.md`](docs/architecture.md)

---

## Repository Structure

```
.
├── ml/               # Data pipeline, feature engineering, model training
├── scaler/           # KEDA external gRPC scaler service (Go)
├── demo-app/         # Sample Flask workload + K8s manifests
├── infra/            # Terraform: VPC, EKS, ECR, S3, IAM
├── monitoring/       # Prometheus + Grafana Helm values + dashboard JSON
├── frontend/         # React + Vite dashboard
├── backend/          # FastAPI prediction + benchmark API
├── jenkins/          # Jenkinsfile + Helm values for in-cluster Jenkins
├── load-tests/       # k6 load test scripts
└── docs/             # Architecture, setup guide, results
```

---

## How to Run Locally (docker-compose)

Prerequisites: Docker, Docker Compose, Python 3.11+

```bash
# 1. Clone the repo
git clone https://github.com/Parths-29/Horizontal_pod_scaler.git
cd Horizontal_pod_scaler

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your AWS credentials and S3 bucket name

# 3. Download training data
cd ml && python download_data.py && cd ..

# 4. Train the model and upload to S3
cd ml && python train.py && python upload_model.py && cd ..

# 5. Start all local services
docker-compose up --build

# Services:
# - Frontend:  http://localhost:5173
# - Backend:   http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana:   http://localhost:3000 (admin/admin)
```

---

## How to Deploy to AWS

Prerequisites: AWS CLI configured, Terraform 1.7+, kubectl, Helm 3, Jenkins

### Step 1 — Bootstrap Terraform remote state

```bash
# Create S3 bucket and DynamoDB table for state locking BEFORE running any Terraform
# (This is a one-time manual step — see docs/setup.md for the exact commands)
```

### Step 2 — Provision infrastructure

```bash
cd infra
terraform init
terraform plan
terraform apply   # Review the plan carefully before confirming
```

### Step 3 — Push images via Jenkins pipeline

```bash
# Configure Jenkins credentials (see docs/setup.md)
# Push to main branch — webhook triggers the pipeline automatically
git push origin main
```

### Step 4 — Access the dashboard

```bash
# Get the Grafana load balancer URL
kubectl get svc -n monitoring grafana

# Get the frontend URL (if deployed) or run locally
npm run dev --prefix frontend
```

> Full deployment guide: [`docs/setup.md`](docs/setup.md)

---

## Results

> **Note:** This section will be updated with actual benchmark numbers after Phase 6 load tests run on AWS EKS. Placeholder values below represent the target outcomes.

| Metric | Reactive HPA | Predictive KEDA | Improvement |
|--------|-------------|-----------------|-------------|
| P99 Latency (spike) | — ms | — ms | —% |
| Dropped Requests | — | — | — |
| Time-to-Scale | ~60s | <10s | —s faster |
| Idle Pod-Hours | — | — | —% overhead |
| Cost Estimate | $— | $— | —% |

*Results will be filled in after running [`load-tests/`](load-tests/) against both scaling strategies on EKS.*

---

## Key Design Decisions

### IRSA over Static Keys
The scaler pod accesses S3 using **IAM Roles for Service Accounts (IRSA)** — an OIDC-backed mechanism that issues short-lived credentials to pods without any static `AWS_ACCESS_KEY_ID` in the environment. This is the AWS-recommended approach for production EKS workloads.

### Remote State with S3 + DynamoDB
Terraform state is stored in S3 (encrypted, versioned) with a DynamoDB table providing **state locking** — preventing two concurrent `terraform apply` runs from corrupting the state file. This is a common interview question for infrastructure roles.

### KEDA External Scaler gRPC Interface
Rather than using KEDA's built-in scalers, this project implements the full `ExternalScaler` gRPC interface (`GetMetricSpec`, `GetMetrics`, `IsActive`) — the same interface used by production GPU and custom metric scalers. The gRPC service queries the FastAPI prediction endpoint and surfaces the forecast as a KEDA metric.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Cloud | AWS (EKS, ECR, S3, IAM, CloudWatch) |
| IaC | Terraform 1.7 |
| ML | Prophet, XGBoost, scikit-learn |
| Scaler | Go 1.22, gRPC, KEDA v2 |
| API | FastAPI, Python 3.11 |
| Demo App | Flask, Python 3.11 |
| Frontend | React 18, Vite, Recharts |
| CI/CD | Jenkins |
| Monitoring | Prometheus, Grafana |
| Load Testing | k6 |

---

## License

MIT — see [LICENSE](LICENSE).
