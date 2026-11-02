import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uuid_str() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    PLAYER = "PLAYER"
    ADMIN = "ADMIN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class TeamStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class MatchStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"


class TargetStatus(str, enum.Enum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    UNHEALTHY = "UNHEALTHY"
    RESTARTING = "RESTARTING"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    STOPPED = "STOPPED"


class SubmissionResult(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    OWN_TEAM = "OWN_TEAM"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"
    MATCH_NOT_RUNNING = "MATCH_NOT_RUNNING"


class InjectStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class LedgerReason(str, enum.Enum):
    ATTACK = "ATTACK"
    BREACH = "BREACH"
    MANUAL_ADJUST = "MANUAL_ADJUST"


class AnnouncementStatus(str, enum.Enum):
    PUBLISHED = "PUBLISHED"
    WITHDRAWN = "WITHDRAWN"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    team_no: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    invite_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    current_score: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    attack_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    breached_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[TeamStatus] = mapped_column(Enum(TeamStatus, native_enum=False), default=TeamStatus.ACTIVE, nullable=False)
    last_score_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="team")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False), default=Role.PLAYER, nullable=False)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), index=True)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus, native_enum=False), default=UserStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    team: Mapped[Team | None] = relationship(back_populates="users")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[MatchStatus] = mapped_column(Enum(MatchStatus, native_enum=False), default=MatchStatus.DRAFT, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    round_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    grace_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    score_frozen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    freeze_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("round_seconds >= 180 AND round_seconds <= 600", name="ck_match_round_seconds"),
        CheckConstraint("grace_seconds >= 0", name="ck_match_grace_seconds"),
        CheckConstraint("ends_at > starts_at", name="ck_match_time_range"),
    )


class Service(Base):
    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    service_no: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), default="TCP", nullable=False)
    internal_port: Mapped[int] = mapped_column(Integer, nullable=False)
    public_base_port: Mapped[int] = mapped_column(Integer, nullable=False)
    flag_path: Mapped[str] = mapped_column(String(255), default="/data/flag", nullable=False)
    image: Mapped[str] = mapped_column(String(255), nullable=False)
    check_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    container_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    attack_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    public_port: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    volume_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    gateway_host: Mapped[str] = mapped_column(String(120), nullable=False)
    gateway_port: Mapped[int] = mapped_column(Integer, default=2222, nullable=False)
    status: Mapped[TargetStatus] = mapped_column(Enum(TargetStatus, native_enum=False), default=TargetStatus.CREATED, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    restart_history: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    unhealthy_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_unhealthy_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    team: Mapped[Team] = relationship()
    service: Mapped[Service] = relationship()

    __table_args__ = (UniqueConstraint("team_id", "service_id", name="uq_target_team_service"),)


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True, nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    __table_args__ = (UniqueConstraint("match_id", "round_no", name="uq_round_match_no"),)


class Flag(Base):
    __tablename__ = "flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id", ondelete="CASCADE"), index=True, nullable=False)
    flag_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    inject_status: Mapped[InjectStatus] = mapped_column(Enum(InjectStatus, native_enum=False), default=InjectStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    round: Mapped[Round] = relationship()
    target: Mapped[Target] = relationship()

    __table_args__ = (UniqueConstraint("round_id", "target_id", name="uq_flag_round_target"),)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    attacker_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True, nullable=False)
    victim_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    flag_id: Mapped[str | None] = mapped_column(ForeignKey("flags.id"), index=True)
    result: Mapped[SubmissionResult] = mapped_column(Enum(SubmissionResult, native_enum=False), nullable=False)
    attacker_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    victim_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    attacker_team: Mapped[Team] = relationship(foreign_keys=[attacker_team_id])
    victim_team: Mapped[Team | None] = relationship(foreign_keys=[victim_team_id])
    flag: Mapped[Flag | None] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_submission_user_request"),
        Index(
            "uq_valid_submission",
            "flag_id",
            "attacker_team_id",
            unique=True,
            sqlite_where=text("result = 'ACCEPTED'"),
            postgresql_where=text("result = 'ACCEPTED'"),
        ),
    )


class ScoreLedger(Base):
    __tablename__ = "score_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True, nullable=False)
    submission_id: Mapped[str | None] = mapped_column(ForeignKey("submissions.id"), index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    score_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[LedgerReason] = mapped_column(Enum(LedgerReason, native_enum=False), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("submission_id", "team_id", "reason", name="uq_ledger_submission_team_reason"),
    )


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)
    status: Mapped[AnnouncementStatus] = mapped_column(Enum(AnnouncementStatus, native_enum=False), default=AnnouncementStatus.PUBLISHED, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    object_type: Mapped[str] = mapped_column(String(60), nullable=False)
    object_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_ip: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    request_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
