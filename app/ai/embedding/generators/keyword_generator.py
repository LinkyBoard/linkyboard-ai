import unicodedata
import re
from typing import List
from app.ai.embedding.generators.openai_generator import OpenAIEmbeddingGenerator
from app.core.logging import get_logger

logger = get_logger(__name__)


def _preprocess_keyword(keyword: str) -> str:
    """키워드 전처리"""
    # TODO : 형태소 분석기 연결하여 명사만 추출하도록 업데이트
    # 1. 유니코드 정규화 및 앞뒤 공백 제거
    processed = unicodedata.normalize('NFC', keyword.strip())

    # 2. 영문 소문자 변환
    processed = processed.lower()

    # 3. 특수문자를 공백으로 변환 (한글, 영문, 숫자, 하이픈, 언더스코어 제외)
    processed = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ\-_]', ' ', processed)

    # 4. 여러 개의 공백을 하나로 축소
    processed = re.sub(r'\s+', ' ', processed)

    # 5. 공백을 하이픈으로 변경
    processed = processed.replace(' ', '-')

    # 6. 연속된 하이픈이나 언더스코어를 단일 하이픈으로 변경
    processed = re.sub(r'[-_]+', '-', processed)

    # 7. 앞뒤 하이픈 제거
    processed = processed.strip('-')

    return processed


class KeywordEmbeddingGenerator(OpenAIEmbeddingGenerator):
    """키워드 전용 임베딩 생성기"""
    
    def __init__(self):
        super().__init__()
        logger.info("Keyword embedding generator initialized")

    async def generate_keyword_embedding(self, keyword: str) -> List[float]:
        """키워드에 최적화된 임베딩 생성"""
        try:
            # 키워드 전처리
            processed_keyword = _preprocess_keyword(keyword)
            
            if not processed_keyword:
                raise ValueError(f"Invalid keyword after preprocessing: '{keyword}'")
            
            # 키워드 컨텍스트 추가 (선택적)
            # 더 좋은 임베딩을 위해 키워드를 문장 형태로 변환
            context_text = f"주제: {processed_keyword}"
            
            logger.bind(ai=True).info(f"Generating embedding for keyword: '{keyword}' -> '{processed_keyword}'")
            
            # 부모 클래스의 generate 메서드 사용
            embedding = await self.generate(context_text)
            
            return embedding
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate keyword embedding for '{keyword}': {str(e)}")
            raise Exception(f"키워드 임베딩 생성 실패: {str(e)}")
    
    async def generate_batch_keyword_embeddings(self, keywords: List[str]) -> List[List[float]]:
        """키워드 배치 임베딩 생성"""
        embeddings = []
        
        for keyword in keywords:
            try:
                embedding = await self.generate_keyword_embedding(keyword)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to generate embedding for keyword '{keyword}': {str(e)}")
                # 실패한 키워드는 None으로 처리하거나 기본값 사용
                embeddings.append(None)
        
        return embeddings
