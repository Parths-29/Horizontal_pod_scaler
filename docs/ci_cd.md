# CI/CD with Jenkins on AWS

> This guide covers how the Jenkins CI/CD pipeline is set up, how to provision it,
> and critical operational tips for cost control.

---

## Architecture Overview

```
  Developer pushes to main
           │
           ▼
  ┌─────────────────┐
  │   Jenkins (EC2)  │◄── t3.medium, Amazon Linux 2023
  │   Port 8080      │    Docker + AWS CLI + kubectl
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐     ┌────────────────┐
  │  Lint & Test     │────▶│  Build Images  │  (parallel)
  │  flake8, black,  │     │  backend       │
  │  pytest          │     │  scaler        │
  └─────────────────┘     │  demo-app      │
                          └───────┬────────┘
                                  │
                                  ▼
                          ┌────────────────┐
                          │  Push to ECR   │  (tagged with GIT_COMMIT)
                          └───────┬────────┘
                                  │
                                  ▼
                          ┌────────────────┐
                          │  Deploy to EKS │  kubectl set image
                          │  + rollout     │  + rollout status
                          └────────────────┘
```

---

## Provisioning the Jenkins Server

### Prerequisites
- AWS CLI configured with a profile that can create EC2, IAM, and ECR resources.
- Terraform >= 1.5.0 installed.
- An EC2 key pair created in the target region (optional, for SSH).

### Steps

```bash
cd infra/

# 1. Set your IP for security group (REQUIRED — do NOT leave as 0.0.0.0/0)
export TF_VAR_jenkins_allowed_cidr="$(curl -s https://checkip.amazonaws.com)/32"
export TF_VAR_jenkins_key_pair_name="your-key-pair-name"  # optional

# 2. Initialize and apply
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 3. Note the outputs
terraform output jenkins_url           # → http://<ip>:8080
terraform output jenkins_instance_id   # → i-0abc123def456
```

### First-Time Jenkins Setup

1. SSH into the instance (or use Session Manager):
   ```bash
   ssh -i your-key.pem ec2-user@<jenkins-ip>
   ```
2. Retrieve the initial admin password:
   ```bash
   sudo cat /var/lib/jenkins/secrets/initialAdminPassword
   ```
3. Open `http://<jenkins-ip>:8080` in your browser and complete the setup wizard.
4. Install suggested plugins + the **Pipeline** plugin.

### Configure Jenkins Credentials

Go to **Manage Jenkins → Credentials → System → Global credentials** and add:

| Credential ID       | Type          | Value                              |
|---------------------|---------------|------------------------------------|
| `AWS_REGION`        | Secret text   | `us-west-2`                        |
| `AWS_ACCOUNT_ID`    | Secret text   | Your 12-digit AWS account ID       |
| `EKS_CLUSTER_NAME`  | Secret text   | `predictive-hpa-cluster`           |

### Create the Pipeline Job

1. **New Item → Pipeline → OK**
2. Under **Pipeline**, select **Pipeline script from SCM**
3. SCM: **Git**, Repository URL: your GitHub repo
4. Script Path: `Jenkinsfile`
5. Build Triggers: **GitHub hook trigger for GITScm polling** (optional)

---

## IAM Policy — Least Privilege

The Jenkins EC2 instance profile uses **three separate, scoped IAM policies**:

### ECR Policy
Allows pushing images **only** to the three project repositories:
- `horizontal-pod-scaler/backend`
- `horizontal-pod-scaler/scaler`
- `horizontal-pod-scaler/demo-app`

Actions granted:
```
ecr:GetAuthorizationToken        (account-wide, required for login)
ecr:BatchCheckLayerAvailability  (scoped to repos)
ecr:BatchGetImage                (scoped to repos)
ecr:GetDownloadUrlForLayer       (scoped to repos)
ecr:PutImage                     (scoped to repos)
ecr:InitiateLayerUpload          (scoped to repos)
ecr:UploadLayerPart              (scoped to repos)
ecr:CompleteLayerUpload          (scoped to repos)
ecr:DescribeRepositories         (scoped to repos)
ecr:ListImages                   (scoped to repos)
```

### EKS Policy
```
eks:DescribeCluster   (scoped to the specific cluster ARN)
eks:ListClusters      (scoped to the specific cluster ARN)
```

