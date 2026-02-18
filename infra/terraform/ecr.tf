resource "aws_ecr_repository" "k6" {
  name         = local.name
  force_delete = true

  tags = merge(local.common_tags, {
    Name = local.name
  })
}

resource "aws_ecr_lifecycle_policy" "k6" {
  repository = aws_ecr_repository.k6.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images (old digests after tags move)"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the last 7 build-* images (latest is kept forever)"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["build-"]
          countType     = "imageCountMoreThan"
          countNumber   = 7
        }
        action = { type = "expire" }
      }
    ]
  })
}