#!/usr/bin/env bash
set -euo pipefail

TERRAFORM_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../terraform" && pwd)"

command -v terraform >/dev/null 2>&1 || {
  printf 'Error: Terraform is required but was not found in PATH.\n' >&2
  exit 1
}

WEBSITE_URL="$(terraform -chdir="$TERRAFORM_DIR" output -raw website_url)"

printf 'Testing application URL: %s\n' "$WEBSITE_URL"
HOMEPAGE="$(curl -fsS "$WEBSITE_URL")"
printf '%s' "$HOMEPAGE" | grep -q 'Mobile Launch Event'
printf '%s' "$HOMEPAGE" | grep -q 'Register for the launch'
printf '%s' "$HOMEPAGE" | grep -q 'name="pincode"'
printf '%s' "$HOMEPAGE" | grep -Eq 'id="total-visits">[0-9][0-9,]*</strong>' || {
  printf 'Error: visitor counter did not return a numeric total.\n' >&2
  exit 1
}
printf 'Event page: OK\n'

printf 'Checking ALB readiness endpoint...\n'
curl -fsS "$WEBSITE_URL/health/ready"
printf '\nChecking instance telemetry...\n'
STATUS_JSON="$(curl -fsS "$WEBSITE_URL/api/status")"
for field in status instance_id availability_zone region app_version uptime_seconds page_requests; do
  printf '%s' "$STATUS_JSON" | grep -q "\"$field\":" || {
    printf 'Error: status response is missing field %s.\n' "$field" >&2
    exit 1
  }
done
printf 'Application status API: OK\n'
