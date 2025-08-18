import asyncio
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
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
from app.core.models import Tag, ItemTags, Category
from app.observability import trace_request, trace_ai_operation, record_ai_tokens, record_wtu_usage
from app.dedup_detection import check_for_duplicates, DuplicateCandidate
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

    async def _process_embedding_with_monitoring(self, item_id: int, html_content: str, user_id: int = None):
        """
        백그라운드 태스크로 임베딩 처리 - EmbeddingService 사용 (WTU 계측 포함)
        """
        start_time = datetime.now()
        logger.bind(
            task_type="embedding",
            item_id=item_id,
            user_id=user_id,
            status="started",
            timestamp=start_time.isoformat()
        ).info(f"Starting embedding process for item {item_id} (user: {user_id})")

        try:
            # DB 세션 생성
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                # EmbeddingService에 임베딩 생성 위임 (user_id 전달로 WTU 계측)
                embedding_results = await self.embedding_service.create_embeddings(
                    session=session,
                    item_id=item_id,
                    content=html_content,
                    content_type="html",
                    chunking_strategy="token_based",
                    embedding_generator="openai",
                    max_chunk_size=8000,
                    user_id=user_id  # WTU 계측을 위한 사용자 ID 전달
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
        Spring Boot에서 생성된 Item ID를 사용하여 동기화 (관측성 포함)
        """
        async with trace_request(
            "sync_webpage", 
            user_id=request_data.user_id,
            item_id=request_data.item_id,
            url=request_data.url,
            has_html_content=bool(request_data.html_content),
            method="POST"
        ) as span:
            try:
                logger.info(f"Syncing webpage for user {request_data.user_id}, item {request_data.item_id}")
                
                # 사용자 존재 확인 및 생성
                user = await self.user_repository.get_or_create(session, user_id=request_data.user_id)
                logger.bind(database=True).info(f"User {request_data.user_id} retrieved/created")
                span.set_attribute("user_found", True)

                existing_item = await self.item_repository.get_by_id(session, request_data.item_id)
                if existing_item:
                    logger.info(f"Updating existing item {request_data.item_id}")
                    span.set_attribute("operation", "update")
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
                        processing_status="raw",
                        updated_at=func.now(),
                        is_active=True
                    )
                else:
                    logger.info(f"Creating new item {request_data.item_id}")
                    span.set_attribute("operation", "create")
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
                        processing_status="raw",
                        is_active=True
                    )

                # 카테고리 ID 설정
                if request_data.category:
                    category_id = await self._get_or_create_category_id(session, request_data.category)
                    item.category_id = category_id

                # 키워드를 태그로 처리
                if request_data.tags:
                    await self._create_item_tags(session, request_data.item_id, request_data.tags)
                    span.set_attribute("tags_count", len(request_data.tags))
                
                # 중복 콘텐츠 탐지 (새 아이템인 경우에만)
                duplicate_candidates = []
                if not existing_item:
                    try:
                        duplicate_candidates = await check_for_duplicates(
                            session=session,
                            user_id=request_data.user_id,
                            title=request_data.title,
                            summary=request_data.summary or "",
                            url=request_data.url,
                            max_candidates=3
                        )
                        span.set_attribute("duplicate_candidates_found", len(duplicate_candidates))
                        
                        if duplicate_candidates:
                            logger.info(f"Found {len(duplicate_candidates)} duplicate candidates for item {request_data.item_id}")
                            for i, candidate in enumerate(duplicate_candidates):
                                logger.info(f"  Candidate {i+1}: item_id={candidate.item_id}, similarity={candidate.similarity_score:.3f}, type={candidate.match_type}")
                    except Exception as dedup_error:
                        # 중복 탐지 실패는 전체 프로세스를 방해하지 않음
                        logger.warning(f"Duplicate detection failed: {dedup_error}")
                        span.set_attribute("duplicate_detection_error", str(dedup_error))
                    
                # 변경사항 커밋
                await session.commit()

                # 백그라운드 태스크로 임베딩 처리 (WTU 계측 포함)
                if background_tasks and request_data.html_content:
                    background_tasks.add_task(
                        self._process_embedding_with_monitoring,
                        request_data.item_id,
                        request_data.html_content,
                        request_data.user_id  # WTU 계측을 위한 user_id 전달
                    )
                    span.set_attribute("embedding_scheduled", True)
                    logger.info(f"Background task for embedding processing added for item {request_data.item_id} (user: {request_data.user_id})")

                logger.bind(database=True).info(f"Item {request_data.item_id} saved successfully")
                span.set_attribute("success", True)
                
                # 중복 후보를 응답에 포함
                duplicate_response = []
                if duplicate_candidates:
                    from .schemas import DuplicateCandidateResponse
                    duplicate_response = [
                        DuplicateCandidateResponse(
                            item_id=candidate.item_id,
                            title=candidate.title,
                            url=candidate.url,
                            similarity_score=candidate.similarity_score,
                            match_type=candidate.match_type,
                            created_at=candidate.created_at
                        )
                        for candidate in duplicate_candidates
                    ]
                
                return WebpageSyncResponse(
                    success=True,
                    message="콘텐츠가 성공적으로 저장되었습니다.",
                    duplicate_candidates=duplicate_response if duplicate_response else None
                )
                
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
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
                summary=summary,
                user_id=request_data.user_id  # WTU 계측을 위한 사용자 ID 전달
            )

            category = await self.openai_service.recommend_webpage_category(
                summary=summary,
                user_id=request_data.user_id  # WTU 계측을 위한 사용자 ID 전달
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
    
    async def generate_youtube_summary_with_recommendations(
        self,
        session: AsyncSession,
        url: str,
        title: str,
        transcript: str,
        user_id: int,
        tag_count: int = 5
    ) -> Dict:
        """
        사용자 맞춤 추천이 포함된 유튜브 동영상 요약 생성
        """
        logger.bind(user_id=user_id).info(f"Generating YouTube summary with recommendations for URL: {url}")

        # 1. 기본 요약 생성 (유튜브 전용)
        summary = await self.openai_service.generate_youtube_summary(
            title=title,
            transcript=transcript,
            user_id=user_id
        )

        try:
            # 2. 사용자 기반 추천 서비스 초기화
            user_profiling = UserProfilingService(session)
            
            # 3. 개인화된 태그 추천
            recommended_tags = await user_profiling.recommend_tags_for_content(
                content_text=f"{title}\n\n{summary}",
                user_id=user_id,
                limit=tag_count
            )
            
            # 4. 개인화된 카테고리 추천
            recommended_category = await user_profiling.recommend_category_for_content(
                content_text=f"{title}\n\n{summary}",
                user_id=user_id
            )
            
            logger.bind(user_id=user_id).info(
                f"YouTube personalized recommendations completed: "
                f"tags={len(recommended_tags)}, category={recommended_category}"
            )
            
            return {
                'summary': summary,
                'recommended_tags': recommended_tags,
                'recommended_category': recommended_category
            }
            
        except Exception as rec_error:
            # 추천 실패 시 기본 AI 추천으로 폴백
            logger.warning(f"Personalized recommendations failed, falling back to AI: {str(rec_error)}")
            
            try:
                tags = await self.openai_service.generate_youtube_tags(
                    title=title,
                    summary=summary,
                    user_id=user_id
                )
                
                category = await self.openai_service.recommend_youtube_category(
                    title=title,
                    summary=summary,
                    user_id=user_id
                )
                
                return {
                    'summary': summary,
                    'recommended_tags': tags,
                    'recommended_category': category
                }
                
            except Exception as ai_error:
                logger.error(f"AI fallback also failed: {str(ai_error)}")
                # 최후의 기본값
                return {
                    'summary': summary,
                    'recommended_tags': ['유튜브', '동영상'],
                    'recommended_category': 'Video'
                }

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
        logger.bind(user_id=user_id).info(f"Generating summary with recommendations for URL: {request_data.url}")

        # 1. 기본 요약 생성 (항상 먼저 실행)
        summary = await self.openai_service.generate_webpage_summary(
            url=request_data.url,
            html_content=request_data.html_content
        )

        try:
            # DB 연결이 필요한 서비스들 초기화
            vector_service = VectorProcessingService(session)
            user_profiling = UserProfilingService(session)

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
            # 폴백: 기본 요약, 태그, 카테고리 생성
            try:
                logger.info(f"Fallback: Generating basic tags and category for URL {request_data.url}")
                tags = await self.openai_service.generate_webpage_tags(
                    summary=summary,
                    user_id=user_id  # WTU 계측을 위한 사용자 ID 전달
                )
                category = await self.openai_service.recommend_webpage_category(
                    summary=summary,
                    user_id=user_id  # WTU 계측을 위한 사용자 ID 전달
                )

                return {
                    "summary": summary,  # 이미 생성된 요약 사용
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
        # TODO : 더 정교한 유사도 계산 로직 필요 (예: Levenshtein 거리, Jaccard 유사도 등)
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
    
    async def _get_or_create_category_id(self, session: AsyncSession, category_name: str) -> int:
        """카테고리 조회 또는 생성하고 ID 반환"""
        if not category_name:
            logger.warning("Empty category name provided")
            return None
            
        logger.info(f"Getting or creating category: {category_name}")
        
        # 기존 카테고리 조회
        category = await session.execute(
            select(Category).where(Category.name == category_name)
        )
        category = category.scalar_one_or_none()
        
        if not category:
            # 새 카테고리 생성
            category = Category(name=category_name, frequency_count=1)
            session.add(category)
            await session.flush()
            logger.info(f"Created new category: {category_name} (ID: {category.id})")
        else:
            # 빈도 증가
            category.frequency_count += 1
            logger.info(f"Updated existing category: {category_name} (ID: {category.id}, frequency: {category.frequency_count})")
            
        return category.id
    
    async def _create_item_tags(self, session: AsyncSession, item_id: int, keywords: List[str]):
        """키워드를 태그로 생성하고 아이템과 연결 (사용자 입력)"""
        logger.info(f"Creating tags for item {item_id}: {keywords}")
        
        for keyword in keywords:
            # 기존 태그 조회 또는 새 태그 생성
            tag = await session.execute(
                select(Tag).where(Tag.name == keyword)
            )
            tag = tag.scalar_one_or_none()
            
            if not tag:
                tag = Tag(name=keyword, frequency_global=1)
                session.add(tag)
                await session.flush()
                logger.info(f"Created new tag: {keyword} (ID: {tag.id})")
            else:
                tag.frequency_global += 1
                logger.info(f"Updated existing tag: {keyword} (ID: {tag.id}, frequency: {tag.frequency_global})")
            
            # ItemTags 관계 생성 (중복 체크)
            existing_relation = await session.execute(
                select(ItemTags).where(
                    ItemTags.item_id == item_id,
                    ItemTags.tag_id == tag.id
                )
            )
            
            if not existing_relation.scalar_one_or_none():
                item_tag = ItemTags(
                    item_id=item_id,
                    tag_id=tag.id,
                    source="user",  # 사용자가 직접 입력한 키워드
                    relevance_score=1.0
                )
                session.add(item_tag)
                logger.info(f"Created ItemTag relationship: item {item_id} <-> tag {tag.id}")
            else:
                logger.info(f"ItemTag relationship already exists: item {item_id} <-> tag {tag.id}")
        
        # 태그 변경사항 커밋
        await session.commit()
        logger.info(f"Successfully committed tags for item {item_id}")
    
    async def _create_item_tags_ai(self, session: AsyncSession, item_id: int, tags: List[str]):
        """AI 추천 태그를 생성하고 아이템과 연결"""
        logger.info(f"Creating AI tags for item {item_id}: {tags}")
        
        for tag_name in tags:
            # 기존 태그 조회 또는 새 태그 생성
            tag = await session.execute(
                select(Tag).where(Tag.name == tag_name)
            )
            tag = tag.scalar_one_or_none()
            
            if not tag:
                tag = Tag(name=tag_name, frequency_global=1)
                session.add(tag)
                await session.flush()
                logger.info(f"Created new AI tag: {tag_name} (ID: {tag.id})")
            else:
                tag.frequency_global += 1
                logger.info(f"Updated existing AI tag: {tag_name} (ID: {tag.id}, frequency: {tag.frequency_global})")
            
            # ItemTags 관계 생성 (중복 체크)
            existing_relation = await session.execute(
                select(ItemTags).where(
                    ItemTags.item_id == item_id,
                    ItemTags.tag_id == tag.id
                )
            )
            
            if not existing_relation.scalar_one_or_none():
                item_tag = ItemTags(
                    item_id=item_id,
                    tag_id=tag.id,
                    source="ai",  # AI 추천 태그
                    relevance_score=0.8  # 기본 관련도 점수
                )
                session.add(item_tag)
                logger.info(f"Created AI ItemTag relationship: item {item_id} <-> tag {tag.id}")
            else:
                logger.info(f"AI ItemTag relationship already exists: item {item_id} <-> tag {tag.id}")
        
        # 태그 변경사항 커밋
        await session.commit()
        logger.info(f"Successfully committed AI tags for item {item_id}")
    
# 서비스 인스턴스 생성 (싱글톤 패턴)
clipper_service = ClipperService()

# 의존성 주입용 함수
def get_clipper_service() -> ClipperService:
    """ClipperService 인스턴스 반환"""
    return clipper_service
