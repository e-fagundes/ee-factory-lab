from __future__ import annotations

from pathlib import Path

from worker.image_builder_service import ImageBuilderService


class PublisherService:
    def __init__(self, image_builder: ImageBuilderService | None = None) -> None:
        self.image_builder = image_builder or ImageBuilderService()

    def publish(self, workspace: Path, image_ref: str, log_path: Path) -> dict[str, str | None]:
        return self.image_builder.publish_image(workspace, image_ref, log_path)
