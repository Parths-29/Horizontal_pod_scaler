variable "bucket_name" { type = string }

resource "aws_s3_bucket" "ml_models" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id
  versioning_configuration {
    status = "Enabled"
  }
}

output "bucket_name" {
  value = aws_s3_bucket.ml_models.id
}

output "bucket_arn" {
  value = aws_s3_bucket.ml_models.arn
}
