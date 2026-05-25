from app.builders.kubernetes_builder import KubernetesBuildOrchestrator
from app.models.ee_request import AnsibleCollection, BuildMode, EERequestRecord


def record() -> EERequestRecord:
    return EERequestRecord(
        id="abc12345-0000-0000-0000-000000000000",
        ee_name="ee-ansible-windows",
        description="Windows automation",
        purpose="Run Windows automation",
        automation_domain="windows",
        base_image="quay.io/rockylinux/rockylinux:9",
        ansible_core_version="2.15.13",
        ansible_runner_version="2.4.0",
        collections=[AnsibleCollection(name="ansible.windows", version="2.5.0")],
        python_dependencies=["pywinrm==0.5.0"],
        system_dependencies=[],
        image_tag="0.1.0",
        registry_namespace="example-platform",
        publish_target="quay.io",
        registry_target="quay.io/example-platform/ee-ansible-windows:0.1.0",
        created_at="2026-05-24T00:00:00Z",
        updated_at="2026-05-24T00:00:00Z",
    )


def test_build_only_job_does_not_mount_registry_secret():
    manifest = KubernetesBuildOrchestrator().job_manifest(record(), BuildMode.build_only)
    volumes = manifest["spec"]["template"]["spec"]["volumes"]
    env = manifest["spec"]["template"]["spec"]["containers"][0]["env"]
    assert all(volume["name"] != "registry-auth" for volume in volumes)
    assert all(item["name"] != "DOCKER_CONFIG" for item in env)


def test_publish_job_mounts_registry_secret():
    manifest = KubernetesBuildOrchestrator().job_manifest(record(), BuildMode.publish_after_approval)
    volumes = manifest["spec"]["template"]["spec"]["volumes"]
    env = manifest["spec"]["template"]["spec"]["containers"][0]["env"]
    assert any(volume["name"] == "registry-auth" for volume in volumes)
    assert any(item["name"] == "DOCKER_CONFIG" for item in env)
    registry_secret = next(volume for volume in volumes if volume["name"] == "registry-auth")
    assert registry_secret["secret"]["optional"] is False


def test_job_names_are_unique_per_build_mode():
    orchestrator = KubernetesBuildOrchestrator()
    names = {
        orchestrator.job_manifest(record(), BuildMode.build_only)["metadata"]["name"],
        orchestrator.job_manifest(record(), BuildMode.stage_for_approval)["metadata"]["name"],
        orchestrator.job_manifest(record(), BuildMode.publish_after_approval)["metadata"]["name"],
    }
    assert names == {"ee-builder-abc12345-build", "ee-builder-abc12345-stage", "ee-builder-abc12345-publish"}
