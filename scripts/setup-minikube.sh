#!/usr/bin/env bash
set -euo pipefail
PROFILE="${PROFILE:-minikube}"
DRIVER="${DRIVER:-podman}"
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-containerd}"
CPUS="${CPUS:-4}"
MEMORY="${MEMORY:-6144mb}"

if command -v podman >/dev/null 2>&1; then
  podman info >/dev/null 2>&1 || podman machine start
fi

minikube start \
  --profile "${PROFILE}" \
  --driver "${DRIVER}" \
  --container-runtime "${CONTAINER_RUNTIME}" \
  --cpus "${CPUS}" \
  --memory "${MEMORY}"

minikube profile "${PROFILE}"
minikube addons enable storage-provisioner --profile "${PROFILE}"
minikube addons enable default-storageclass --profile "${PROFILE}"
