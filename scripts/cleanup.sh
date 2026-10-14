#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-aws-capstone}"
REGION="${AWS_REGION:-us-east-1}"

printf 'Deleting stack %s in %s...\n' "$STACK_NAME" "$REGION"
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

printf 'Stack deletion complete.\n'
