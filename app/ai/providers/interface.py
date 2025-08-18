"""
AI Provider Interface

모든 AI 제공업체가 구현해야 하는 공통 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AIResponse:
    """AI 응답 표준화 클래스"""
    content: str
    input_tokens: int
    output_tokens: int
    model_used: str
    provider: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TokenUsage:
    """토큰 사용량 정보"""
    input_tokens: int
    output_tokens: int
    total_tokens: int


class AIProviderInterface(ABC):
    """AI Provider 공통 인터페이스"""
    
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.provider_name = self._get_provider_name()
    
    @abstractmethod
    def _get_provider_name(self) -> str:
        """제공업체 이름 반환"""
        pass
    
    @abstractmethod
    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> AIResponse:
        """
        채팅 완성 생성
        
        Args:
            messages: 채팅 메시지 리스트
            model: 사용할 모델명
            max_tokens: 최대 출력 토큰 수
            temperature: 창의성 정도 (0.0~1.0)
            
        Returns:
            AIResponse 객체
        """
        pass
    
    @abstractmethod
    async def generate_webpage_tags(
        self,
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        model: str = None,
        **kwargs
    ) -> List[str]:
        """
        웹페이지 태그 생성
        
        Args:
            summary: 웹페이지 요약
            similar_tags: 유사한 기존 태그들
            tag_count: 생성할 태그 수
            model: 사용할 모델명
            
        Returns:
            생성된 태그 리스트
        """
        pass
    
    @abstractmethod
    async def recommend_webpage_category(
        self,
        summary: str,
        similar_categories: List[str] = None,
        model: str = None,
        **kwargs
    ) -> str:
        """
        웹페이지 카테고리 추천
        
        Args:
            summary: 웹페이지 요약
            similar_categories: 유사한 기존 카테고리들
            model: 사용할 모델명
            
        Returns:
            추천 카테고리명
        """
        pass
    
    @abstractmethod
    async def generate_webpage_summary(
        self,
        url: str,
        html_content: str,
        model: str = None,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """
        웹페이지 요약 생성
        
        Args:
            url: 웹페이지 URL
            html_content: HTML 내용
            model: 사용할 모델명
            max_tokens: 최대 출력 토큰 수
            
        Returns:
            웹페이지 요약
        """
        pass
    
    @abstractmethod
    async def generate_youtube_summary(
        self,
        title: str,
        transcript: str,
        model: str = None,
        **kwargs
    ) -> str:
        """
        YouTube 동영상 요약 생성
        
        Args:
            title: 동영상 제목
            transcript: 동영상 스크립트
            model: 사용할 모델명
            
        Returns:
            동영상 요약
        """
        pass
    
    @abstractmethod
    async def generate_youtube_tags(
        self,
        title: str,
        summary: str,
        tag_count: int = 5,
        model: str = None,
        **kwargs
    ) -> List[str]:
        """
        YouTube 동영상 태그 생성
        
        Args:
            title: 동영상 제목
            summary: 동영상 요약
            tag_count: 생성할 태그 수
            model: 사용할 모델명
            
        Returns:
            생성된 태그 리스트
        """
        pass
    
    @abstractmethod
    async def recommend_youtube_category(
        self,
        title: str,
        summary: str,
        model: str = None,
        **kwargs
    ) -> str:
        """
        YouTube 동영상 카테고리 추천
        
        Args:
            title: 동영상 제목
            summary: 동영상 요약
            model: 사용할 모델명
            
        Returns:
            추천 카테고리명
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str, model: str) -> int:
        """
        텍스트의 토큰 수 계산
        
        Args:
            text: 토큰 수를 계산할 텍스트
            model: 사용할 모델명
            
        Returns:
            토큰 수
        """
        pass
    
    def is_available(self) -> bool:
        """제공업체 사용 가능 여부 확인"""
        return bool(self.api_key)