### S3 Policy (Read-Only)
```
s3:GetObject    (scoped to the ML models bucket)
s3:ListBucket   (scoped to the ML models bucket)
```

> **Why this matters:** The original plan used `ecr:*`, `s3:*`, `eks:*` which would have
> allowed this Jenkins box to delete any S3 bucket or ECR repo in the entire AWS account.
> Scoping to project resources follows the principle of least privilege — a strong talking
> point in interviews ("I noticed the generated IAM policy was overly permissive and scoped
> it down to only the resources the pipeline actually needs").

---

## Cost Control

### Stop the Jenkins EC2 When Not in Use

The t3.medium instance costs ~$0.0416/hr (~$30/month if running 24/7).
**Stop it when you're not actively developing:**

```bash
# Get the instance ID from Terraform outputs
INSTANCE_ID=$(cd infra && terraform output -raw jenkins_instance_id)

# Stop the instance (you won't be charged for compute while stopped)
aws ec2 stop-instances --instance-ids $INSTANCE_ID --region us-west-2

# Start it again when you need it
aws ec2 start-instances --instance-ids $INSTANCE_ID --region us-west-2

# NOTE: The public IP may change after restart. Check:
aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

### Scale EKS Node Group to Zero

If you're not running workloads, scale the EKS managed node group to zero:

```bash
# List node groups
aws eks list-nodegroups --cluster-name predictive-hpa-cluster --region us-west-2

# Scale to zero (replace <nodegroup-name> with the actual name)
aws eks update-nodegroup-config \
  --cluster-name predictive-hpa-cluster \
  --nodegroup-name <nodegroup-name> \
  --scaling-config minSize=0,maxSize=0,desiredSize=0 \
  --region us-west-2

# Scale back up when needed
aws eks update-nodegroup-config \
  --cluster-name predictive-hpa-cluster \
  --nodegroup-name <nodegroup-name> \
  --scaling-config minSize=1,maxSize=3,desiredSize=2 \
  --region us-west-2
```

### Teardown Everything

To destroy all Jenkins-related resources:
```bash
cd infra/
terraform destroy -target=module.jenkins
```

---

## Known Limitations

### No Automatic Rollback on Partial Deployment Failure

**Current behavior:** If the Deploy stage fails partway through (e.g., `backend` deploys
successfully but `scaler` fails), you're left in an inconsistent state where some services
run the old image and others run the new one.

**Production fix:** Add `kubectl rollout undo` in the `post.failure` block of the
Jenkinsfile:
```groovy
post {
    failure {
        sh '''
            kubectl rollout undo deployment/ml-backend       -n default || true
            kubectl rollout undo deployment/keda-external-scaler -n default || true
            kubectl rollout undo deployment/demo-app         -n default || true
        '''
    }
}
```

**Why we don't do it now:** For a portfolio project, the added complexity of rollback
testing isn't worth it. But documenting the limitation shows you understand the gap — an
interviewer is more likely to ask "what happens if a deployment fails halfway?" than to
test it.

### Build Speed

Each pipeline run installs `flake8`, `black`, and `pytest` fresh. To speed this up:
1. Create a custom Jenkins agent Docker image with these tools pre-installed.
2. Use Jenkins' built-in pip cache (set `PIP_CACHE_DIR` to a persistent volume).
3. Add a `Makefile` with a `make lint` / `make test` target that uses a virtualenv.

---

## Pipeline Triggers

| Trigger | How |
|---------|-----|
| Manual | Click "Build Now" in Jenkins UI |
| On push to `main` | Configure a GitHub webhook pointing to `http://<jenkins-ip>:8080/github-webhook/` |
| On PR | Add a branch filter in the Jenkinsfile or use a Multibranch Pipeline |

---

## Running Jenkins Locally (Docker Compose)

For offline development/testing of the Jenkinsfile without AWS:

```bash
docker run -d \
  --name jenkins-local \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts

# Access at http://localhost:8080
# Get initial password: docker exec jenkins-local cat /var/lib/jenkins/secrets/initialAdminPassword
```

> ⚠️ The ECR push and EKS deploy stages will fail locally (no AWS credentials).
> Use this for testing the Lint & Test and Build stages only.
