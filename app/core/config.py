from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "LinkyBoard AI"
    app_env: str = "development"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/linkyboard_ai"
    )
    database_echo: bool = False
    auto_migrate: bool = True  # 서버 시작 시 자동 마이그레이션 여부

    # Redis (TODO: Redis 클라이언트 구현 시 활성화)
    redis_url: str = "redis://localhost:6379/0"

    # Security (TODO: JWT 인증 구현 시 활성화)
    secret_key: str = "your-secret-key-here"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Internal API Key (Spring Boot 통신용)
    internal_api_key: str = "your-internal-api-key-here"

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # LLM Provider API Keys
    openai_api_key: str = "sk-your-openai-key-here"
    anthropic_api_key: str = "sk-ant-your-anthropic-key-here"
    google_api_key: str = "AIza-your-google-key-here"
    perplexity_api_key: str = "pplx-your-perplexity-key-here"

    # LangFuse Observability
    langfuse_secret_key: str = "sk-lf-your-secret-key-here"
    langfuse_public_key: str = "pk-lf-your-public-key-here"
    langfuse_host: str = "https://cloud.langfuse.com"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """프로덕션 환경에서 보안 설정 검증"""
        if not self.is_production:
            return self

        # Internal API Key 검증
        if self.internal_api_key == "your-internal-api-key-here":
            raise ValueError(
                "Production requires valid INTERNAL_API_KEY. "
                "Set it via environment variable."
            )

        if len(self.internal_api_key) < 32:
            raise ValueError(
                "INTERNAL_API_KEY must be at least 32 characters long "
                "for security."
            )

        # Secret Key 검증 (JWT 구현 시)
        if self.secret_key == "your-secret-key-here":
            raise ValueError(
                "Production requires valid SECRET_KEY. "
                "Set it via environment variable."
            )

        if len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long for security."
            )

        # LLM API 키 검증 (최소 1개 필요)
        has_llm_provider = any(
            [
                self.openai_api_key != "sk-your-openai-key-here",
                self.anthropic_api_key != "sk-ant-your-anthropic-key-here",
                self.google_api_key != "AIza-your-google-key-here",
            ]
        )
        if not has_llm_provider:
            raise ValueError(
                "Production requires at least one LLM provider API key. "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY."
            )

        return self

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """설정 인스턴스를 반환 (캐싱됨)"""
    return Settings()


settings = get_settings()
