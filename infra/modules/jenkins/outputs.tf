# ─────────────────────────────────────────────────────────────────────────────
# infra/modules/jenkins/outputs.tf
# ─────────────────────────────────────────────────────────────────────────────

output "jenkins_public_ip" {
  description = "Public IP of the Jenkins EC2 instance"
  value       = aws_instance.jenkins.public_ip
}

output "jenkins_public_dns" {
  description = "Public DNS of the Jenkins EC2 instance"
  value       = aws_instance.jenkins.public_dns
}

output "jenkins_url" {
  description = "URL to access the Jenkins UI"
  value       = "http://${aws_instance.jenkins.public_ip}:8080"
}

output "jenkins_instance_id" {
  description = "EC2 instance ID (for stop/start cost control)"
  value       = aws_instance.jenkins.id
}

output "jenkins_iam_role_arn" {
  description = "ARN of the Jenkins IAM role"
  value       = aws_iam_role.jenkins.arn
}
