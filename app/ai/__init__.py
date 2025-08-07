"""
AI 서비스 패키지 - OpenAI 및 기타 AI 모델 연동

이 패키지는 다양한 AI 서비스와의 연동을 담당합니다.
"""

from .openai_service import OpenAIService, openai_service

__all__ = [
    "OpenAIService", 
    "openai_service"
]