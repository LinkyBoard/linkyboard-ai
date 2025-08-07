from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ChunkData:
    """청크 데이터 구조"""
    content: str
    chunk_number: int
    start_position: int
    end_position: int
    chunk_size: int
    token_count: Optional[int] = None


@dataclass
class EmbeddingResult:
    """임베딩 결과 구조"""
    chunk_data: ChunkData
    embedding_vector: List[float]
    model_name: str
    model_version: str


class ContentProcessor(ABC):
    """콘텐츠 전처리 인터페이스"""
    
    @abstractmethod
    async def process(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """콘텐츠를 전처리하여 텍스트 추출"""
        pass
    
    @abstractmethod
    def get_content_type(self) -> str:
        """지원하는 콘텐츠 타입 반환"""
        pass


class ChunkingStrategy(ABC):
    """청킹 전략 인터페이스"""
    
    @abstractmethod
    async def chunk(self, content: str, max_chunk_size: int = 15000) -> List[ChunkData]:
        """콘텐츠를 청크로 분할"""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """청킹 전략 이름 반환"""
        pass


class EmbeddingGenerator(ABC):
    """임베딩 생성기 인터페이스"""
    
    @abstractmethod
    async def generate(self, text: str) -> List[float]:
        """텍스트에 대한 임베딩 벡터 생성"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """모델 이름 반환"""
        pass
    
    @abstractmethod
    def get_model_version(self) -> str:
        """모델 버전 반환"""
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """임베딩 차원 수 반환"""
        pass
