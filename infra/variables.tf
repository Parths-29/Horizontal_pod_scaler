variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "predictive-hpa-cluster"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# ── Jenkins CI/CD ─────────────────────────────────────────────────────────────

variable "jenkins_allowed_cidr" {
  description = "Your IP address in CIDR notation (e.g., 203.0.113.5/32) for Jenkins UI access"
  type        = string
  default     = "0.0.0.0/0" # OVERRIDE THIS with your actual IP before applying!
}

variable "jenkins_key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access to Jenkins (optional)"
  type        = string
  default     = ""
}
