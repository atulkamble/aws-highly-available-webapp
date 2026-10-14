#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-aws-capstone}"
REGION="${AWS_REGION:-us-east-1}"
INFRA_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../infra" && pwd)"

command -v terraform >/dev/null 2>&1 || {
  printf 'Error: Terraform is required but was not found in PATH.\n' >&2
  exit 1
}

printf 'Initializing Terraform...\n'
terraform -chdir="$INFRA_DIR" init

printf 'Destroying stack %s in %s...\n' "$STACK_NAME" "$REGION"
terraform -chdir="$INFRA_DIR" destroy \
  -auto-approve \
  -var="project_name=$STACK_NAME" \
  -var="aws_region=$REGION"

printf 'Terraform destroy complete.\n'
