"""SQLAlchemy ORM models for the web application."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    site_profiles = relationship("SiteProfile", back_populates="user", cascade="all, delete-orphan")
    config = relationship(
        "UserConfig", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    archive_jobs = relationship("ArchiveJob", back_populates="user", cascade="all, delete-orphan")
    rss_feeds = relationship("RssFeed", back_populates="user", cascade="all, delete-orphan")
    scheduled_tasks = relationship(
        "ScheduledTask", back_populates="user", cascade="all, delete-orphan"
    )


class UserConfig(Base):
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False
    )
    pipeline_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ua_cycle_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ua_list_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=40)
    output_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="config")


class SiteProfile(Base):
    __tablename__ = "site_profiles"
    __table_args__ = (UniqueConstraint("user_id", "domain"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cookies_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ua_override: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    use_stealth: Mapped[bool] = mapped_column(Boolean, default=False)
    pipeline_overrides: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="site_profiles")


class ArchiveJob(Base):
    __tablename__ = "archive_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    output_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paywalled: Mapped[bool] = mapped_column(Boolean, default=False)
    paywall_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bypass_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bypass_cached: Mapped[bool] = mapped_column(Boolean, default=False)
    is_partial: Mapped[bool] = mapped_column(Boolean, default=False)
    step_log_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("site_profiles.id"), nullable=True
    )
    site_profile_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="archive_jobs")


class RssFeed(Base):
    __tablename__ = "rss_feeds"
    __table_args__ = (UniqueConstraint("user_id", "feed_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    feed_url: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("site_profiles.id"), nullable=True
    )
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="rss_feeds")
    items = relationship("FeedItem", back_populates="feed", cascade="all, delete-orphan")


class FeedItem(Base):
    __tablename__ = "feed_items"
    __table_args__ = (UniqueConstraint("feed_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    feed_id: Mapped[int] = mapped_column(Integer, ForeignKey("rss_feeds.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("archive_jobs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    feed = relationship("RssFeed", back_populates="items")


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    __table_args__ = (UniqueConstraint("user_id", "url", "cron_expression"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    site_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("site_profiles.id"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("archive_jobs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="scheduled_tasks")


def create_all() -> None:
    """Create all tables in the database."""
    from archiveinator.web.db import get_engine

    Base.metadata.create_all(bind=get_engine())
