from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./awd-dev.db"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: str = ""
    flag_hmac_secret: str = ""
    session_secure_cookie: bool = True
    session_ttl_seconds: int = 86400
    allow_in_memory_redis: bool = False
    allow_mock_docker: bool = False
    mock_target_root: str = "/tmp/awd-targets"

    match_round_seconds: int = 300
    flag_grace_seconds: int = 30
    initial_team_score: int = 1000
    attack_reward: int = 100
    victim_penalty: int = 50
    health_interval_seconds: int = 30
    max_auto_restarts: int = 2
    flag_submit_rate_per_second: int = 10

    terminal_ssh_username: str = "player"
    terminal_ssh_password: str = ""
    terminal_ssh_private_key: str = ""
    gateway_image: str = "linuxserver/openssh-server:latest"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_production(self):
        if self.environment == "production":
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("production DATABASE_URL must use PostgreSQL asyncpg")
            if self.allow_in_memory_redis or self.allow_mock_docker:
                raise ValueError("in-memory Redis and mock Docker are development-only")
            if len(self.session_secret) < 32 or len(self.flag_hmac_secret) < 32:
                raise ValueError("production secrets must contain at least 32 characters")
            if not self.session_secure_cookie:
                raise ValueError("Secure session cookie cannot be disabled in production")
            if not self.terminal_ssh_password:
                raise ValueError("terminal SSH password master secret is required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
