# Known Limitations & Simplifications

This document outlines deliberate simplifications made in this project to balance complexity, learning objectives, and practical deployment considerations. These are great talking points for technical interviews to demonstrate awareness of production best practices versus development pragmatism.

## 1. IAM Role Scoping for S3 Access (Node vs Pod Level)

**Current Implementation:**
The ML model artifacts are stored in an S3 bucket (`predictive-hpa-cluster-ml-models`). To allow the `ml-backend` pod to read this bucket at startup, we attached an inline S3 read policy directly to the **EKS node group's IAM role** (`standard_node_group-eks-node-group-...`).

**The Production "Correct" Way:**
In a strict production environment, giving the entire worker node access to S3 violates the principle of least privilege. *Any* pod scheduled on that node would inherit the ability to read from the ML bucket. The industry standard is to use **IAM Roles for Service Accounts (IRSA)**. With IRSA, we would create a specific IAM role mapped via an OIDC provider directly to a Kubernetes ServiceAccount (e.g., `ml-backend-sa`). Only the `ml-backend` pod, running under that ServiceAccount, would assume the role and access the bucket.

**Why We Simplified:**
We already demonstrated the ability to use least-privilege role scoping successfully with the Jenkins EC2 instance. Configuring IRSA in EKS via Terraform involves creating an OIDC provider, managing thumbprints, mapping trust policies, and annotating Kubernetes service accounts. Given the scope of this project (focusing heavily on KEDA, custom metrics, and ML forecasting), we opted for node-level permissions to keep the infrastructure code readable and maintain focus on the core autoscaling logic.

## 2. Synthetic vs. Real Trace Data

**Current Implementation:**
Due to memory constraints and download times in some environments (like CloudShell), the model may be trained using a generated `--synthetic` dataset. This data mimics daily and weekly cycles but lacks the organic unpredictability of real-world traffic.

**The Production "Correct" Way:**
The model should be trained on the actual Alibaba 2018 cluster trace data to prove its efficacy against real-world, noisy workload patterns.

**Status:**
This is flagged as an open item to be completed before finalizing the project portfolio. The final `results.md` and benchmarking phase will reflect the model's performance on the genuine Alibaba dataset.
