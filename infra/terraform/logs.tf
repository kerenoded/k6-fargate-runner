resource "aws_cloudwatch_log_group" "k6" {
  name              = "/ecs/${local.name}"
  retention_in_days = 3

  tags = merge(local.common_tags, {
    Name = "/ecs/${local.name}"
  })
}