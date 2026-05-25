#!/usr/bin/env bash
set -euo pipefail
NAMESPACE="${NAMESPACE:-ee-factory-lab}"
kubectl -n "${NAMESPACE}" port-forward svc/ee-factory-api 8000:8000 &
kubectl -n "${NAMESPACE}" port-forward svc/ee-factory-portal 3000:3000 &
wait
