resource "aws_ecs_cluster" "this" {
  name = local.name

  tags = merge(local.common_tags, {
    Name = local.name
  })
}

# No inbound; egress only 443
resource "aws_security_group" "task" {
  name        = "${local.name}-task-sg"
  description = "k6 Fargate task SG (no inbound)"
  vpc_id      = aws_vpc.this.id

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name}-task-sg"
  })
}

resource "aws_ecs_task_definition" "k6" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_role.arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = local.container_name
      image     = "${aws_ecr_repository.k6.repository_url}:${var.image_tag}"
      essential = true

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-region        = var.region
          awslogs-group         = aws_cloudwatch_log_group.k6.name
          awslogs-stream-prefix = "run"
        }
      }
    }
  ])

  tags = merge(local.common_tags, {
    Name = local.name
  })
}