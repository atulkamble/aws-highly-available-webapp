#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-aws-capstone}"
REGION="${AWS_REGION:-us-east-1}"
TERRAFORM_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../terraform" && pwd)"

command -v terraform >/dev/null 2>&1 || {
  printf 'Error: Terraform is required but was not found in PATH.\n' >&2
  exit 1
}

printf 'Initializing Terraform...\n'
terraform -chdir="$TERRAFORM_DIR" init

printf 'Deploying stack %s in %s...\n' "$STACK_NAME" "$REGION"
terraform -chdir="$TERRAFORM_DIR" apply \
  -auto-approve \
  -var="project_name=$STACK_NAME" \
  -var="aws_region=$REGION"

printf 'Deployment outputs:\n'
terraform -chdir="$TERRAFORM_DIR" output
