variable "cluster_name" { type = string }
variable "s3_bucket_arn" { type = string }
variable "namespace" { type = string }
variable "service_account" { type = string }

data "aws_iam_policy_document" "s3_access" {
  statement {
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

resource "aws_iam_policy" "s3_access" {
  name        = "${var.cluster_name}-s3-access"
  description = "Allow EKS pods to access the ML models bucket"
  policy      = data.aws_iam_policy_document.s3_access.json
}

module "irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${var.cluster_name}-ml-backend-role"

  role_policy_arns = {
    policy = aws_iam_policy.s3_access.arn
  }

  # Replace placeholder with actual OIDC provider ARN from EKS module in real usage
  oidc_providers = {
    main = {
      provider_arn               = "arn:aws:iam::000000000000:oidc-provider/oidc.eks.us-west-2.amazonaws.com/id/EXAMPLED539D4633E53DE1B716D3041E"
      namespace_service_accounts = ["${var.namespace}:${var.service_account}"]
    }
  }
}

output "iam_role_arn" {
  value = module.irsa.iam_role_arn
}
