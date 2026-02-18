data "aws_iam_policy_document" "results_s3_write" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload"
    ]
    resources = [
      "${aws_s3_bucket.results.arn}/${local.results_prefix}/*"
    ]
  }
}

resource "aws_iam_policy" "results_s3_write" {
  name   = "${var.project}-results-s3-write"
  policy = data.aws_iam_policy_document.results_s3_write.json
}

resource "aws_iam_role_policy_attachment" "task_role_results_s3_write" {
  role       = aws_iam_role.task_role.name
  policy_arn = aws_iam_policy.results_s3_write.arn
}