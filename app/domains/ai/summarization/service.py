"""AI summarization 서비스
AI 요약 생성 관련 비즈니스 로직 계층입니다.
"""
import json
from datetime import timedelta
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMMessage, LLMTier, call_with_fallback
from app.core.logging import get_logger
from app.core.middlewares.context import get_request_id
from app.core.utils.datetime import now_utc
from app.domains.ai.embedding.service import EmbeddingService
from app.domains.ai.exceptions import SummarizationFailedException
from app.domains.ai.models import SummaryCache
from app.domains.ai.personalization.service import PersonalizationService
from app.domains.ai.repository import AIRepository
from app.domains.ai.schemas import SummarizeResponse
from app.domains.ai.summarization import prompts
from app.domains.ai.summarization.types import SummaryPipelineResult
from app.domains.ai.utils import parsers

logger = get_logger(__name__)


class SummarizationService:
    """AI 요약 서비스"""

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        personalization_service: Optional[PersonalizationService] = None,
    ):
        self.session = session
        self.repository = AIRepository(session)
        # embedding_service를 DI로 받되, 없으면 동일 세션으로 생성해서 재사용
        self.embedding_service = embedding_service or EmbeddingService(session)
        # personalization_service를 DI로 받되, 없으면 동일 세션으로 생성해서 재사용
        self.personalization_service = (
            personalization_service or PersonalizationService(session)
        )

    async def _get_cached_summary(
        self,
        cache_key: str,
        user_id: int,
        url: str,
        tag_count: int = 5,
    ) -> Optional[dict]:
        cached = await self.repository.get_summary_cache(cache_key)
        if not cached:
            logger.info(
                "Summary cache miss",
                extra={
                    "url": url,
                    "user_id": user_id,
                    "content_hashs": cache_key,
                    "request_id": get_request_id(),
                },
            )
            return None

        logger.info(
            "Summary cache hit",
            extra={
                "url": url,
                "user_id": user_id,
                "content_hashs": cache_key,
                "request_id": get_request_id(),
            },
        )
        candidate_categories = cached.candidate_categories or []
        candidate_tags = cached.candidate_tags or []

        # 캐시 히트 시에도 개인화 적용
        personalized_tags = (
            await self.personalization_service.personalize_tags(
                candidate_tags=candidate_tags,
                user_id=user_id,
                count=tag_count,
            )
        )

        personalized_category = (
            await self.personalization_service.personalize_category(
                candidate_categories=candidate_categories,
                user_id=user_id,
            )
        )

        return {
            "content_hash": cached.content_hash or cache_key,
            "extracted_text": cached.extracted_text or "",
            "summary": cached.summary or "",
            "tags": personalized_tags,
            "category": personalized_category,
            "candidate_tags": candidate_tags,
            "candidate_categories": candidate_categories,
            "cached": True,
        }

    async def _prepare_transcript_and_strategy(
        self,
        url: str,
    ) -> tuple[str, Optional[object]]:
        youtube_id = parsers.extract_youtube_video_id(url)
        youtube_transcript = parsers.get_youtube_transcript(youtube_id)
        chunk_strategy = await self.embedding_service.get_chunk_strategy(
            content_type="youtube"
        )
        return youtube_transcript, chunk_strategy

    async def _prepare_text_and_strategy(
        self,
        html_content: str,
    ) -> tuple[str, Optional[object]]:
        extracted_text = parsers.extract_text_from_html(html_content)
        chunk_strategy = await self.embedding_service.get_chunk_strategy(
            content_type="webpage"
        )

        # TODO : 도메인 추출 후 청크 분리 로직 적용할 수 있도록
        # TODO : 백그라운드 워커로 임베딩 생성 분리 고려
        # TODO : 요약 과정에서 임베딩 필요성 재검토
        #   요약 테이블에서 임베딩 삭제고려
        #   사용자가 저장한 콘텐츠에 대해서만 임베딩 생성이 원칙
        #   캐싱된 내용을 미리 임베딩하면 더 효율적일 수 있으나, 흐름을 고려해야함
        return extracted_text, chunk_strategy

    async def _prepare_pdf_text_and_strategy(
        self,
        pdf_content: bytes,
    ) -> tuple[str, Optional[object]]:
        extracted_text = parsers.extract_text_from_pdf(pdf_content)
        chunk_strategy = await self.embedding_service.get_chunk_strategy(
            content_type="pdf"
        )
        return extracted_text, chunk_strategy

    async def _run_llm_pipeline(
        self,
        extracted_text: str,
        summary_prompt: str = prompts.WEBPAGE_SUMMARY_PROMPT,
        max_summary_tokens: int = 400,
        prompt_kwargs: Optional[dict] = None,
    ) -> SummaryPipelineResult:
        """LLM 파이프라인 실행 (요약 + 태그 + 카테고리)

        Args:
            extracted_text: 추출된 텍스트
            summary_prompt: 요약 프롬프트 템플릿
            max_summary_tokens: 요약 최대 토큰 수
            prompt_kwargs: 프롬프트 포맷 인자

        Returns:
            SummaryPipelineResult: 요약, 태그, 카테고리 결과
        """
        try:
            prompt_data = prompt_kwargs or {"content": extracted_text}
            summary_result = await call_with_fallback(
                tier=LLMTier.LIGHT,
                messages=[
                    LLMMessage(
                        role="user",
                        content=summary_prompt.format(**prompt_data),
                    )
                ],
                temperature=0.3,
                max_tokens=max_summary_tokens,
            )

            tag_result = await call_with_fallback(
                tier=LLMTier.LIGHT,
                messages=[
                    LLMMessage(
                        role="user",
                        content=prompts.TAG_EXTRACTION_PROMPT.format(
                            summary=summary_result.content.strip()
                        ),
                    )
                ],
                temperature=0.2,
                max_tokens=200,
            )

            # 카테고리 후보 목록 조회
            # TODO : 개인화 추천 로직 고민 필요
            #   키워드를 뽑은 이후, 카테고리 후보를 추출할지
            #   카테고리를 전달하여 후보를 뽑을지, 키워드 중심인 경우 태그와 병합 고려
            category_result = await call_with_fallback(
                tier=LLMTier.LIGHT,
                messages=[
                    LLMMessage(
                        role="user",
                        content=prompts.CATEGORY_PREDICTION_PROMPT.format(
                            summary=summary_result.content.strip()
                        ),
                    )
                ],
                temperature=0.2,
                max_tokens=150,
            )

            return SummaryPipelineResult(
                summary=summary_result,
                tags=tag_result,
                category=category_result,
            )
        except Exception as e:
            logger.error("LLM summarization failed", exc_info=e)
            raise SummarizationFailedException(
                detail_msg=f"LLM 요약 생성 실패: {str(e)}"
            )

    @staticmethod
    def _parse_json_array(raw: str) -> list[str]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("` \n")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            # Fallback: 파싱 실패 시 원본 문자열 사용
            pass
        return [cleaned] if cleaned else []

    async def _build_summary_data(
        self,
        extracted_text: str,
        pipeline_result: SummaryPipelineResult,
        user_id: int,
        tag_count: int,
    ) -> tuple[dict, int]:
        """요약 데이터 구성

        Args:
            extracted_text: 추출된 원본 텍스트
            pipeline_result: LLM 파이프라인 실행 결과
            user_id: 사용자 ID (개인화용)
            tag_count: 반환할 태그 수

        Returns:
            tuple[dict, int]: (요약 데이터, 총 WTU)
        """
        summary_text = pipeline_result.summary.content.strip()
        candidate_tags = self._parse_json_array(pipeline_result.tags.content)
        candidate_categories = self._parse_json_array(
            pipeline_result.category.content
        )

        # 개인화 추천 로직 적용
        personalized_tags = (
            await self.personalization_service.personalize_tags(
                candidate_tags=candidate_tags,
                user_id=user_id,
                count=tag_count,
            )
        )

        personalized_category = (
            await self.personalization_service.personalize_category(
                candidate_categories=candidate_categories,
                user_id=user_id,
            )
        )

        # WTU 계산 (SummaryPipelineResult의 메서드 활용)
        total_wtu = pipeline_result.calculate_total_wtu()

        content_hash = parsers.calculate_content_hash(extracted_text)
        summary_data = {
            "content_hash": content_hash,
            "extracted_text": extracted_text,
            "summary": summary_text,
            "tags": personalized_tags,
            "category": personalized_category,
            "candidate_tags": candidate_tags,
            "candidate_categories": candidate_categories,
            "cached": False,
        }
        return summary_data, total_wtu

    async def _save_cache(
        self,
        cache_key: str,
        summary_data: dict,
        total_tokens: int,
        cache_type: str = "webpage",
    ) -> None:
        # 기존 동일 cache_key/type 캐시가 있으면 교체 (UPSERT 대용)
        await self.session.execute(
            delete(SummaryCache).where(
                SummaryCache.cache_key == cache_key,
                SummaryCache.cache_type == cache_type,
            )
        )

        summary_cache = SummaryCache(
            cache_key=cache_key,
            cache_type=cache_type,
            content_hash=summary_data["content_hash"],
            extracted_text=summary_data["extracted_text"],
            summary=summary_data["summary"],
            candidate_tags=summary_data["candidate_tags"],
            candidate_categories=summary_data["candidate_categories"],
            expires_at=now_utc() + timedelta(days=30),
            wtu_cost=total_tokens,
        )
        self.session.add(summary_cache)
        await self.session.flush()

    @staticmethod
    def _to_schema_dict(data: dict) -> dict:
        """Ensure response matches SummarizeResponse schema."""
        return SummarizeResponse(**data).model_dump()

    async def summarize_webpage(
        self,
        url: str,
        html_content: str,
        user_id: int,
        tag_count: int = 5,
        refresh: bool = False,
    ) -> dict:
        """웹페이지 요약 생성
        캐싱 로직:
        1. content_hashs = SHA256(url)
        2. 캐시 조회 (expires_at > now_utc())
        3. content_hash 비교
        4. 캐시 미스 or 변경 시:
        - HTML 파싱
        - 텍스트 청크 분할
        - 청크별 임베딩 생성
        - LLM 요약 생성
        - 태그/카테고리 후보 추출
        - 캐시 저장 (TTL 30일)
        5. 개인화 추천 적용

        Returns:
            {
                "content_hash": str,
                "extracted_text": str,
                "summary": str,
                "tags": list[str],  # 개인화된 상위 N개
                "category": str,    # 개인화된 최상위
                "candidate_tags": list[str],  # 전체 후보
                "candidate_categories": list[str],
                "cached": bool
            }
        # TODO : groq 도입 고려
            - 빠른 키워드 추출 및 요약 생성
            - 관련 레퍼런스
                https://github.com/Glitch-Jar/LLM-EYES
        """
        cache_key = parsers.calculate_content_hash(url)

        extracted_text, _ = await self._prepare_text_and_strategy(html_content)
        current_content_hash = parsers.calculate_content_hash(extracted_text)

        if refresh:
            logger.info(
                "Summary cache refresh requested",
                extra={
                    "url": url,
                    "user_id": user_id,
                    "content_hashs": cache_key,
                    "request_id": get_request_id(),
                },
            )
        else:
            cached_summary = await self._get_cached_summary(
                cache_key=cache_key,
                user_id=user_id,
                url=url,
                tag_count=tag_count,
            )
            if (
                cached_summary
                and cached_summary["content_hash"] == current_content_hash
            ):
                return self._to_schema_dict(cached_summary)

        pipeline_result = await self._run_llm_pipeline(extracted_text)
        summary_data, total_wtu = await self._build_summary_data(
            extracted_text,
            pipeline_result,
            user_id,
            tag_count,
        )
        await self._save_cache(
            cache_key=cache_key,
            summary_data=summary_data,
            total_tokens=total_wtu,
            cache_type="webpage",
        )

        return self._to_schema_dict(summary_data)

    async def summarize_youtube(
        self, url: str, user_id: int, tag_count: int = 5, refresh: bool = False
    ) -> dict:
        """유튜브 요약 생성

        캐싱 로직:
        1. content_hashs = SHA256(url)
        2. 캐시 조회 (expires_at > now_utc())
        3. content_hash 비교
        4. 캐시 미스 or 변경 시:
        - 자막 추출
        - 자막이 없으면 음성 -> 텍스트 변환
        - 텍스트 청크 분할
        - 청크별 임베딩 생성
        - LLM 요약 생성
        - 태그/카테고리 후보 추출
        - 캐시 저장 (TTL 30일)
        5. 개인화 추천 적용

        Returns:
            {
                "content_hash": str,
                "extracted_text": str,
                "summary": str,
                "tags": list[str],  # 개인화된 상위 N개
                "category": str,    # 개인화된 최상위
                "candidate_tags": list[str],  # 전체 후보
                "candidate_categories": list[str],
                "cached": bool
            }
        """

        cache_key = parsers.calculate_content_hash(url)

        extracted_text, _ = await self._prepare_transcript_and_strategy(url)
        current_content_hash = parsers.calculate_content_hash(extracted_text)

        if refresh:
            logger.info(
                "Summary cache refresh requested",
                extra={
                    "url": url,
                    "user_id": user_id,
                    "content_hashs": cache_key,
                    "request_id": get_request_id(),
                },
            )
        else:
            cached_summary = await self._get_cached_summary(
                cache_key=cache_key,
                user_id=user_id,
                url=url,
                tag_count=tag_count,
            )
            if (
                cached_summary
                and cached_summary["content_hash"] == current_content_hash
            ):
                return self._to_schema_dict(cached_summary)

        pipeline_result = await self._run_llm_pipeline(
            extracted_text,
            summary_prompt=prompts.YOUTUBE_SUMMARY_PROMPT,
            prompt_kwargs={
                "transcript": extracted_text,
            },
        )
        summary_data, total_wtu = await self._build_summary_data(
            extracted_text,
            pipeline_result,
            user_id,
            tag_count,
        )
        await self._save_cache(
            cache_key=cache_key,
            summary_data=summary_data,
            total_tokens=total_wtu,
            cache_type="youtube",
        )

        return self._to_schema_dict(summary_data)

    async def summarize_pdf(
        self,
        pdf_content: bytes,
        user_id: int,
        tag_count: int = 5,
        refresh: bool = False,
    ) -> dict:
        """PDF 요약 생성
        OCR 및 텍스트 추출 후 요약 생성

        캐싱 로직:
        1. content_hashs = SHA256(content)
        2. 캐시 조회 (expires_at > now_utc())
        3. content_hash 비교
        4. 캐시 미스 or 변경 시:
        - OCR 및 텍스트 추출
        - 텍스트 청크 분할
        - 청크별 임베딩 생성
        - LLM 요약 생성
        - 태그/카테고리 후보 추출
        - 캐시 저장 (TTL 30일)
        5. 개인화 추천 적용

        Returns:
            {
                "content_hash": str,
                "extracted_text": str,
                "summary": str,
                "tags": list[str],  # 개인화된 상위 N개
                "category": str,    # 개인화된 최상위
                "candidate_tags": list[str],  # 전체 후보
                "candidate_categories": list[str],
                "cached": bool
            }
        """
        cache_key = parsers.calculate_content_hash(pdf_content)

        if refresh:
            logger.info(
                "Summary cache refresh requested",
                extra={
                    "url": "pdf_content",
                    "user_id": user_id,
                    "content_hashs": cache_key,
                    "request_id": get_request_id(),
                },
            )
        else:
            cached_summary = await self._get_cached_summary(
                cache_key=cache_key,
                user_id=user_id,
                url="pdf_content",
                tag_count=tag_count,
            )
            if cached_summary:
                return self._to_schema_dict(cached_summary)

        extracted_text, _ = await self._prepare_pdf_text_and_strategy(
            pdf_content
        )
        pipeline_result = await self._run_llm_pipeline(
            extracted_text,
            summary_prompt=prompts.PDF_SUMMARY_PROMPT,
            max_summary_tokens=500,
        )
        summary_data, total_wtu = await self._build_summary_data(
            extracted_text,
            pipeline_result,
            user_id,
            tag_count,
        )
        await self._save_cache(
            cache_key=cache_key,
            summary_data=summary_data,
            total_tokens=total_wtu,
            cache_type="pdf",
        )

        return self._to_schema_dict(summary_data)
