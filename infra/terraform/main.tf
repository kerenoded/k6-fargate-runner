terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # ~> 6.0 allows patch/minor upgrades within 6.x. Bumped from ~> 5.0
      # because the remote state was written by a v6.x provider; keeping the
      # constraint at ~> 5.0 causes "Resource instance managed by newer
      # provider version" errors on plan/destroy.
      version = "~> 6.0"
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

# Used to scope IAM trust policies to this account (confused deputy protection).
data "aws_caller_identity" "current" {}

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