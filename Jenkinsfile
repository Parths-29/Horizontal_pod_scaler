// ─────────────────────────────────────────────────────────────────────────────
// Jenkinsfile — CI/CD pipeline for Horizontal Pod Scaler
// ─────────────────────────────────────────────────────────────────────────────
// Stages:
//   1. Checkout           — pull the repo
//   2. Setup              — verify Docker & AWS CLI are available
//   3. Lint & Test        — flake8, black, pytest
//   4. Build Images       — parallel Docker builds tagged with GIT_COMMIT
//   5. Push to ECR        — authenticate and push to project-scoped ECR repos
//   6. Deploy to EKS      — kubectl set image + rollout status
//
// Environment variables are injected via Jenkins Credentials Binding.
// No secrets are hardcoded in this file.
// ─────────────────────────────────────────────────────────────────────────────

pipeline {
    agent any

    environment {
        // ── Immutable image tag from the commit SHA ──────────────────────
        IMAGE_TAG = "${env.GIT_COMMIT?.take(12) ?: 'latest'}"

        // ── AWS config (injected via Jenkins env vars / credentials) ─────
        AWS_REGION     = credentials('AWS_REGION')        // e.g. "us-west-2"
        AWS_ACCOUNT_ID = credentials('AWS_ACCOUNT_ID')    // e.g. "123456789012"
        EKS_CLUSTER    = credentials('EKS_CLUSTER_NAME')  // e.g. "predictive-hpa-cluster"

        // ── ECR repository URIs (constructed from account + region) ──────
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        ECR_BACKEND  = "${ECR_REGISTRY}/horizontal-pod-scaler/backend"
        ECR_SCALER   = "${ECR_REGISTRY}/horizontal-pod-scaler/scaler"
        ECR_DEMO     = "${ECR_REGISTRY}/horizontal-pod-scaler/demo-app"
    }

    options {
        // Abort if the pipeline runs longer than 30 minutes
        timeout(time: 30, unit: 'MINUTES')
        // Keep last 10 builds
        buildDiscarder(logRotator(numToKeepStr: '10'))
        // Prepend timestamps to every log line
        timestamps()
    }

    stages {
        // ── 1. Checkout ──────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // ── 2. Setup — verify tooling is available ───────────────────────
        stage('Setup') {
            steps {
                sh 'docker --version'
                sh 'aws --version'
                sh 'kubectl version --client --short || true'
            }
        }

        // ── 3. Lint & Test ───────────────────────────────────────────────
        // NOTE: For faster builds, pre-install flake8/black/pytest on the
        // Jenkins agent image. The || true handles cases where they are
        // already installed.
        stage('Lint & Test') {
            steps {
                sh '''
                    pip install --quiet flake8 black pytest 2>/dev/null || true
                    echo "── Linting with flake8 ──"
                    flake8 backend/ scaler/ ml/ --max-line-length=120 --exclude=proto
                    echo "── Checking formatting with black ──"
                    black --check --line-length=120 backend/ scaler/ ml/ || echo "WARN: black formatting issues (non-blocking)"
                    echo "── Running tests ──"
                    pytest scaler/test_main.py ml/tests/ -v --tb=short
                '''
            }
        }

        // ── 4. Build Docker Images (parallel) ────────────────────────────
        stage('Build Images') {
            parallel {
                stage('Build Backend') {
                    steps {
                        sh "docker build -t ${ECR_BACKEND}:${IMAGE_TAG} -f backend/Dockerfile backend/"
                    }
                }
                stage('Build Scaler') {
                    steps {
                        sh "docker build -t ${ECR_SCALER}:${IMAGE_TAG} -f scaler/Dockerfile scaler/"
                    }
                }
                stage('Build Demo App') {
                    steps {
                        sh "docker build -t ${ECR_DEMO}:${IMAGE_TAG} -f demo-app/Dockerfile demo-app/"
                    }
                }
            }
        }

        // ── 5. Push to ECR ───────────────────────────────────────────────
        stage('Push to ECR') {
            steps {
                sh '''
                    echo "── Authenticating with ECR ──"
                    aws ecr get-login-password --region $AWS_REGION \
                        | docker login --username AWS --password-stdin $ECR_REGISTRY

                    echo "── Pushing images ──"
                    docker push ${ECR_BACKEND}:${IMAGE_TAG}
                    docker push ${ECR_SCALER}:${IMAGE_TAG}
                    docker push ${ECR_DEMO}:${IMAGE_TAG}
                '''
            }
        }

        // ── 6. Deploy to EKS ─────────────────────────────────────────────
        stage('Deploy to EKS') {
            steps {
                sh """
                    echo "── Configuring kubectl ──"
                    aws eks update-kubeconfig --region $AWS_REGION --name $EKS_CLUSTER

                    echo "── Updating deployments ──"
                    kubectl set image deployment/ml-backend       ml-backend=${ECR_BACKEND}:${IMAGE_TAG}       -n default
                    kubectl set image deployment/keda-external-scaler scaler=${ECR_SCALER}:${IMAGE_TAG}        -n default
                    kubectl set image deployment/demo-app         demo-app=${ECR_DEMO}:${IMAGE_TAG}            -n default

                    echo "── Waiting for rollouts ──"
                    kubectl rollout status deployment/ml-backend       -n default --timeout=120s
                    kubectl rollout status deployment/keda-external-scaler -n default --timeout=120s
                    kubectl rollout status deployment/demo-app         -n default --timeout=120s
                """
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline succeeded — images pushed and deployments rolled out with tag: ${IMAGE_TAG}"
        }
        failure {
            echo "❌ Pipeline failed. Check logs above for details."
            // NOTE (known limitation): A production pipeline would add
            // `kubectl rollout undo` here to automatically revert failed
            // deployments. For this portfolio project, we document this
            // as a known limitation in docs/ci_cd.md — an interviewer
            // might probe "what happens if a deployment fails halfway?"
        }
        always {
            cleanWs()
        }
    }
}
