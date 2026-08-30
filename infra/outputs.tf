output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ids attached to the cluster control plane"
  value       = module.eks.cluster_security_group_id
}

output "region" {
  description = "AWS region"
  value       = var.aws_region
}

output "cluster_name" {
  description = "Kubernetes Cluster Name"
  value       = module.eks.cluster_name
}

# ── Jenkins CI/CD ─────────────────────────────────────────────────────────────

output "jenkins_url" {
  description = "URL to access the Jenkins UI"
  value       = module.jenkins.jenkins_url
}

output "jenkins_instance_id" {
  description = "EC2 instance ID — use with 'aws ec2 stop-instances' to save costs"
  value       = module.jenkins.jenkins_instance_id
}

output "jenkins_iam_role_arn" {
  description = "ARN of the Jenkins IAM role (least-privilege)"
  value       = module.jenkins.jenkins_iam_role_arn
}
