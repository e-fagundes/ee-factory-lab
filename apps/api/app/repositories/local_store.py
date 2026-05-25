import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import select

from app.core.config import get_settings
from app.database.session import EERequestRow, SessionLocal, utc_now
from app.models.ee_request import EERequestCreate, EERequestRecord


class LocalStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.builds_dir = self.settings.resolved_data_dir / "builds"
        self.metadata_dir = self.settings.resolved_data_dir / "metadata"
        self.builds_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def create_request(self, payload: EERequestCreate) -> EERequestRecord:
        now = datetime.now(UTC).isoformat()
        request_id = str(uuid4())
        workspace = self.builds_dir / request_id
        (workspace / "logs").mkdir(parents=True, exist_ok=True)
        (workspace / "context").mkdir(parents=True, exist_ok=True)
        for log_name in ("validation.log", "build.log", "publish.log"):
            (workspace / "logs" / log_name).touch()
        record = EERequestRecord(
            **payload.model_dump(),
            id=request_id,
            created_at=now,
            updated_at=now,
            workspace_path=str(workspace),
            registry_target=f"{payload.publish_target}/{payload.registry_namespace}/{payload.ee_name}:{payload.image_tag}",
            validation_log_path=str(workspace / "logs" / "validation.log"),
            build_log_path=str(workspace / "logs" / "build.log"),
            publish_log_path=str(workspace / "logs" / "publish.log"),
        )
        self.save_record(record)
        self.write_json(request_id, "request.json", payload.model_dump())
        return record

    def save_record(self, record: EERequestRecord) -> None:
        record.updated_at = datetime.now(UTC).isoformat()
        self._upsert_db_record(record)
        self._record_path(record.id).write_text(record.model_dump_json(indent=2), encoding="utf-8")

    def get_request(self, request_id: str) -> EERequestRecord:
        with SessionLocal() as session:
            row = session.get(EERequestRow, request_id)
            if row:
                return EERequestRecord.model_validate_json(row.record_json)
        path = self._record_path(request_id)
        if not path.exists():
            raise FileNotFoundError(request_id)
        return EERequestRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list_requests(self) -> list[EERequestRecord]:
        adapter = TypeAdapter(list[EERequestRecord])
        with SessionLocal() as session:
            rows = session.execute(select(EERequestRow).order_by(EERequestRow.updated_at)).scalars().all()
            if rows:
                return adapter.validate_python(
                    [EERequestRecord.model_validate_json(row.record_json) for row in rows]
                )
        records = [
            EERequestRecord.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.metadata_dir.glob("*.json"))
        ]
        return adapter.validate_python(records)

    def write_text(self, request_id: str, relative_path: str, content: str) -> Path:
        path = self.builds_dir / request_id / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, request_id: str, relative_path: str, payload: object) -> Path:
        return self.write_text(request_id, relative_path, json.dumps(payload, indent=2, sort_keys=True))

    def read_text(self, request_id: str, relative_path: str) -> str:
        path = self.builds_dir / request_id / relative_path
        return path.read_text(encoding="utf-8")

    def read_json(self, request_id: str, relative_path: str) -> object:
        return json.loads(self.read_text(request_id, relative_path))

    def exists(self, request_id: str, relative_path: str) -> bool:
        return (self.builds_dir / request_id / relative_path).exists()

    def _record_path(self, request_id: str) -> Path:
        return self.metadata_dir / f"{request_id}.json"

    def _upsert_db_record(self, record: EERequestRecord) -> None:
        created_at = _parse_datetime(record.created_at)
        updated_at = _parse_datetime(record.updated_at)
        with SessionLocal() as session:
            row = session.get(EERequestRow, record.id)
            if row is None:
                row = EERequestRow(
                    id=record.id,
                    ee_name=record.ee_name,
                    automation_domain=record.automation_domain,
                    image_tag=record.image_tag,
                    registry_target=record.registry_target,
                    status=record.status,
                    build_status=record.build_status,
                    publish_status=record.publish_status,
                    record_json=record.model_dump_json(),
                    created_at=created_at,
                    updated_at=updated_at,
                )
                session.add(row)
            else:
                row.ee_name = record.ee_name
                row.automation_domain = record.automation_domain
                row.image_tag = record.image_tag
                row.registry_target = record.registry_target
                row.status = record.status
                row.build_status = record.build_status
                row.publish_status = record.publish_status
                row.record_json = record.model_dump_json()
                row.updated_at = updated_at
            session.commit()


def _parse_datetime(value: str):
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return utc_now()
