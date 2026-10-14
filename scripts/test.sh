#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
INFRA_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../infra" && pwd)"

command -v terraform >/dev/null 2>&1 || {
  printf 'Error: Terraform is required but was not found in PATH.\n' >&2
  exit 1
}

WEBSITE_URL="$(terraform -chdir="$INFRA_DIR" output -raw website_url)"
TABLE_NAME="$(terraform -chdir="$INFRA_DIR" output -raw dynamodb_table_name)"

printf 'Testing application URL: %s\n' "$WEBSITE_URL"
curl -fsS "$WEBSITE_URL"
printf '\n\nChecking DynamoDB counter...\n'
aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key '{"counter_id":{"S":"homepage"}}' \
  --region "$REGION"
