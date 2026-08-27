terraform {
  required_version = ">= 1.5.0"
  
  # For a production setup, use S3 backend with DynamoDB locking.
  # We leave this as local for demo/portfolio purposes unless explicitly configured.
  # backend "s3" {
  #   bucket         = "my-terraform-state-bucket"
  #   key            = "hpa/terraform.tfstate"
  #   region         = "us-west-2"
  #   dynamodb_table = "terraform-locks"
  # }
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11.0"
    }
  }
}
