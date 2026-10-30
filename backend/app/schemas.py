from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .models import Role


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=4, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TeamCreate(BaseModel):
    team_no: int = Field(ge=1, le=15)
    name: str = Field(min_length=1, max_length=80)
    invite_code: str | None = Field(default=None, min_length=4, max_length=64)


class TeamUpdate(BaseModel):
    team_no: int | None = Field(default=None, ge=1, le=15)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    invite_code: str | None = Field(default=None, min_length=4, max_length=64)
    status: Literal["ACTIVE", "DISABLED"] | None = None
    reset_score: bool = False


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.PLAYER
    team_id: str | None = None


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: Role | None = None
    team_id: str | None = None
    status: Literal["ACTIVE", "DISABLED"] | None = None

    @field_validator("team_id", mode="before")
    @classmethod
    def empty_team_is_none(cls, value):
        return None if value == "" else value


class MatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    starts_at: datetime
    ends_at: datetime
    round_seconds: int = Field(default=300, ge=180, le=600)
    grace_seconds: int = Field(default=30, ge=0, le=300)


class MatchUpdate(BaseModel):
    name: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    round_seconds: int | None = Field(default=None, ge=180, le=600)
    grace_seconds: int | None = Field(default=None, ge=0, le=300)


class FreezeRequest(BaseModel):
    frozen: bool


class ServiceCreate(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9-]+$", max_length=40)
    name: str
    service_no: int = Field(ge=1, le=99)
    protocol: Literal["TCP", "HTTP"] = "TCP"
    internal_port: int = Field(ge=1, le=65535)
    public_base_port: int = Field(ge=1, le=65535)
    flag_path: str = "/data/flag"
    image: str = Field(min_length=1)
    check_config: dict[str, Any] = Field(default_factory=dict)


class TargetInitializeRequest(BaseModel):
    team_ids: list[str] | None = None
    service_ids: list[str] | None = None
    start: bool = True


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1)
    level: Literal["INFO", "WARNING", "CRITICAL"] = "INFO"
    is_pinned: bool = False


class AnnouncementUpdate(BaseModel):
    is_pinned: bool | None = None
    status: Literal["PUBLISHED", "WITHDRAWN"] | None = None


class FlagSubmitRequest(BaseModel):
    flag: str = Field(min_length=1, max_length=512)
    request_id: str = Field(min_length=8, max_length=80)


class ScoreAdjustRequest(BaseModel):
    team_id: str
    delta: int
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("delta")
    @classmethod
    def delta_must_not_be_zero(cls, value):
        if value == 0:
            raise ValueError("delta must not be zero")
        return value
