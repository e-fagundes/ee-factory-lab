#!/usr/bin/env bash
set -euo pipefail
: "${QUAY_USERNAME:?Set QUAY_USERNAME}"
: "${QUAY_PASSWORD:?Set QUAY_PASSWORD}"

QUAY_EMAIL="${QUAY_EMAIL:-ee-factory-lab@example.invalid}"

kubectl -n ee-factory-lab create secret docker-registry quay-docker-config \
  --docker-server=quay.io \
  --docker-username="${QUAY_USERNAME}" \
  --docker-password="${QUAY_PASSWORD}" \
  --docker-email="${QUAY_EMAIL}" \
  --dry-run=client -o yaml | kubectl apply -f -
