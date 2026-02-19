locals {
  results_bucket_name = "${var.project}-results"
  results_prefix      = "runs"
}

resource "aws_s3_bucket" "results" {
  bucket = local.results_bucket_name

  # Set to true so `terraform destroy` can remove the bucket even when it
  # contains result objects. Without this, destroy fails with BucketNotEmpty.
  # The lifecycle rule below already expires objects after 30 days, so data
  # loss risk is low — but be aware this makes accidental destruction easier.
  force_destroy = true

  tags = merge(local.common_tags, {
    Name = local.results_bucket_name
  })
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket                  = aws_s3_bucket.results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "results" {
  bucket = aws_s3_bucket.results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "results" {
  bucket = aws_s3_bucket.results.id

  rule {
    id     = "expire-old"
    status = "Enabled"

    # An explicit filter block is required by the AWS provider (will be a hard
    # error in a future version). Empty filter = apply to all objects.
    filter {}

    expiration {
      days = 30
    }
  }
}

data "aws_iam_policy_document" "results_bucket_tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    resources = [
      aws_s3_bucket.results.arn,
      "${aws_s3_bucket.results.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "results" {
  bucket = aws_s3_bucket.results.id
  policy = data.aws_iam_policy_document.results_bucket_tls_only.json
}