#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-aws-capstone}"
REGION="${AWS_REGION:-us-east-1}"

WEBSITE_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
  --output text)

TABLE_NAME=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`DynamoDBTable`].OutputValue' \
  --output text)

printf 'Testing application URL: %s\n' "$WEBSITE_URL"
curl -fsS "$WEBSITE_URL"
printf '\n\nChecking DynamoDB counter...\n'
aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key '{"counter_id":{"S":"homepage"}}' \
  --region "$REGION"
