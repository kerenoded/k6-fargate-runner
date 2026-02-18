# Reuse the shared assume-role policy from iam.tf (includes aws:SourceAccount
# confused deputy protection). Do not duplicate it here.
resource "aws_iam_role" "task_role" {
  name               = "${var.project}-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}
