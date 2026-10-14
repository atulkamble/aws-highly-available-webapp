variable "aws_region" {
  description = "AWS region in which to deploy the application."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used to name resources created by this stack."
  type        = string
  default     = "aws-capstone"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,27}$", var.project_name))
    error_message = "project_name must be 2-28 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "instance_type" {
  description = "EC2 instance type for the web application."
  type        = string
  default     = "t3.micro"
}

variable "vpc_cidr" {
  description = "IPv4 CIDR block for the application VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the two public subnets, one per Availability Zone."
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Exactly two public subnet CIDR blocks are required."
  }
}

variable "asg_min_size" {
  description = "Minimum number of EC2 instances in the Auto Scaling group."
  type        = number
  default     = 2
}

variable "asg_desired_capacity" {
  description = "Initial desired number of EC2 instances in the Auto Scaling group."
  type        = number
  default     = 2
}

variable "asg_max_size" {
  description = "Maximum number of EC2 instances in the Auto Scaling group."
  type        = number
  default     = 4
}

variable "cpu_target_value" {
  description = "Target average CPU utilization percentage for Auto Scaling."
  type        = number
  default     = 60
}

variable "tags" {
  description = "Tags applied to all supported AWS resources."
  type        = map(string)
  default = {
    Project   = "aws-highly-available-webapp"
    ManagedBy = "Terraform"
  }
}
