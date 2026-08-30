# ─────────────────────────────────────────────────────────────────────────────
# infra/modules/jenkins/variables.tf
# ─────────────────────────────────────────────────────────────────────────────

variable "cluster_name" {
  description = "Name of the EKS cluster (used for resource naming and IAM scoping)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID to place the Jenkins security group in"
  type        = string
}

variable "subnet_id" {
  description = "Public subnet ID for the Jenkins EC2 instance"
  type        = string
}

variable "allowed_cidr" {
  description = "CIDR block allowed to access Jenkins UI (e.g., your IP: 203.0.113.5/32)"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket used for ML models (read-only access)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for the Jenkins server"
  type        = string
  default     = "t3.medium"
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access (optional)"
  type        = string
  default     = ""
}
