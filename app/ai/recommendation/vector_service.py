import numpy as np
from typing import List, Dict, Optional, Tuple
from app.core.logging import get_logger
from app.ai.embedding.generators.keyword_generator import KeywordEmbeddingGenerator
from app.ai.embedding.generators.category_generator import CategoryEmbeddingGenerator

logger = get_logger(__name__)


class VectorProcessingService:
    """벡터 처리 서비스 - 임베딩 저장, 유사도 계산 등"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.keyword_generator = KeywordEmbeddingGenerator()
        self.category_generator = CategoryEmbeddingGenerator()
        logger.info("Vector processing service initialized")
    
    async def store_keyword_with_embedding(self, keyword: str) -> int:
        """키워드와 임베딩을 DB에 저장"""
        try:
            # 이미 존재하는 키워드인지 확인
            existing = await self.db.fetch_one(
                "SELECT id FROM keywords WHERE keyword = $1", 
                keyword
            )
            
            if existing:
                logger.info(f"Keyword '{keyword}' already exists with id: {existing['id']}")
                return existing['id']
            
            # 새 키워드 임베딩 생성
            embedding = await self.keyword_generator.generate_keyword_embedding(keyword)
            
            # DB에 저장
            result = await self.db.fetch_one("""
                INSERT INTO keywords (keyword, embedding, frequency_global) 
                VALUES ($1, $2::vector, 1)
                RETURNING id
            """, keyword, embedding)
            
            logger.bind(ai=True).info(f"Stored keyword '{keyword}' with embedding, id: {result['id']}")
            return result['id']
            
        except Exception as e:
            logger.error(f"Failed to store keyword '{keyword}': {str(e)}")
            raise
    
    async def store_category_with_embedding(self, category: str, description: str = None) -> int:
        """카테고리와 임베딩을 DB에 저장"""
        try:
            # 이미 존재하는 카테고리인지 확인
            existing = await self.db.fetch_one(
                "SELECT id FROM categories WHERE name = $1", 
                category
            )
            
            if existing:
                logger.info(f"Category '{category}' already exists with id: {existing['id']}")
                return existing['id']
            
            # 새 카테고리 임베딩 생성
            embedding = await self.category_generator.generate_category_embedding(
                category, description
            )
            
            # DB에 저장
            result = await self.db.fetch_one("""
                INSERT INTO categories (name, embedding, description) 
                VALUES ($1, $2::vector, $3)
                RETURNING id
            """, category, embedding, description)
            
            logger.bind(ai=True).info(f"Stored category '{category}' with embedding, id: {result['id']}")
            return result['id']
            
        except Exception as e:
            logger.error(f"Failed to store category '{category}': {str(e)}")
            raise
    
    async def batch_store_keywords_with_embeddings(self, keywords: List[str]) -> List[int]:
        """키워드 배치 저장"""
        try:
            # 기존 키워드 확인
            existing_keywords = await self.db.fetch_all("""
                SELECT keyword, id FROM keywords WHERE keyword = ANY($1::text[])
            """, keywords)
            
            existing_map = {row['keyword']: row['id'] for row in existing_keywords}
            new_keywords = [kw for kw in keywords if kw not in existing_map]
            
            keyword_ids = []
            
            # 기존 키워드 ID 추가
            for keyword in keywords:
                if keyword in existing_map:
                    keyword_ids.append(existing_map[keyword])
                else:
                    keyword_ids.append(None)  # 나중에 채워질 예정
            
            if new_keywords:
                # 새 키워드들의 임베딩 배치 생성
                embeddings = await self.keyword_generator.generate_batch_keyword_embeddings(new_keywords)
                
                # DB에 배치 저장
                insert_data = []
                for keyword, embedding in zip(new_keywords, embeddings):
                    if embedding:  # 유효한 임베딩만
                        insert_data.append((keyword, embedding, 1))
                
                if insert_data:
                    new_ids = await self.db.fetch_all("""
                        INSERT INTO keywords (keyword, embedding, frequency_global)
                        SELECT * FROM unnest($1::text[], $2::vector[], $3::int[])
                        RETURNING id, keyword
                    """, 
                    [item[0] for item in insert_data],  # keywords
                    [item[1] for item in insert_data],  # embeddings
                    [item[2] for item in insert_data]   # frequencies
                    )
                    
                    # 새로 생성된 ID를 결과에 반영
                    new_id_map = {row['keyword']: row['id'] for row in new_ids}
                    
                    for i, keyword in enumerate(keywords):
                        if keyword_ids[i] is None and keyword in new_id_map:
                            keyword_ids[i] = new_id_map[keyword]
            
            logger.info(f"Batch stored {len(keywords)} keywords")
            return keyword_ids
            
        except Exception as e:
            logger.error(f"Failed to batch store keywords: {str(e)}")
            raise
    
    async def find_similar_keywords(self, target_keyword: str, limit: int = 10) -> List[Dict]:
        """유사한 키워드 찾기"""
        try:
            # 타겟 키워드 임베딩 생성
            target_embedding = await self.keyword_generator.generate_keyword_embedding(target_keyword)
            
            # 벡터 유사도 검색
            similar_keywords = await self.db.fetch_all("""
                SELECT 
                    keyword,
                    frequency_global,
                    1 - (embedding <=> $1::vector) as similarity_score
                FROM keywords
                WHERE embedding <=> $1::vector < 0.5  -- 유사도 임계값
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, target_embedding, limit)
            
            return [dict(row) for row in similar_keywords]
            
        except Exception as e:
            logger.error(f"Failed to find similar keywords for '{target_keyword}': {str(e)}")
            raise
    
    async def find_similar_categories(self, target_category: str, limit: int = 5) -> List[Dict]:
        """유사한 카테고리 찾기"""
        try:
            # 타겟 카테고리 임베딩 생성
            target_embedding = await self.category_generator.generate_category_embedding(target_category)
            
            # 벡터 유사도 검색
            similar_categories = await self.db.fetch_all("""
                SELECT 
                    name,
                    description,
                    1 - (embedding <=> $1::vector) as similarity_score
                FROM categories
                WHERE embedding <=> $1::vector < 0.3  -- 더 엄격한 임계값
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, target_embedding, limit)
            
            return [dict(row) for row in similar_categories]
            
        except Exception as e:
            logger.error(f"Failed to find similar categories for '{target_category}': {str(e)}")
            raise
    
    async def generate_content_embedding(self, content_id: int) -> Optional[List[float]]:
        """콘텐츠의 키워드와 카테고리 기반 임베딩 생성"""
        try:
            # 콘텐츠의 키워드들과 가중치 조회
            keyword_data = await self.db.fetch_all("""
                SELECT k.embedding, ck.relevance_score
                FROM content_keywords ck
                JOIN keywords k ON ck.keyword_id = k.id
                WHERE ck.content_id = $1
            """, content_id)
            
            # 카테고리 임베딩 조회
            category_data = await self.db.fetch_one("""
                SELECT c.embedding
                FROM summaries s
                JOIN categories c ON s.category_id = c.id
                WHERE s.id = $1
            """, content_id)
            
            if not keyword_data and not category_data:
                logger.warning(f"No keywords or category found for content {content_id}")
                return None
            
            # 가중 평균으로 콘텐츠 임베딩 계산
            embeddings = []
            weights = []
            
            # 키워드 임베딩들 추가
            for row in keyword_data:
                embeddings.append(np.array(row['embedding']))
                weights.append(row['relevance_score'])
            
            # 카테고리 임베딩 추가 (높은 가중치)
            if category_data and category_data['embedding']:
                embeddings.append(np.array(category_data['embedding']))
                weights.append(2.0)  # 카테고리 가중치
            
            if embeddings:
                content_embedding = np.average(embeddings, axis=0, weights=weights)
                
                # DB에 저장
                await self.db.execute("""
                    INSERT INTO content_embeddings (content_id, embedding)
                    VALUES ($1, $2::vector)
                    ON CONFLICT (content_id) 
                    DO UPDATE SET embedding = $2::vector, created_at = CURRENT_TIMESTAMP
                """, content_id, content_embedding.tolist())
                
                logger.bind(ai=True).info(f"Generated and stored embedding for content {content_id}")
                return content_embedding.tolist()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate content embedding for {content_id}: {str(e)}")
            raise
    
    def calculate_cosine_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """코사인 유사도 계산"""
        try:
            v1 = np.array(vector1)
            v2 = np.array(vector2)
            
            # 코사인 유사도 = dot(v1, v2) / (||v1|| * ||v2||)
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Failed to calculate cosine similarity: {str(e)}")
            return 0.0