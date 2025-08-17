from typing import List
import openai
from app.ai.embedding.interfaces import EmbeddingGenerator
from app.core.config import settings
from app.core.logging import get_logger
from app.metrics import count_tokens, record_embedding_usage

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
    
    async def generate(self, text: str, user_id: int = None) -> List[float]:
        """텍스트에 대한 임베딩 벡터 생성 (WTU 계측 포함)"""
        try:
            logger.bind(ai=True).info(f"Generating embedding for text (length: {len(text)})")
            
            # 텍스트 길이 검증
            if len(text.strip()) == 0:
                raise ValueError("Empty text provided for embedding")
            
            # 토큰 수 계산 (실제 요청 전)
            embed_tokens = count_tokens(text, self.model_name)
            logger.bind(ai=True).info(f"Estimated tokens: {embed_tokens}")
            
            # 토큰 수 제한 검증
            max_tokens = 8192  # OpenAI 임베딩 모델 제한
            
            if embed_tokens > max_tokens:
                logger.warning(f"Text may exceed token limit (estimated: {embed_tokens}, max: {max_tokens})")
                # 안전하게 자르기 (토큰 기준으로 더 정확하게)
                safe_char_count = int(len(text) * (max_tokens / embed_tokens * 0.9))  # 10% 여유
                text = text[:safe_char_count]
                embed_tokens = count_tokens(text, self.model_name)  # 재계산
                logger.info(f"Text truncated, new estimated tokens: {embed_tokens}")
            
            # OpenAI API 호출
            response = await self.client.embeddings.create(
                model=self.model_name,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            # WTU 사용량 기록 (user_id가 있을 때만)
            if user_id:
                try:
                    await record_embedding_usage(
                        user_id=user_id,
                        embed_tokens=embed_tokens,
                        embedding_model=self.model_name
                    )
                    logger.bind(ai=True).info(f"WTU usage recorded for user {user_id}: {embed_tokens} tokens")
                except Exception as wtu_error:
                    # WTU 기록 실패는 임베딩 생성을 방해하지 않음
                    logger.bind(ai=True).warning(f"Failed to record WTU usage: {wtu_error}")
            
            logger.bind(ai=True).info(
                f"Generated embedding with {len(embedding)} dimensions, "
                f"tokens: {embed_tokens}, model: {self.model_name}"
            )
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
