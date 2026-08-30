# ─────────────────────────────────────────────────────────────────────────────
# infra/modules/jenkins/main.tf — Jenkins CI/CD server on EC2
# ─────────────────────────────────────────────────────────────────────────────
# Provisions:
#   - EC2 instance (t3.medium) with Docker + Jenkins pre-installed via user_data
#   - Security group restricting Jenkins UI (8080) to the operator's IP
#   - IAM instance profile with least-privilege access to ECR, EKS, and S3
# ─────────────────────────────────────────────────────────────────────────────

# ── Data Sources ─────────────────────────────────────────────────────────────

# Latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── Security Group ───────────────────────────────────────────────────────────

resource "aws_security_group" "jenkins" {
  name_prefix = "jenkins-sg-"
  description = "Allow Jenkins UI (8080) and SSH (22) from operator IP only"
  vpc_id      = var.vpc_id

  # Jenkins UI — restricted to operator IP
  ingress {
    description = "Jenkins UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  # SSH — restricted to operator IP
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  # All outbound traffic (for package installs, ECR pulls, etc.)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.cluster_name}-jenkins-sg"
    Project = "horizontal-pod-scaler"
  }
}

# ── IAM — Least Privilege ───────────────────────────────────────────────────

# Trust policy: allow EC2 to assume the role
data "aws_iam_policy_document" "jenkins_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "jenkins" {
  name               = "${var.cluster_name}-jenkins-role"
  assume_role_policy = data.aws_iam_policy_document.jenkins_assume_role.json

  tags = {
    Project = "horizontal-pod-scaler"
  }
}

# ECR permissions — scoped to only this project's repositories
data "aws_iam_policy_document" "jenkins_ecr" {
  # GetAuthorizationToken is account-wide (no resource scoping possible)
  statement {
    sid     = "ECRAuth"
    actions = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push/pull actions scoped to only our three repos
  statement {
    sid = "ECRPushPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeRepositories",
      "ecr:ListImages"
    ]
    resources = [
      "arn:aws:ecr:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:repository/horizontal-pod-scaler/*"
    ]
  }
}

# EKS permissions — scoped to the specific cluster
data "aws_iam_policy_document" "jenkins_eks" {
  statement {
    sid = "EKSDescribe"
    actions = [
      "eks:DescribeCluster",
      "eks:ListClusters"
    ]
    resources = [
      "arn:aws:eks:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:cluster/${var.cluster_name}"
    ]
  }
}

# S3 permissions — read-only, scoped to the ML models bucket
data "aws_iam_policy_document" "jenkins_s3" {
  statement {
    sid = "S3ReadModels"
    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      var.s3_bucket_arn,
      "${var.s3_bucket_arn}/*"
    ]
  }
}

resource "aws_iam_policy" "jenkins_ecr" {
  name   = "${var.cluster_name}-jenkins-ecr"
  policy = data.aws_iam_policy_document.jenkins_ecr.json
}

resource "aws_iam_policy" "jenkins_eks" {
  name   = "${var.cluster_name}-jenkins-eks"
  policy = data.aws_iam_policy_document.jenkins_eks.json
}

resource "aws_iam_policy" "jenkins_s3" {
  name   = "${var.cluster_name}-jenkins-s3"
  policy = data.aws_iam_policy_document.jenkins_s3.json
}

resource "aws_iam_role_policy_attachment" "ecr" {
  role       = aws_iam_role.jenkins.name
  policy_arn = aws_iam_policy.jenkins_ecr.arn
}

resource "aws_iam_role_policy_attachment" "eks" {
  role       = aws_iam_role.jenkins.name
  policy_arn = aws_iam_policy.jenkins_eks.arn
}

resource "aws_iam_role_policy_attachment" "s3" {
  role       = aws_iam_role.jenkins.name
  policy_arn = aws_iam_policy.jenkins_s3.arn
}

resource "aws_iam_instance_profile" "jenkins" {
  name = "${var.cluster_name}-jenkins-profile"
  role = aws_iam_role.jenkins.name
}

# ── EC2 Instance ─────────────────────────────────────────────────────────────

resource "aws_instance" "jenkins" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.jenkins.id]
  iam_instance_profile   = aws_iam_instance_profile.jenkins.name
  key_name               = var.key_pair_name

  associate_public_ip_address = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
  }

  # User-data script installs Docker, kubectl, and Jenkins on first boot
  user_data = <<-USERDATA
    #!/bin/bash
    set -euxo pipefail

    # ── System updates ────────────────────────────────────────────────
    dnf update -y

    # ── Docker ────────────────────────────────────────────────────────
    dnf install -y docker
    systemctl enable docker && systemctl start docker
    usermod -aG docker ec2-user

    # ── AWS CLI v2 (already on AL2023, just verify) ───────────────────
    aws --version

    # ── kubectl ───────────────────────────────────────────────────────
    curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x kubectl && mv kubectl /usr/local/bin/

    # ── Jenkins (LTS) ────────────────────────────────────────────────
    dnf install -y java-17-amazon-corretto-headless
    curl -fsSL https://pkg.jenkins.io/redhat-stable/jenkins.repo -o /etc/yum.repos.d/jenkins.repo
    rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io-2023.key
    dnf install -y jenkins
    usermod -aG docker jenkins
    systemctl enable jenkins && systemctl start jenkins

    # ── Git (for Jenkins pipeline checkout) ───────────────────────────
    dnf install -y git

    echo ">>> Jenkins setup complete. Access at http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8080"
  USERDATA

  tags = {
    Name    = "${var.cluster_name}-jenkins"
    Project = "horizontal-pod-scaler"
  }
}
