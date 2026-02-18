variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "project" {
  type    = string
  default = "k6-fargate-loadtest"
}

variable "image_tag" {
  type        = string
  description = "Container image tag for the k6 runner stored in ECR. Default avoids ':latest' for better reproducibility."
  default     = "stable"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "public_subnet_cidrs" {
  type = list(string)

  default = [
    "10.40.10.0/24",
    "10.40.11.0/24"
  ]
}