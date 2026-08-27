# Setup Guide

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | 2.x | [docs.aws.amazon.com](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| Terraform | 1.7+ | [developer.hashicorp.com](https://developer.hashicorp.com/terraform/install) |
| kubectl | 1.29+ | [kubernetes.io](https://kubernetes.io/docs/tasks/tools/) |
| Helm | 3.x | [helm.sh](https://helm.sh/docs/intro/install/) |
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Go | 1.22+ | [go.dev](https://go.dev/dl/) |
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| k6 | 0.51+ | [grafana.com/docs/k6](https://grafana.com/docs/k6/latest/set-up/install-k6/) |

## Step 0 — Bootstrap Terraform Remote State

> **Do this ONCE before the first `terraform init`.**

These resources cannot be managed by Terraform itself (chicken-and-egg), so create them manually:

```bash
# Create the S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket hpa-scaler-tfstate \
  --region us-east-1

# Enable versioning (lets you recover from accidental state corruption)
aws s3api put-bucket-versioning \
  --bucket hpa-scaler-tfstate \
  --versioning-configuration Status=Enabled

# Enable server-side encryption
aws s3api put-bucket-encryption \
  --bucket hpa-scaler-tfstate \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Create the DynamoDB table for state locking
# The LockID attribute is the partition key — required by Terraform
aws dynamodb create-table \
  --table-name hpa-scaler-tfstate-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Step 1 — Configure AWS CLI

```bash
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output format (json)

# Verify
aws sts get-caller-identity
```

## Step 2 — Set Environment Variables

```bash
cp .env.example .env
# Edit .env with your values (S3 bucket name, AWS region)
export $(cat .env | xargs)
```

## Step 3 — Train the ML Model

```bash
cd ml
pip install -r requirements.txt

# Download training data (~1GB, stored in ml/data/ which is gitignored)
python download_data.py

# Train both models, evaluate, save best to ml/artifacts/model.pkl
python train.py

# Upload model artifact to S3 (uses AWS credentials from environment)
python upload_model.py

cd ..
```

## Step 4 — Provision AWS Infrastructure

```bash
cd infra
terraform init    # Downloads providers, configures S3 backend
terraform plan    # Review: VPC, EKS, ECR, S3, IAM resources
terraform apply   # Type 'yes' to confirm — takes ~15 minutes for EKS

# Configure kubectl to talk to the new cluster
aws eks update-kubeconfig --name hpa-scaler-eks --region us-east-1
kubectl get nodes  # Should show 2x t3.medium nodes

cd ..
```

## Step 5 — Build and Push Docker Images

```bash
# Get the ECR registry URL from Terraform outputs
ECR_URL=$(cd infra && terraform output -raw ecr_demo_app_url | cut -d/ -f1)

# Authenticate Docker with ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_URL

# Build and push (Jenkins automates this in production)
docker build -t $ECR_URL/demo-app:latest demo-app/
docker push $ECR_URL/demo-app:latest

docker build -t $ECR_URL/scaler:latest scaler/
docker push $ECR_URL/scaler:latest

docker build -t $ECR_URL/backend:latest backend/
docker push $ECR_URL/backend:latest
```

## Step 6 — Deploy to EKS

```bash
# Install KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda-system --create-namespace

# Install Prometheus + Grafana (kube-prometheus-stack)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f monitoring/prometheus/values.yaml

# Deploy the demo app (both reactive and predictive)
kubectl apply -f demo-app/k8s/

# Deploy the external scaler
kubectl apply -f scaler/k8s/

# Deploy the FastAPI backend
kubectl apply -f backend/k8s/
```

## Step 7 — Run Load Tests

```bash
# Gradual ramp (recommended first test)
k6 run load-tests/gradual_ramp.js

# Sudden spike
k6 run load-tests/sudden_spike.js

# Realistic traffic pattern (30 min)
k6 run --out json=load-tests/results/realistic.json load-tests/realistic_traffic.js
```

## Step 8 — Access the Dashboard

```bash
# Grafana
kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80
# → http://localhost:3000 (admin/admin)

# React dashboard (local dev)
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

## Teardown

```bash
# Remove all K8s resources
kubectl delete -f demo-app/k8s/ -f scaler/k8s/ -f backend/k8s/
helm uninstall keda -n keda-system
helm uninstall monitoring -n monitoring

# Destroy AWS infrastructure (CAUTION: this is irreversible)
cd infra && terraform destroy
```
