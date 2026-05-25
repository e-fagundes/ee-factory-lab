#!/usr/bin/env bash
set -euo pipefail
EE="${1:-ee-ansible-windows}"
BUILD_IMAGE="${BUILD_IMAGE:-false}"
PUSH_IMAGE="${PUSH_IMAGE:-false}"
RUNTIME="${RUNTIME:-podman}"

EXAMPLE_DIR="examples/${EE}"
if [ ! -f "${EXAMPLE_DIR}/execution-environment.yml" ]; then
  echo "Example not found: ${EXAMPLE_DIR}" >&2
  exit 1
fi

IMAGE_REF="$(python - <<PY
import json
from pathlib import Path
request = json.loads(Path("${EXAMPLE_DIR}/request.json").read_text(encoding="utf-8"))
print(f"{request.get('publish_target', 'quay.io')}/{request['registry_namespace']}/{request['ee_name']}:{request['image_tag']}")
PY
)"

ansible-builder create \
  --file "${EXAMPLE_DIR}/execution-environment.yml" \
  --context "${EXAMPLE_DIR}/context" \
  --output-filename Containerfile

if [ "${BUILD_IMAGE}" != "true" ]; then
  echo "Build context created at ${EXAMPLE_DIR}/context"
  echo "Set BUILD_IMAGE=true to build ${IMAGE_REF} with ${RUNTIME}."
  exit 0
fi

"${RUNTIME}" build -f "${EXAMPLE_DIR}/context/Containerfile" -t "${IMAGE_REF}" "${EXAMPLE_DIR}/context"

if [ "${PUSH_IMAGE}" = "true" ]; then
  "${RUNTIME}" push "${IMAGE_REF}"
fi
