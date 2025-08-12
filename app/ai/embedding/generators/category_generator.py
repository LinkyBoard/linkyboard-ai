from typing import List, Optional
from app.ai.embedding.generators.openai_generator import OpenAIEmbeddingGenerator
from app.core.logging import get_logger

logger = get_logger(__name__)


def _preprocess_category(category: str) -> str:
    """카테고리 전처리"""
    # 카테고리 정규화
    processed = category.strip()

    # 공백 정리
    processed = ' '.join(processed.split())

    return processed


class CategoryEmbeddingGenerator(OpenAIEmbeddingGenerator):
    """카테고리 전용 임베딩 생성기"""

    def __init__(self):
        super().__init__()
        logger.info("Category embedding generator initialized")

    async def generate_category_embedding(
            self,
            category: str,
            description: Optional[str] = None
    ) -> List[float]:
        """카테고리에 최적화된 임베딩 생성"""
        try:
            # 카테고리 전처리
            processed_category = _preprocess_category(category)

            if not processed_category:
                raise ValueError(f"Invalid category after preprocessing: '{category}'")

            # 카테고리 컨텍스트 구성
            if description:
                context_text = f"카테고리: {processed_category}\n설명: {description}"
            else:
                context_text = f"카테고리: {processed_category}"

            logger.bind(ai=True).info(f"Generating embedding for category: '{category}'")

            # 부모 클래스의 generate 메서드 사용
            embedding = await self.generate(context_text)

            return embedding

        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate category embedding for '{category}': {str(e)}")
            raise Exception(f"카테고리 임베딩 생성 실패: {str(e)}")

    async def generate_batch_category_embeddings(
            self,
            categories: List[str],
            descriptions: Optional[List[str]] = None
    ) -> List[List[float]]:
        """카테고리 배치 임베딩 생성"""
        embeddings = []

        for i, category in enumerate(categories):
            try:
                description = descriptions[i] if descriptions and i < len(descriptions) else None
                embedding = await self.generate_category_embedding(category, description)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to generate embedding for category '{category}': {str(e)}")
                embeddings.append(None)

        return embeddings
