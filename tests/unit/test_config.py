"""Config 설정 검증 테스트"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


class TestDevelopmentConfig:
    """개발 환경 설정 테스트"""

    def test_development_allows_default_keys(self):
        """개발 환경에서는 기본 키 허용"""
        config = Settings(
            app_env="development",
            internal_api_key="your-internal-api-key-here",
            secret_key="your-secret-key-here",
        )
        assert config.is_development
        assert config.internal_api_key == "your-internal-api-key-here"


class TestProductionConfig:
    """프로덕션 환경 설정 검증 테스트"""

    def test_production_rejects_default_internal_api_key(self):
        """프로덕션에서 기본 Internal API Key 거부"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                app_env="production",
                internal_api_key="your-internal-api-key-here",
                secret_key="valid-secret-key-with-32-characters-long",
            )

        assert "INTERNAL_API_KEY" in str(exc_info.value)

    def test_production_rejects_short_internal_api_key(self):
        """프로덕션에서 짧은 Internal API Key 거부"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                app_env="production",
                internal_api_key="short-key",
                secret_key="valid-secret-key-with-32-characters-long",
            )

        assert "32 characters" in str(exc_info.value)

    def test_production_rejects_default_secret_key(self):
        """프로덕션에서 기본 Secret Key 거부"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                app_env="production",
                internal_api_key="valid-internal-api-key-with-32-chars",
                secret_key="your-secret-key-here",
            )

        assert "SECRET_KEY" in str(exc_info.value)

    def test_production_rejects_short_secret_key(self):
        """프로덕션에서 짧은 Secret Key 거부"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                app_env="production",
                internal_api_key="valid-internal-api-key-with-32-chars",
                secret_key="short",
            )

        assert "32 characters" in str(exc_info.value)

    def test_production_accepts_valid_keys(self):
        """프로덕션에서 유효한 키 허용"""
        config = Settings(
            app_env="production",
            internal_api_key=(
                "valid-internal-api-key-with-32-characters-minimum"
            ),
            secret_key="valid-secret-key-with-32-characters-or-more",
        )
        assert config.is_production
        assert len(config.internal_api_key) >= 32
        assert len(config.secret_key) >= 32
