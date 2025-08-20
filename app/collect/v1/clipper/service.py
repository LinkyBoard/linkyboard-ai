import asyncio
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from fastapi import BackgroundTasks
from datetime import datetime

from app.ai.providers.router import ai_router
from app.core.repository import ItemRepository
from app.core.logging import get_logger
from app.user.user_repository import UserRepository
from app.ai.embedding.service import embedding_service
from app.ai.classification.tag_extractor import TagExtractionService
from app.ai.classification.category_classifier import CategoryClassificationService
from app.ai.classification.smart_extractor import smart_extraction_service
from app.ai.content_extraction.youtube_url_extractor import youtube_url_extractor
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
from .schemas_youtube import (
    YouTubeSyncRequest,
    YouTubeSyncResponse,
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
        self.ai_router = ai_router
        self.embedding_service = embedding_service
        
        # 추천 관련 서비스들 추가
        self.tag_extractor = TagExtractionService()  # 기존 OpenAI 기반
        self.category_classifier = CategoryClassificationService()  # 기존 OpenAI 기반
        self.smart_extractor = smart_extraction_service  # 새로운 로컬 NLP 기반
        self.youtube_url_extractor = youtube_url_extractor  # YouTube URL 추출기
        # vector_service와 user_profiling은 DB 연결이 필요하므로 메서드에서 초기화
        
        logger.info("Clipper service initialized with recommendation services (including smart extractor and YouTube URL extractor)")

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

    async def sync_youtube(
        self, 
        session: AsyncSession,
        background_tasks: BackgroundTasks,
        request_data: YouTubeSyncRequest,
    ) -> YouTubeSyncResponse:
        """
        YouTube 동영상 동기화 - transcript를 raw_content로 저장
        """
        async with trace_request(
            "sync_youtube", 
            user_id=request_data.user_id,
            item_id=request_data.item_id,
            url=request_data.url,
            has_transcript=bool(request_data.transcript),
            method="POST"
        ) as span:
            try:
                logger.info(f"Syncing YouTube video for user {request_data.user_id}, item {request_data.item_id}")
                
                # 사용자 존재 확인 및 생성
                user = await self.user_repository.get_or_create(session, user_id=request_data.user_id)
                logger.bind(database=True).info(f"User {request_data.user_id} retrieved/created")
                span.set_attribute("user_found", True)

                existing_item = await self.item_repository.get_by_id(session, request_data.item_id)
                if existing_item:
                    logger.info(f"Updating existing YouTube item {request_data.item_id}")
                    span.set_attribute("operation", "update")
                    item = await self.item_repository.update(
                        session,
                        request_data.item_id,
                        user_id=user.id,
                        item_type="youtube",
                        title=request_data.title,
                        source_url=request_data.url,
                        thumbnail=request_data.thumbnail,
                        raw_content=request_data.transcript,  # YouTube 스크립트를 raw_content로 저장
                        summary=request_data.summary,
                        category=request_data.category,
                        memo=request_data.memo,
                        processing_status="raw",
                        updated_at=func.now(),
                    )
                else:
                    logger.info(f"Creating new YouTube item {request_data.item_id}")
                    span.set_attribute("operation", "create")
                    item = await self.item_repository.create(
                        session,
                        id=request_data.item_id,
                        user_id=user.id,
                        item_type="youtube",
                        title=request_data.title,
                        source_url=request_data.url,
                        thumbnail=request_data.thumbnail,
                        raw_content=request_data.transcript,  # YouTube 스크립트를 raw_content로 저장
                        summary=request_data.summary,
                        category=request_data.category,
                        memo=request_data.memo,
                        processing_status="raw"
                    )

                logger.bind(database=True).info(f"Item {request_data.item_id} saved with transcript length: {len(request_data.transcript)}")
                span.set_attribute("item_saved", True)
                span.set_attribute("transcript_length", len(request_data.transcript))

                # 태그 처리 (있는 경우)
                if request_data.tags:
                    try:
                        logger.info(f"Processing {len(request_data.tags)} tags for item {request_data.item_id}")
                        for tag_name in request_data.tags:
                            if tag_name and tag_name.strip():
                                # 기존 태그를 찾거나 새로 생성
                                existing_tag = await session.execute(
                                    select(Tag).where(Tag.name == tag_name.strip())
                                )
                                tag = existing_tag.scalar_one_or_none()
                                
                                if not tag:
                                    tag = Tag(name=tag_name.strip())
                                    session.add(tag)
                                    await session.flush()  # ID 생성을 위해 flush
                                
                                # 아이템-태그 연결 확인 및 생성
                                existing_item_tag = await session.execute(
                                    select(ItemTags).where(
                                        ItemTags.item_id == item.id,
                                        ItemTags.tag_id == tag.id
                                    )
                                )
                                if not existing_item_tag.scalar_one_or_none():
                                    item_tag = ItemTags(
                                        item_id=item.id,
                                        tag_id=tag.id,
                                        source="user",
                                        relevance_score=1.0
                                    )
                                    session.add(item_tag)
                        
                        logger.info(f"Tags processed successfully for item {request_data.item_id}")
                        span.set_attribute("tags_processed", len(request_data.tags))
                    except Exception as tag_error:
                        logger.warning(f"Tag processing failed: {tag_error}")
                        span.set_attribute("tag_processing_error", str(tag_error))

                # 중복 탐지 시도 (실패해도 전체 프로세스는 계속)
                duplicate_candidates = []
                try:
                    # YouTube URL로 중복 탐지
                    candidates = await check_for_duplicates(
                        session, 
                        user_id=request_data.user_id,
                        title=request_data.title,
                        summary=request_data.summary or "",
                        url=request_data.url
                    )
                    duplicate_candidates = candidates or []
                    logger.info(f"Duplicate detection completed: {len(duplicate_candidates)} candidates found")
                    span.set_attribute("duplicate_candidates_count", len(duplicate_candidates))
                except Exception as dedup_error:
                    # 중복 탐지 실패는 전체 프로세스를 방해하지 않음
                    logger.warning(f"Duplicate detection failed: {dedup_error}")
                    span.set_attribute("duplicate_detection_error", str(dedup_error))
                
                # 변경사항 커밋
                await session.commit()

                # 백그라운드 태스크로 임베딩 처리 (transcript 기반)
                if background_tasks and request_data.transcript:
                    background_tasks.add_task(
                        self._process_embedding_with_monitoring,
                        request_data.item_id,
                        request_data.transcript,  # transcript를 임베딩 처리용으로 사용
                        request_data.user_id
                    )
                    span.set_attribute("embedding_scheduled", True)
                    logger.info(f"Background task for embedding processing added for YouTube item {request_data.item_id} (user: {request_data.user_id})")

                logger.bind(database=True).info(f"YouTube item {request_data.item_id} saved successfully")
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
                
                return YouTubeSyncResponse(
                    success=True,
                    message="YouTube 동영상이 성공적으로 저장되었습니다.",
                    duplicate_candidates=duplicate_response if duplicate_response else None
                )
                
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Failed to sync YouTube video for item {request_data.item_id}: {str(e)}")
                raise Exception(f"YouTube 동영상 저장 중 오류가 발생했습니다: {str(e)}")
    
    async def generate_webpage_summary(self, request_data: SummarizeRequest) -> SummarizeResponse:
        """
        요약 생성 비즈니스 로직
        """
        try:
            logger.info(f"Generating summary for URL: {request_data.url}")
            
            summary = await self.ai_router.generate_webpage_summary(
                url=request_data.url,
                html_content=request_data.html_content
            )

            tags = await self.ai_router.generate_webpage_tags(
                summary=summary,
                user_id=request_data.user_id  # WTU 계측을 위한 사용자 ID 전달
            )

            category = await self.ai_router.recommend_webpage_category(
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
        사용자 맞춤 추천이 포함된 유튜브 동영상 요약 생성 (스마트 추출 우선 사용)
        """
        logger.bind(user_id=user_id).info(f"Generating YouTube summary with recommendations for URL: {url}")

        # 1. 기본 요약 생성 (유튜브 전용)
        summary = await self.ai_router.generate_youtube_summary(
            title=title,
            transcript=transcript,
            user_id=user_id
        )

        try:
            # 2. 스마트 추출 시스템으로 태그/카테고리 추천 (비용 절약)
            logger.info(f"Using smart extraction for YouTube content: {title[:50]}...")
            
            # YouTube 비디오 ID 추출 (URL에서)
            video_id = self._extract_video_id_from_url(url)
            
            smart_result = await self.smart_extractor.extract_youtube_tags_and_category(
                title=title,
                transcript=transcript,
                video_id=video_id,
                user_id=user_id,
                max_tags=tag_count,
                session=session
            )
            
            logger.bind(user_id=user_id).info(
                f"YouTube smart extraction completed: "
                f"tags={len(smart_result['tags'])}, category={smart_result['category']}, "
                f"method={smart_result['metadata']['processing_method']}"
            )
            
            return {
                'summary': summary,
                'recommended_tags': smart_result['tags'],
                'recommended_category': smart_result['category']
            }
            
        except Exception as smart_error:
            # 스마트 추출 실패 시 사용자 프로파일링으로 폴백
            logger.warning(f"Smart extraction failed, falling back to user profiling: {str(smart_error)}")
            
            try:
                user_profiling = UserProfilingService(session)
                
                # 개인화된 태그 추천
                recommended_tags = await user_profiling.recommend_tags_for_content(
                    content_text=f"{title}\n\n{summary}",
                    user_id=user_id,
                    limit=tag_count
                )
                
                # 개인화된 카테고리 추천
                recommended_category = await user_profiling.recommend_category_for_content(
                    content_text=f"{title}\n\n{summary}",
                    user_id=user_id
                )
                
                logger.bind(user_id=user_id).info(
                    f"YouTube user profiling completed: "
                    f"tags={len(recommended_tags)}, category={recommended_category}"
                )
                
                return {
                    'summary': summary,
                    'recommended_tags': recommended_tags,
                    'recommended_category': recommended_category
                }
                
            except Exception as profile_error:
                # 사용자 프로파일링 실패 시 OpenAI로 최종 폴백
                logger.warning(f"User profiling failed, falling back to OpenAI: {str(profile_error)}")
                
                try:
                    tags = await self.ai_router.generate_youtube_tags(
                        title=title,
                        summary=summary,
                        user_id=user_id
                    )
                    
                    category = await self.ai_router.recommend_youtube_category(
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
                    logger.error(f"All fallback methods failed: {str(ai_error)}")
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
        summary = await self.ai_router.generate_webpage_summary(
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
                tags = await self.ai_router.generate_webpage_tags(
                    summary=summary,
                    user_id=user_id  # WTU 계측을 위한 사용자 ID 전달
                )
                category = await self.ai_router.recommend_webpage_category(
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
    
    async def generate_smart_webpage_summary_with_recommendations(
        self,
        session: AsyncSession,
        request_data: SummarizeRequest,
        user_id: int,
        use_smart_extraction: bool = True
    ) -> Dict:
        """
        스마트 추출기를 사용한 웹페이지 요약 및 추천 생성 (비용 절감 버전)
        
        Args:
            session: 데이터베이스 세션
            request_data: 요약 요청 데이터
            user_id: 사용자 ID
            use_smart_extraction: 스마트 추출기 사용 여부 (False면 기존 OpenAI 방식)
            
        Returns:
            요약, 추천 태그, 추천 카테고리가 포함된 딕셔너리
        """
        logger.bind(user_id=user_id).info(
            f"Generating smart summary for URL: {request_data.url}, "
            f"smart_extraction: {use_smart_extraction}"
        )
        
        try:
            # HTML 파일 읽기
            html_content = await self._read_html_file(request_data.html_file)
            if not html_content:
                raise ValueError("HTML 파일을 읽을 수 없습니다.")
            
            # 스마트 추출기 사용
            if use_smart_extraction:
                logger.info("Using smart extraction (cost-efficient)")
                
                # 스마트 추출기로 태그와 카테고리 추출
                smart_result = await self.smart_extractor.extract_tags_and_category(
                    html_content=html_content,
                    url=request_data.url,
                    user_id=user_id,
                    max_tags=5,
                    session=session
                )
                
                # 요약은 별도로 생성하거나 콘텐츠에서 추출
                content_info = smart_result['metadata']['content_info']
                
                # 간단한 요약 생성 (첫 200자 + 정제)
                extracted_content = content_info.get('extracted_content', '')
                if extracted_content:
                    summary = self._generate_simple_summary(extracted_content, content_info['title'])
                else:
                    # Fallback to OpenAI summary
                    summary = await self.ai_router.generate_webpage_summary(
                        url=request_data.url,
                        html_content=html_content[:5000],  # 길이 제한
                        max_tokens=300
                    )
                
                result = {
                    'summary': summary,
                    'recommended_tags': smart_result['tags'],
                    'recommended_category': smart_result['category'],
                    'metadata': {
                        **smart_result['metadata'],
                        'cost_savings': True,
                        'processing_method': 'smart_extraction'
                    }
                }
                
                logger.info(f"Smart extraction completed - tags: {len(result['recommended_tags'])}, "
                           f"category: {result['recommended_category']}")
                
                return result
            
            else:
                # 기존 OpenAI 방식 사용 (fallback)
                logger.info("Using traditional OpenAI extraction (fallback)")
                return await self.generate_webpage_summary_with_recommendations(
                    session=session,
                    request_data=request_data,
                    user_id=user_id,
                    tag_count=5
                )
        
        except Exception as e:
            logger.error(f"Smart summary generation failed: {str(e)}")
            
            # 완전한 fallback: 기존 방식으로 재시도
            try:
                logger.info("Falling back to traditional OpenAI extraction")
                return await self.generate_webpage_summary_with_recommendations(
                    session=session,
                    request_data=request_data,
                    user_id=user_id,
                    tag_count=5
                )
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {str(fallback_error)}")
                
                # 최후의 수단: 기본값 반환
                return {
                    'summary': f"웹페이지 요약을 생성할 수 없습니다. URL: {request_data.url}",
                    'recommended_tags': ['웹페이지'],
                    'recommended_category': '기타',
                    'metadata': {
                        'processing_method': 'error_fallback',
                        'cost_savings': False,
                        'error': str(e)
                    }
                }
    
    def _generate_simple_summary(self, content: str, title: str = "") -> str:
        """
        콘텐츠에서 간단한 요약 생성 (OpenAI 없이)
        """
        try:
            if not content:
                return title if title else "콘텐츠를 요약할 수 없습니다."
            
            # 문장 단위로 분할
            import re
            sentences = re.split(r'[.!?]+', content)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
            
            if not sentences:
                return title if title else "콘텐츠를 요약할 수 없습니다."
            
            # 첫 3개 문장 또는 200자까지
            summary_parts = []
            total_length = 0
            
            for sentence in sentences[:5]:  # 최대 5개 문장 확인
                if total_length + len(sentence) <= 200:
                    summary_parts.append(sentence)
                    total_length += len(sentence)
                else:
                    break
            
            if summary_parts:
                summary = '. '.join(summary_parts)
                if not summary.endswith('.'):
                    summary += '.'
                return summary
            else:
                # 길이 제한으로 요약
                return content[:200].rstrip() + '...' if len(content) > 200 else content
        
        except Exception as e:
            logger.warning(f"Simple summary generation failed: {e}")
            return title if title else "요약을 생성할 수 없습니다."
    
    async def _read_html_file(self, html_file) -> Optional[str]:
        """HTML 파일 읽기 (기존 메서드 활용)"""
        try:
            if hasattr(html_file, 'read'):
                content = await html_file.read()
                if isinstance(content, bytes):
                    return content.decode('utf-8', errors='ignore')
                return content
            else:
                return str(html_file)
        except Exception as e:
            logger.error(f"Failed to read HTML file: {e}")
            return None
    
    def _extract_video_id_from_url(self, url: str) -> Optional[str]:
        """YouTube URL에서 video ID를 추출합니다."""
        try:
            import re
            
            # 다양한 YouTube URL 패턴 지원
            patterns = [
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    logger.info(f"Extracted YouTube video ID: {video_id}")
                    return video_id
            
            logger.warning(f"Could not extract video ID from YouTube URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting video ID from URL {url}: {e}")
            return None

    async def generate_youtube_summary_from_url(
        self,
        session: AsyncSession,
        url: str,
        user_id: int,
        tag_count: int = 5
    ) -> Dict:
        """
        YouTube URL만으로 완전한 요약 및 추천 생성
        
        Args:
            session: 데이터베이스 세션
            url: YouTube URL
            user_id: 사용자 ID
            tag_count: 추천 태그 수
            
        Returns:
            완전한 YouTube 분석 결과
        """
        try:
            logger.info(f"Starting YouTube URL analysis for: {url}")
            
            # 1. YouTube URL에서 완전한 정보 추출
            complete_info = await self.youtube_url_extractor.extract_complete_info(url)
            
            if not complete_info.get('extraction_success'):
                error_msg = complete_info.get('error', 'Unknown extraction error')
                logger.error(f"YouTube extraction failed: {error_msg}")
                return {
                    'success': False,
                    'error': f"YouTube 정보를 추출할 수 없습니다: {error_msg}",
                    'video_info': None,
                    'transcript_info': None,
                    'summary': None,
                    'tags': None,
                    'category': None
                }
            
            metadata = complete_info['metadata']
            transcript_info = complete_info['transcript']
            
            # 2. 자막 사용 가능 여부 확인 및 대안 처리
            has_transcript = transcript_info.get('success') and transcript_info.get('transcript')
            
            if not has_transcript:
                logger.info(f"No transcript available for {url}, returning basic response without AI analysis")
                
                # 자막이 없는 경우 AI를 사용하지 않고 기본 응답 생성
                basic_summary = self._generate_basic_youtube_response(metadata, transcript_info)
                
                # 자막 없음을 명시한 기본 결과 반환
                result = {
                    'success': True,
                    'video_info': metadata,
                    'transcript_info': transcript_info,
                    'summary': basic_summary['summary'],
                    'tags': basic_summary['tags'],
                    'category': basic_summary['category'],
                    'analysis_method': 'basic_metadata',
                    'warning': '자막을 추출할 수 없어 AI 분석 없이 기본 정보만 제공됩니다.'
                }
                
                logger.info(f"Basic response generated for: {metadata.get('title', 'Unknown')[:50]}...")
                return result
            
            # 3. 자막이 있는 경우 일반 요약 및 추천 생성
            logger.info(f"Generating summary and recommendations for: {metadata.get('title', 'Unknown')[:50]}...")
            
            summary_result = await self.generate_youtube_summary_with_recommendations(
                session=session,
                url=url,
                title=metadata.get('title', ''),
                transcript=transcript_info.get('transcript', ''),
                user_id=user_id,
                tag_count=tag_count
            )
            
            # 4. 완전한 결과 반환 (자막 사용 가능한 경우)
            result = {
                'success': True,
                'video_info': metadata,
                'transcript_info': transcript_info,
                'summary': summary_result.get('summary'),
                'tags': summary_result.get('recommended_tags'),
                'category': summary_result.get('recommended_category'),
                'analysis_method': 'full_transcript',
                'extraction_metadata': {
                    'extraction_timestamp': complete_info.get('extraction_timestamp'),
                    'transcript_language': transcript_info.get('language'),
                    'is_auto_generated': transcript_info.get('is_auto_generated'),
                    'available_languages': transcript_info.get('available_languages', []),
                    'extraction_method': transcript_info.get('extraction_method')
                }
            }
            
            logger.info(f"YouTube URL analysis completed successfully for: {metadata.get('title', 'Unknown')[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"YouTube URL analysis failed for {url}: {str(e)}")
            return {
                'success': False,
                'error': f"YouTube 분석 중 오류가 발생했습니다: {str(e)}",
                'video_info': None,
                'transcript_info': None,
                'summary': None,
                'tags': None,
                'category': None
            }
    
    async def generate_youtube_summary_from_metadata_only(
        self,
        session: AsyncSession,
        url: str,
        metadata: Dict[str, Any],
        user_id: int,
        tag_count: int = 5
    ) -> Dict:
        """
        자막 없이 메타데이터만으로 YouTube 비디오 요약 생성
        
        Args:
            session: 데이터베이스 세션
            url: YouTube URL
            metadata: 비디오 메타데이터
            user_id: 사용자 ID
            tag_count: 추천 태그 수
            
        Returns:
            메타데이터 기반 요약 결과
        """
        try:
            logger.info(f"Generating metadata-only summary for: {metadata.get('title', 'Unknown')[:50]}...")
            
            # 메타데이터에서 사용 가능한 정보 추출
            title = metadata.get('title', '')
            description = metadata.get('description', '')[:500]  # 설명이 너무 길면 자르기
            tags = metadata.get('tags', [])
            categories = metadata.get('categories', [])
            channel = metadata.get('channel', metadata.get('uploader', ''))
            
            # 메타데이터 결합 콘텐츠 생성
            metadata_content = self._create_metadata_content(metadata)
            
            # AI 요약 생성 (한국어 지정)
            ai_prompt = f"""
            YouTube 비디오의 메타데이터를 분석하여 한국어로 요약해주세요.
            자막이 없어 제목, 설명, 태그 등 제한된 정보만 사용할 수 있습니다.
            
            비디오 정보:
            {metadata_content}
            
            요구사항:
            1. 제목과 설명을 기반으로 한국어로 2-3문장 요약 생성
            2. 자막이 없어 제한적임을 명시
            3. 반드시 한국어로 작성
            
            예시 형식:
            "제목과 설명을 바탕으로 이 비디오는... 대해 다룹니다. 자막이 제공되지 않아 상세한 내용을 살펴볼 수 없었지만, 주요 주제는...일 것으로 추정됩니다."
            """
            
            # AI 요약 생성
            summary = await self.ai_service.generate_summary_with_context(ai_prompt, metadata_content)
            
            # 사용자 프로필링 및 추천 시스템 활용
            user_profile = await self.user_profiling.get_user_profile_summary(session, user_id)
            
            # 메타데이터 기반 태그 및 카테고리 추천
            ai_tags_prompt = f"""
            YouTube 비디오의 메타데이터를 바탕으로 한국어 태그 {tag_count}개를 추천해주세요.
            
            비디오 정보:
            {metadata_content}
            
            사용자 관심사: {user_profile.get('interests', '')}
            
            요구사항:
            1. 반드시 한국어로 작성
            2. 쉽표나 따옴표 없이 태그만 나열 (,로 구분)
            3. 사용자 관심사 고려
            
            예시: 기술, 개발, 프로그래밍, AI, 머신러닝
            """
            
            ai_tags = await self.ai_service.generate_tags(ai_tags_prompt, metadata_content, tag_count)
            
            # 카테고리 추천
            category_prompt = f"""
            YouTube 비디오의 메타데이터를 바탕으로 적절한 한국어 카테고리를 추천해주세요.
            
            비디오 정보:
            {metadata_content}
            
            사용자 관심사: {user_profile.get('interests', '')}
            
            요구사항:
            1. 반드시 한국어로 작성
            2. 단일 카테고리만 반환 (예: 기술, 교육, 엔터테인먼트 등)
            """
            
            ai_category = await self.ai_service.generate_category(category_prompt, metadata_content)
            
            # 기존 사용자 태그/카테고리 형식으로 조정
            recommended_tags = self._rank_tags_by_user_preference(
                ai_tags, 
                user_profile.get('preferred_tags', []),
                tag_count
            )
            
            result = {
                'summary': summary,
                'recommended_tags': recommended_tags,
                'recommended_category': ai_category,
                'user_profile_applied': True,
                'metadata_sources': {
                    'title': bool(title),
                    'description': bool(description),
                    'tags': len(tags) > 0,
                    'categories': len(categories) > 0,
                    'channel': bool(channel)
                }
            }
            
            logger.info(f"Metadata-only analysis completed: summary={len(summary)} chars, "
                       f"tags={len(recommended_tags)}, category='{ai_category}'")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate metadata-only summary: {str(e)}")
            # 오류시에도 기본적인 정보는 제공
            return {
                'summary': f"자막이 없는 YouTube 비디오입니다. 제목: {metadata.get('title', '알 수 없음')}",
                'recommended_tags': ['비디오'],
                'recommended_category': '일반',
                'user_profile_applied': False,
                'error': str(e)
            }
    
    def _create_metadata_content(self, metadata: Dict[str, Any]) -> str:
        """메타데이터를 기반으로 콘텐츠 생성"""
        parts = []
        
        if metadata.get('title'):
            parts.append(f"제목: {metadata['title']}")
        
        if metadata.get('description'):
            description = metadata['description'][:300]  # 설명 제한
            if len(metadata['description']) > 300:
                description += "..."
            parts.append(f"설명: {description}")
        
        if metadata.get('channel') or metadata.get('uploader'):
            channel = metadata.get('channel', metadata.get('uploader'))
            parts.append(f"채널: {channel}")
        
        if metadata.get('tags'):
            tags = metadata['tags'][:10]  # 태그 10개만 사용
            parts.append(f"태그: {', '.join(tags)}")
        
        if metadata.get('categories'):
            parts.append(f"카테고리: {', '.join(metadata['categories'])}")
        
        if metadata.get('duration_formatted'):
            parts.append(f"재생시간: {metadata['duration_formatted']}")
        
        if metadata.get('view_count'):
            parts.append(f"조회수: {metadata['view_count']:,}만번")
        
        return "\n\n".join(parts)
    
    def _generate_basic_youtube_response(self, metadata: Dict[str, Any], transcript_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI를 사용하지 않고 메타데이터만으로 기본적인 YouTube 응답 생성
        
        Args:
            metadata: YouTube 비디오 메타데이터
            transcript_info: 자막 정보 (실패 시)
            
        Returns:
            기본 응답 딕셔너리 (summary, tags, category)
        """
        title = metadata.get('title', '제목 없음')
        description = metadata.get('description', '')
        channel = metadata.get('channel', metadata.get('uploader', '채널 없음'))
        duration = metadata.get('duration_formatted', '시간 없음')
        
        # 기본 요약 생성 (AI 없이)
        summary_parts = [f"YouTube 영상: {title}"]
        
        if channel != '채널 없음':
            summary_parts.append(f"채널: {channel}")
        
        if duration != '시간 없음':
            summary_parts.append(f"재생시간: {duration}")
            
        if description:
            # 설명의 첫 100자만 사용
            short_desc = description[:100].strip()
            if len(description) > 100:
                short_desc += "..."
            if short_desc:
                summary_parts.append(f"설명: {short_desc}")
        
        # 자막 추출 실패 이유 추가
        extraction_method = transcript_info.get('extraction_method', 'unknown')
        if extraction_method == 'no_transcript_available':
            summary_parts.append("자막이 제공되지 않는 영상입니다.")
        elif 'error' in transcript_info:
            summary_parts.append("자막을 추출할 수 없었습니다.")
        else:
            summary_parts.append("자막 분석에 실패했습니다.")
            
        summary = " | ".join(summary_parts)
        
        # 기본 태그 생성 (AI 없이, 메타데이터 기반)
        tags = []
        
        # YouTube 메타데이터에서 태그 추출
        if metadata.get('tags'):
            youtube_tags = metadata['tags'][:5]  # 최대 5개
            tags.extend([tag for tag in youtube_tags if isinstance(tag, str) and len(tag) > 1])
        
        # 카테고리에서 태그 추출
        if metadata.get('categories'):
            for category in metadata['categories'][:2]:  # 최대 2개
                if isinstance(category, str) and len(category) > 1:
                    tags.append(category)
        
        # 항상 'YouTube' 태그 추가 (기본 식별자)
        if 'YouTube' not in tags and 'youtube' not in [tag.lower() for tag in tags]:
            tags.append('YouTube')
        
        # 기본 태그가 부족하면 일반적인 태그 추가
        if len(tags) < 3:
            basic_tags = ['동영상', '미디어']
            tags.extend([tag for tag in basic_tags if tag not in tags])
        
        # 중복 제거 및 최대 5개 제한
        tags = list(dict.fromkeys(tags))[:5]  # 중복 제거 후 5개 제한
        
        # 기본 카테고리 결정 (AI 없이)
        category = '일반'
        
        # YouTube 카테고리가 있으면 사용
        if metadata.get('categories') and len(metadata['categories']) > 0:
            youtube_category = metadata['categories'][0]
            if isinstance(youtube_category, str):
                category = youtube_category
        
        # 제목이나 태그를 기반으로 간단한 카테고리 분류
        title_lower = title.lower()
        if any(word in title_lower for word in ['tutorial', '튜토리얼', '강의', '배우기', 'how to']):
            category = '교육'
        elif any(word in title_lower for word in ['music', '음악', 'song', '노래']):
            category = '음악'
        elif any(word in title_lower for word in ['game', '게임', 'gaming']):
            category = '게임'
        elif any(word in title_lower for word in ['tech', '기술', 'technology', '개발']):
            category = '기술'
        elif any(word in title_lower for word in ['news', '뉴스', '새소식']):
            category = '뉴스'
        
        return {
            'summary': summary,
            'tags': tags,
            'category': category
        }

# 서비스 인스턴스 생성 (싱글톤 패턴)
clipper_service = ClipperService()

# 의존성 주입용 함수
def get_clipper_service() -> ClipperService:
    """ClipperService 인스턴스 반환"""
    return clipper_service
