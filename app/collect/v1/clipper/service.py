import asyncio
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from fastapi import BackgroundTasks
from datetime import datetime

from app.ai.openai_service import openai_service
from app.core.repository import ItemRepository
from app.core.logging import get_logger
from app.user.user_repository import UserRepository
from app.ai.embedding.service import embedding_service
from app.ai.classification.tag_extractor import TagExtractionService
from app.ai.classification.category_classifier import CategoryClassificationService
from app.ai.recommendation.vector_service import VectorProcessingService
from app.ai.recommendation.user_profiling import UserProfilingService
from .schemas import (
    WebpageSyncRequest,
    SummarizeRequest,
    WebpageSyncResponse,
    SummarizeResponse,
)

logger = get_logger(__name__)


class ClipperService:
    """클리퍼 비즈니스 로직 서비스"""
    
    # 처리 상태 상수 (20자 제한)
    # TODO : 이 상태 상수는 데이터베이스 모델에 맞춰야 함, 전역으로 관리 필요
    STATUS_RAW = "raw"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SAVED = "saved"
    
    def __init__(self):
        self.user_repository = UserRepository()
        self.item_repository = ItemRepository()
        self.openai_service = openai_service
        self.embedding_service = embedding_service
        
        # 추천 관련 서비스들 추가
        self.tag_extractor = TagExtractionService()
        self.category_classifier = CategoryClassificationService()
        # vector_service와 user_profiling은 DB 연결이 필요하므로 메서드에서 초기화
        
        logger.info("Clipper service initialized with recommendation services")

    async def _process_embedding_with_monitoring(self, item_id: int, html_content: str):
        """
        백그라운드 태스크로 임베딩 처리 - EmbeddingService 사용
        """
        start_time = datetime.now()
        logger.bind(
            task_type="embedding",
            item_id=item_id,
            status="started",
            timestamp=start_time.isoformat()
        ).info(f"Starting embedding process for item {item_id}")

        try:
            # DB 세션 생성
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                # EmbeddingService에 임베딩 생성 위임
                embedding_results = await self.embedding_service.create_embeddings(
                    session=session,
                    item_id=item_id,
                    content=html_content,
                    content_type="html",
                    chunking_strategy="token_based",
                    embedding_generator="openai",
                    max_chunk_size=8000
                )
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.bind(
                    task_type="embedding",
                    item_id=item_id,
                    status="completed",
                    duration_seconds=duration,
                    chunks_created=len(embedding_results),
                    timestamp=end_time.isoformat()
                ).info(f"Embedding completed for item {item_id} in {duration:.2f}s")

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.bind(
                task_type="embedding",
                item_id=item_id,
                status="failed",
                error=str(e),
                duration_seconds=duration,
                timestamp=end_time.isoformat()
            ).error(f"Embedding failed for item {item_id}: {str(e)}")

    async def sync_webpage(
        self, 
        session: AsyncSession,
        background_tasks: BackgroundTasks,
        request_data: WebpageSyncRequest,
    ) -> WebpageSyncResponse:
        """
        Spring Boot에서 생성된 Item ID를 사용하여 동기화
        """
        try:
            logger.info(f"Syncing webpage for user {request_data.user_id}, item {request_data.item_id}")
            
            # 사용자 존재 확인 및 생성
            user = await self.user_repository.get_or_create(session, user_id=request_data.user_id)
            logger.bind(database=True).info(f"User {request_data.user_id} retrieved/created")

            existing_item = await self.item_repository.get_by_id(session, request_data.item_id)
            if existing_item:
                logger.info(f"Updating existing item {request_data.item_id}")
                item = await self.item_repository.update(
                    session,
                    request_data.item_id,
                    user_id=user.id,
                    item_type="webpage",
                    title=request_data.title,
                    source_url=request_data.url,
                    thumbnail=request_data.thumbnail,
                    raw_content=request_data.html_content,
                    summary=request_data.summary,
                    category=request_data.category,
                    memo=request_data.memo,
                    tags=request_data.keywords or [],
                    processing_status="raw",
                    updated_at=func.now(),
                    is_active=True
                )
            else:
                logger.info(f"Creating new item {request_data.item_id}")
                item = await self.item_repository.create(
                    session,
                    id=request_data.item_id,
                    user_id=user.id,
                    item_type="webpage",
                    title=request_data.title,
                    source_url=request_data.url,
                    thumbnail=request_data.thumbnail,
                    raw_content=request_data.html_content,
                    summary=request_data.summary,
                    category=request_data.category,
                    memo=request_data.memo,
                    tags=request_data.keywords or [],
                    processing_status="raw",
                    is_active=True
                )

            # 백그라운드 태스크로 임베딩 처리
            if background_tasks and request_data.html_content:
                background_tasks.add_task(
                    self._process_embedding_with_monitoring,
                    request_data.item_id,
                    request_data.html_content,
                )
                logger.info(f"Background task for embedding processing added for item {request_data.item_id}")

            logger.bind(database=True).info(f"Item {request_data.item_id} saved successfully")
            return WebpageSyncResponse(
                success=True,
                message="콘텐츠가 성공적으로 저장되었습니다."
            )
        
        except Exception as e:
            logger.error(f"Failed to sync webpage for item {request_data.item_id}: {str(e)}")
            raise Exception(f"저장 중 오류가 발생했습니다: {str(e)}")
    
    async def generate_webpage_summary(self, request_data: SummarizeRequest) -> SummarizeResponse:
        """
        요약 생성 비즈니스 로직
        """
        try:
            logger.info(f"Generating summary for URL: {request_data.url}")
            
            summary = await self.openai_service.generate_webpage_summary(
                url=request_data.url,
                html_content=request_data.html_content
            )

            tags = await self.openai_service.generate_webpage_tags(
                summary = summary
            )

            category = await self.openai_service.recommend_webpage_category(
                summary = summary
            )
            
            logger.info(f"Summary generation completed for URL: {request_data.url}")
            return SummarizeResponse(
                summary=summary,
                tags=tags,
                category=category
            )
        except Exception as e:
            logger.error(f"Failed to generate summary for URL {request_data.url}: {str(e)}")
            raise Exception(f"요약 생성 중 오류가 발생했습니다: {str(e)}")
    
    async def generate_webpage_summary_with_recommendations(
        self, 
        session: AsyncSession,
        request_data: SummarizeRequest,
        user_id: int,
        tag_count: int = 5
    ) -> Dict:
        """
        사용자 맞춤 추천이 포함된 웹페이지 요약 생성
        """
        try:
            logger.bind(user_id=user_id).info(f"Generating summary with recommendations for URL: {request_data.url}")
            
            # DB 연결이 필요한 서비스들 초기화
            vector_service = VectorProcessingService(session)
            user_profiling = UserProfilingService(session)
            
            # 1. 기본 요약 생성
            summary = await self.openai_service.generate_webpage_summary(
                url=request_data.url,
                html_content=request_data.html_content
            )
            
            # 2. 사용자 선호도 기반 태그 추천
            user_keywords = await user_profiling.get_user_top_keywords(user_id, limit=15)
            user_tag_names = [kw['keyword'] for kw in user_keywords]
            
            # AI 기반 태그 생성 (사용자 이력 고려)
            ai_generated_tags = await self.tag_extractor.extract_tags_from_summary(
                summary=summary,
                similar_tags=user_tag_names,
                tag_count=tag_count
            )
            
            # 사용자 선호도 기반 태그 순위화
            recommended_tags = self._rank_tags_by_user_preference(
                ai_generated_tags, user_tag_names, tag_count
            )
            
            # 3. 사용자 선호도 기반 카테고리 추천
            user_categories = await user_profiling.get_user_top_categories(user_id, limit=10)
            user_category_names = [cat['name'] for cat in user_categories]
            
            recommended_category = await self.category_classifier.classify_category_from_summary(
                summary=summary,
                similar_categories=user_category_names
            )
            
            # 신뢰도 계산
            confidence_score = 0.8 if recommended_category in user_category_names else 0.6
            
            # 4. 유사 카테고리 조회
            similar_categories = await vector_service.find_similar_categories(
                recommended_category, limit=3
            )
            similar_category_names = [cat['name'] for cat in similar_categories]
            
            result = {
                "summary": summary,
                "recommended_tags": recommended_tags,
                "recommended_category": recommended_category,
                "confidence_score": confidence_score,
                "user_history_tags": user_tag_names[:5],
                "ai_generated_tags": ai_generated_tags,
                "similar_categories": similar_category_names,
                "user_preferred_categories": user_category_names[:5]
            }
            
            logger.bind(user_id=user_id).info(f"Summary with recommendations completed for URL: {request_data.url}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate summary with recommendations for URL {request_data.url}: {str(e)}")
            # 폴백: 기본 요약만 반환
            try:
                summary = await self.openai_service.generate_webpage_summary(
                    url=request_data.url,
                    html_content=request_data.html_content
                )
                tags = await self.openai_service.generate_webpage_tags(summary=summary)
                category = await self.openai_service.recommend_webpage_category(summary=summary)
                
                return {
                    "summary": summary,
                    "recommended_tags": tags,
                    "recommended_category": category,
                    "confidence_score": 0.5,
                    "user_history_tags": [],
                    "ai_generated_tags": tags,
                    "similar_categories": [],
                    "user_preferred_categories": []
                }
            except Exception as fallback_error:
                logger.error(f"Fallback summary generation also failed: {str(fallback_error)}")
                raise Exception(f"요약 및 추천 생성 중 오류가 발생했습니다: {str(e)}")
    
    async def save_content_with_recommendations(
        self,
        session: AsyncSession,
        user_id: str,
        item_id: int,
        title: str,
        summary: str,
        url: str,
        recommended_tags: List[str],
        recommended_category: str,
        html_content: str = None
    ):
        """추천된 태그/카테고리와 함께 콘텐츠 저장"""
        try:
            logger.bind(user_id=user_id).info(f"Saving content {item_id} with recommendations")
            
            # DB 연결이 필요한 서비스들 초기화
            vector_service = VectorProcessingService(session)
            user_profiling = UserProfilingService(session)
            
            # 1. 카테고리 ID 조회 또는 생성
            category_id = await vector_service.store_category_with_embedding(recommended_category)
            
            # 2. 태그들을 키워드로 저장하고 ID 조회
            keyword_ids = await vector_service.batch_store_keywords_with_embeddings(recommended_tags)
            
            # 3. 기존 아이템 업데이트 또는 생성
            user = await self.user_repository.get_or_create(session, user_id=user_id)
            
            existing_item = await self.item_repository.get_by_id(session, item_id)
            if existing_item:
                item = await self.item_repository.update(
                    session,
                    item_id,
                    user_id=user.id,
                    title=title,
                    summary=summary,
                    source_url=url,
                    category=recommended_category,
                    tags=recommended_tags,
                    raw_content=html_content,
                    processing_status="saved",
                    updated_at=func.now()
                )
            else:
                item = await self.item_repository.create(
                    session,
                    id=item_id,
                    user_id=user.id,
                    item_type="webpage",
                    title=title,
                    summary=summary,
                    source_url=url,
                    category=recommended_category,
                    tags=recommended_tags,
                    raw_content=html_content,
                    processing_status="saved"
                )
            
            # 4. 콘텐츠-키워드 관계 저장
            await self._store_content_keyword_relationships(session, item_id, keyword_ids, recommended_tags)
            
            # 5. 사용자 상호작용 기록 (콘텐츠 저장 행위)
            await self._record_user_interactions(session, user_id, keyword_ids, category_id, "save", user_profiling)
            
            # 6. 콘텐츠 임베딩 생성
            await vector_service.generate_content_embedding(item_id)
            
            logger.bind(user_id=user_id).info(f"Successfully saved content {item_id} with recommendations")
            return item_id
            
        except Exception as e:
            logger.error(f"Failed to save content with recommendations: {str(e)}")
            raise
    
    async def record_user_content_interaction(
        self,
        session: AsyncSession,
        user_id: str,
        content_id: int,
        interaction_type: str = "view"
    ):
        """사용자 콘텐츠 상호작용 기록"""
        try:
            user_profiling = UserProfilingService(session)
            
            # 1. 콘텐츠의 키워드들과 카테고리 조회
            from sqlalchemy import text
            content_query = text("""
                SELECT s.category_id, array_agg(ck.keyword_id) as keyword_ids
                FROM summaries s
                LEFT JOIN content_keywords ck ON s.id = ck.content_id
                WHERE s.id = :content_id
                GROUP BY s.category_id
            """)
            
            result = await session.execute(content_query, {"content_id": content_id})
            content_data = result.fetchone()
            
            if content_data:
                # 2. 키워드 상호작용 업데이트
                if content_data.keyword_ids and content_data.keyword_ids[0] is not None:
                    for keyword_id in content_data.keyword_ids:
                        await user_profiling.update_user_keyword_interaction(
                            user_id, keyword_id, interaction_type
                        )
                
                # 3. 카테고리 선호도 업데이트
                if content_data.category_id:
                    await user_profiling.update_user_category_preference(
                        user_id, content_data.category_id, interaction_type
                    )
                
                # 4. 조회 기록 저장 (중복 방지)
                if interaction_type == "view":
                    view_query = text("""
                        INSERT INTO user_seen_content (user_id, content_id, viewed_at)
                        VALUES (:user_id, :content_id, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id, content_id) 
                        DO UPDATE SET viewed_at = CURRENT_TIMESTAMP
                    """)
                    await session.execute(view_query, {"user_id": user_id, "content_id": content_id})
                    await session.commit()
            
            logger.bind(user_id=user_id).info(
                f"Recorded {interaction_type} interaction for content {content_id}"
            )
            
        except Exception as e:
            logger.error(f"Failed to record user interaction: {str(e)}")
            # 상호작용 기록 실패는 치명적이지 않으므로 예외를 다시 던지지 않음
    
    # 내부 헬퍼 메서드들
    def _rank_tags_by_user_preference(
        self, 
        ai_tags: List[str], 
        user_tags: List[str],
        tag_count: int
    ) -> List[str]:
        """사용자 선호도 기반 태그 순위화"""
        tag_scores = {}
        
        for tag in ai_tags:
            base_score = 1.0
            
            # 사용자 이력에 있는 태그라면 점수 부스트
            if tag.lower() in [ut.lower() for ut in user_tags]:
                base_score += 2.0
            
            # 유사한 태그가 있다면 점수 부스트
            for user_tag in user_tags:
                if self._calculate_tag_similarity(tag, user_tag) > 0.7:
                    base_score += 1.0
                    break
            
            tag_scores[tag] = base_score
        
        # 점수 기준으로 정렬하고 상위 N개 반환
        ranked_tags = sorted(tag_scores.keys(), key=lambda x: tag_scores[x], reverse=True)
        return ranked_tags[:tag_count]
    
    def _calculate_tag_similarity(self, tag1: str, tag2: str) -> float:
        """태그 유사도 계산 (간단한 문자열 기반)"""
        tag1_lower = tag1.lower()
        tag2_lower = tag2.lower()
        
        if tag1_lower == tag2_lower:
            return 1.0
        
        # 포함 관계 확인
        if tag1_lower in tag2_lower or tag2_lower in tag1_lower:
            return 0.8
        
        # 문자 겹침 비율 계산
        common_chars = set(tag1_lower) & set(tag2_lower)
        total_chars = set(tag1_lower) | set(tag2_lower)
        
        if len(total_chars) == 0:
            return 0.0
        
        return len(common_chars) / len(total_chars)
    
    async def _store_content_keyword_relationships(
        self, 
        session: AsyncSession,
        content_id: int, 
        keyword_ids: List[int], 
        keywords: List[str]
    ):
        """콘텐츠-키워드 관계 저장"""
        from sqlalchemy import text
        
        for i, keyword_id in enumerate(keyword_ids):
            if keyword_id is not None:  # 유효한 키워드 ID만
                relevance_score = 1.0 - (i * 0.1)  # 순서에 따른 관련성 점수
                relevance_score = max(0.1, relevance_score)  # 최소 점수 보장
                
                query = text("""
                    INSERT INTO content_keywords (content_id, keyword_id, relevance_score)
                    VALUES (:content_id, :keyword_id, :relevance_score)
                    ON CONFLICT (content_id, keyword_id) 
                    DO UPDATE SET relevance_score = GREATEST(content_keywords.relevance_score, :relevance_score)
                """)
                await session.execute(query, {
                    "content_id": content_id, 
                    "keyword_id": keyword_id, 
                    "relevance_score": relevance_score
                })
        
        await session.commit()
    
    async def _record_user_interactions(
        self, 
        session: AsyncSession,
        user_id: str, 
        keyword_ids: List[int], 
        category_id: int, 
        interaction_type: str,
        user_profiling: UserProfilingService
    ):
        """사용자 상호작용 일괄 기록"""
        # 키워드 상호작용 기록
        for keyword_id in keyword_ids:
            if keyword_id is not None:
                await user_profiling.update_user_keyword_interaction(
                    user_id, keyword_id, interaction_type
                )
        
        # 카테고리 선호도 기록
        if category_id:
            await user_profiling.update_user_category_preference(
                user_id, category_id, interaction_type
            )
    
# 서비스 인스턴스 생성 (싱글톤 패턴)
clipper_service = ClipperService()

# 의존성 주입 함수 (기존 패턴 따름)
def get_clipper_service() -> ClipperService:
    """클리퍼 서비스 의존성"""
    return clipper_service
