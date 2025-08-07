import os
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # 데이터베이스 설정
    POSTGRES_HOST: str
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    # 데이터베이스 연결 풀 설정
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 0
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # 애플리케이션 설정
    APP_NAME: str = "LinkyBoard AI"
    DEBUG: bool = False
    
    # API 설정
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS 설정
    ALLOWED_HOSTS: list = ["*"]
    
    @field_validator("POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    @classmethod
    def validate_required_fields(cls, v, info):
        if not v:
            field_name = info.field_name
            raise ValueError(f"{field_name}는 필수입니다")
        return v
    
    @property
    def database_url(self) -> str:
        """비동기 데이터베이스 URL"""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def sync_database_url(self) -> str:
        """동기 데이터베이스 URL (Alembic용)"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "extra": "ignore"
    }


# 설정 인스턴스 생성
settings = Settings()
