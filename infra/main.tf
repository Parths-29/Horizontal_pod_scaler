provider "aws" {
  region = var.aws_region
}

# Fetch available AZs for the VPC
data "aws_availability_zones" "available" {}

module "vpc" {
  source = "./modules/vpc"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr
  azs  = slice(data.aws_availability_zones.available.names, 0, 3)
}

module "eks" {
  source = "./modules/eks"

  cluster_name    = var.cluster_name
  cluster_version = "1.29"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
}

module "ecr" {
  source = "./modules/ecr"

  repositories = [
    "demo-app",
    "keda-scaler",
    "ml-backend",
    "frontend-dashboard"
  ]
}

module "s3" {
  source = "./modules/s3"

  bucket_name = "${var.cluster_name}-ml-models"
}

# ── Jenkins CI/CD Server ──────────────────────────────────────────────────────
# Provisions an EC2 instance running Jenkins with Docker, kubectl, and AWS CLI.
# IAM role is least-privilege: ECR push to project repos, EKS describe, S3 read.
module "jenkins" {
  source = "./modules/jenkins"

  cluster_name  = var.cluster_name
  vpc_id        = module.vpc.vpc_id
  subnet_id     = module.vpc.public_subnets[0]
  allowed_cidr  = var.jenkins_allowed_cidr
  s3_bucket_arn = module.s3.bucket_arn
  instance_type = "t3.medium"
  key_pair_name = var.jenkins_key_pair_name
}
