#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-ee-factory-lab}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)}"

kubectl apply -f deploy/minikube/namespace.yml

kubectl -n "${NAMESPACE}" create secret generic ee-factory-secrets \
  --from-literal="postgres-password=${POSTGRES_PASSWORD}" \
  --from-literal="database-url=postgresql://ee_factory:${POSTGRES_PASSWORD}@postgres:5432/ee_factory" \
  --dry-run=client -o yaml | kubectl apply -f -

minikube image build -t ee-factory-lab/api:local -f apps/api/Dockerfile .
minikube image build -t ee-factory-lab/portal:local -f Dockerfile apps/portal
minikube image build -t ee-factory-lab/builder:local -f Dockerfile apps/builder

kubectl apply -k deploy/minikube
kubectl -n "${NAMESPACE}" rollout status deployment/postgres --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deployment/ee-factory-api --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deployment/ee-factory-portal --timeout=180s
