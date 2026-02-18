output "ecr_repo_url" {
  description = "ECR repository URL for the k6 runner image"
  value       = aws_ecr_repository.k6.repository_url
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.this.arn
}

output "task_definition_arn" {
  description = "ECS task definition ARN"
  value       = aws_ecs_task_definition.k6.arn
}

output "public_subnet_ids" {
  description = "Public subnet IDs used for Fargate tasks"
  value       = [for s in aws_subnet.public : s.id]
}

output "task_security_group_id" {
  description = "Security group ID attached to the Fargate task ENI"
  value       = aws_security_group.task.id
}

output "log_group_name" {
  description = "CloudWatch log group name for task logs"
  value       = aws_cloudwatch_log_group.k6.name
}

output "container_name" {
  description = "Container name inside the task definition"
  value       = local.container_name
}

output "results_bucket_name" {
  description = "S3 bucket where k6 summary.json is uploaded"
  value       = aws_s3_bucket.results.bucket
}

output "results_prefix" {
  description = "S3 prefix under which runs are stored"
  value       = local.results_prefix
}