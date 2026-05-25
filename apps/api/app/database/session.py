from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


class EERequestRow(Base):
    __tablename__ = "ee_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ee_name: Mapped[str] = mapped_column(String(128), index=True)
    automation_domain: Mapped[str] = mapped_column(String(128), index=True)
    image_tag: Mapped[str] = mapped_column(String(128))
    registry_target: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(128), index=True)
    build_status: Mapped[str] = mapped_column(String(128), index=True)
    publish_status: Mapped[str] = mapped_column(String(128), index=True)
    record_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def create_session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}
    engine = create_engine(settings.resolved_database_url, future=True, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False, future=True)


SessionLocal = create_session_factory()


def utc_now() -> datetime:
    return datetime.now(UTC)
