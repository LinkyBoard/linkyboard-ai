from typing import List
import openai
from app.ai.embedding.interfaces import EmbeddingGenerator
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIEmbeddingGenerator(EmbeddingGenerator):
    """OpenAI 임베딩 생성기"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model_name = settings.OPENAI_EMBEDDING_MODEL
        logger.info(f"OpenAI embedding generator initialized with model: {self.model_name}")
    
    def get_model_name(self) -> str:
        return self.model_name
    
    def get_model_version(self) -> str:
        # OpenAI 모델 버전은 보통 모델명에 포함되어 있음
        return "v1.0"  # 또는 설정에서 가져오기
    
    def get_embedding_dimension(self) -> int:
        # text-embedding-ada-002는 1536차원
        if "ada-002" in self.model_name:
            return 1536
        elif "3-small" in self.model_name:
            return 1536
        elif "3-large" in self.model_name:
            return 3072
        else:
            return 1536  # 기본값
    
    async def generate(self, text: str) -> List[float]:
        """텍스트에 대한 임베딩 벡터 생성"""
        try:
            logger.bind(ai=True).info(f"Generating embedding for text (length: {len(text)})")
            
            # 텍스트 길이 검증
            if len(text.strip()) == 0:
                raise ValueError("Empty text provided for embedding")
            
            # 토큰 수 추정 및 검증
            estimated_tokens = len(text) // 3
            max_tokens = 8192  # OpenAI 임베딩 모델 제한
            
            if estimated_tokens > max_tokens:
                logger.warning(f"Text may exceed token limit (estimated: {estimated_tokens}, max: {max_tokens})")
                # 안전하게 자르기
                safe_length = max_tokens * 3
                text = text[:safe_length]
                logger.info(f"Text truncated to {len(text)} characters")
            
            response = await self.client.embeddings.create(
                model=self.model_name,
                input=text
            )
            
            embedding = response.data[0].embedding
            logger.bind(ai=True).info(f"Generated embedding with {len(embedding)} dimensions")
            return embedding
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate embedding: {str(e)}")
            raise Exception(f"OpenAI 임베딩 생성 실패: {str(e)}")


class MockEmbeddingGenerator(EmbeddingGenerator):
    """테스트용 Mock 임베딩 생성기"""
    
    def get_model_name(self) -> str:
        return "mock-embedding-model"
    
    def get_model_version(self) -> str:
        return "test-1.0"
    
    def get_embedding_dimension(self) -> int:
        return 1536
    
    async def generate(self, text: str) -> List[float]:
        """Mock 임베딩 생성 (테스트용)"""
        logger.info(f"Generating mock embedding for text (length: {len(text)})")
        
        # 텍스트 해시를 기반으로 일관된 벡터 생성
        import hashlib
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # 해시를 기반으로 1536차원 벡터 생성
        embedding = []
        for i in range(1536):
            # 해시의 각 문자를 사용해서 -1.0 ~ 1.0 범위의 값 생성
            char_value = ord(text_hash[i % len(text_hash)])
            normalized_value = (char_value - 128) / 128.0
            embedding.append(normalized_value)
        
        return embedding
