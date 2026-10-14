#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-aws-capstone}"
REGION="${AWS_REGION:-us-east-1}"

printf 'Validating CloudFormation template...\n'
aws cloudformation validate-template \
  --template-body file://infra/template.yaml \
  --region "$REGION"

printf 'Deploying stack %s in %s...\n' "$STACK_NAME" "$REGION"
aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file infra/template.yaml \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"

printf 'Retrieving deployment outputs...\n'
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' \
  --region "$REGION" \
  --output table
