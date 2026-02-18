terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # ~> 5.0 allows patch/minor upgrades within 5.x but blocks major version
      # bumps (6.0+) that may contain breaking changes to resource schemas.
      # Use >= only if you intentionally want to track future major versions.
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      Purpose   = "load-testing"
      ManagedBy = "terraform"
    }
  }
}

data "aws_availability_zones" "available" {}

locals {
  name           = var.project
  container_name = "k6"

  # Reuse explicitly when a resource needs merge(Name=...)
  common_tags = {
    Project   = var.project
    Purpose   = "load-testing"
    ManagedBy = "terraform"
  }
}