from copy import deepcopy
import json

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from app.models.ee_request import BuildMode, EERequestRecord


class KubernetesBuildOrchestrator:
    def __init__(self, namespace: str = "ee-factory-lab") -> None:
        self.namespace = namespace

    def submit_job(self, record: EERequestRecord, mode: BuildMode) -> dict[str, object]:
        job = self.job_manifest(record, mode)
        try:
            self._load_config()
            if mode == BuildMode.publish_after_approval:
                self._require_registry_secret()
            api = client.BatchV1Api()
            api.create_namespaced_job(namespace=self.namespace, body=job)
            return {
                "submitted": True,
                "job_name": job["metadata"]["name"],
                "manifest": job,
                "message": "Kubernetes build job created.",
            }
        except ApiException as exc:
            if exc.status == 409:
                return {
                    "submitted": True,
                    "already_exists": True,
                    "job_name": job["metadata"]["name"],
                    "manifest": job,
                    "message": (
                        f"Kubernetes Job {job['metadata']['name']} already exists for this request and stage. "
                        "Use Refresh build status to follow the existing job, or create a new tagged version "
                        "before starting another build."
                    ),
                }
            return {
                "submitted": False,
                "job_name": job["metadata"]["name"],
                "manifest": job,
                "message": f"Kubernetes job was not submitted: {self._format_api_exception(exc)}",
            }
        except Exception as exc:  # Kubernetes client raises several config/runtime exceptions.
            return {
                "submitted": False,
                "job_name": job["metadata"]["name"],
                "manifest": job,
                "message": f"Kubernetes job was not submitted: {exc}",
            }

    def job_manifest(self, record: EERequestRecord, mode: BuildMode) -> dict[str, object]:
        short_id = record.id.split("-", maxsplit=1)[0]
        mode_suffix = {
            BuildMode.build_only: "build",
            BuildMode.stage_for_approval: "stage",
            BuildMode.publish_after_approval: "publish",
        }[mode]
        job_name = f"ee-builder-{short_id}-{mode_suffix}"
        push_image = mode == BuildMode.publish_after_approval
        env = [
            {"name": "EE_REQUEST_ID", "value": record.id},
            {"name": "DATA_DIR", "value": "/data"},
            {"name": "BUILD_MODE", "value": mode.value},
            {"name": "IMAGE_REF", "value": record.registry_target or ""},
            {"name": "PUSH_IMAGE", "value": str(push_image).lower()},
        ]
        if push_image:
            env.append({"name": "DOCKER_CONFIG", "value": "/workspace/.docker"})

        manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self.namespace,
                "labels": {
                    "app": "ee-builder",
                    "ee-request-id": record.id,
                    "ee-name": record.ee_name,
                },
            },
            "spec": {
                "backoffLimit": 0,
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "ee-builder",
                            "ee-request-id": record.id,
                        }
                    },
                    "spec": {
                        "restartPolicy": "Never",
                        "serviceAccountName": "ee-factory-api",
                        "securityContext": {
                            "fsGroup": 10001,
                            "fsGroupChangePolicy": "OnRootMismatch",
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                        "containers": [
                            {
                                "name": "builder",
                                "image": "ee-factory-lab/builder:local",
                                "imagePullPolicy": "IfNotPresent",
                                "securityContext": {
                                    "privileged": True,
                                    "runAsUser": 0,
                                    "runAsGroup": 0,
                                    "allowPrivilegeEscalation": True,
                                },
                                "env": env,
                                "volumeMounts": [
                                    {"name": "ee-factory-data", "mountPath": "/data"},
                                    {"name": "registry-auth", "mountPath": "/workspace/.docker", "readOnly": True},
                                ],
                            }
                        ],
                        "volumes": [
                            {
                                "name": "ee-factory-data",
                                "persistentVolumeClaim": {"claimName": "ee-factory-data"},
                            },
                            {
                                "name": "registry-auth",
                                "secret": {
                                    "secretName": "quay-docker-config",
                                    "optional": False,
                                    "items": [{"key": ".dockerconfigjson", "path": "config.json"}],
                                },
                            },
                        ],
                    },
                },
            },
        }
        if not push_image:
            manifest = deepcopy(manifest)
            manifest["spec"]["template"]["spec"]["volumes"] = [
                volume for volume in manifest["spec"]["template"]["spec"]["volumes"] if volume["name"] != "registry-auth"
            ]
            manifest["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = [
                mount
                for mount in manifest["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]
                if mount["name"] != "registry-auth"
            ]
        return manifest

    def _require_registry_secret(self) -> None:
        api = client.CoreV1Api()
        try:
            api.read_namespaced_secret(name="quay-docker-config", namespace=self.namespace)
        except ApiException as exc:
            if exc.status == 404:
                raise RuntimeError(
                    "Quay registry Secret 'quay-docker-config' was not found. "
                    "Run scripts/create-quay-secret.ps1 before publishing."
                ) from exc
            raise

    def _load_config(self) -> None:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException as exc:
                raise RuntimeError("No Kubernetes configuration available") from exc

    def _format_api_exception(self, exc: ApiException) -> str:
        reason = exc.reason or "Kubernetes API error"
        if not exc.body:
            return f"{exc.status} {reason}"
        try:
            body = json.loads(exc.body)
        except json.JSONDecodeError:
            return f"{exc.status} {reason}"
        message = body.get("message") if isinstance(body, dict) else None
        if isinstance(message, str):
            return f"{exc.status} {reason}: {message}"
        return f"{exc.status} {reason}"
