"""
Board Analytics Service - 보드 콘텐츠 분석 및 인사이트 생성 서비스
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from collections import Counter
import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.models import Board, BoardItem, BoardAnalytics, Item
from app.core.logging import get_logger
from app.core.config import settings
from app.ai.providers.router import ai_router
from app.ai.embedding.generators.openai_generator import OpenAIEmbeddingGenerator

logger = get_logger(__name__)


class BoardAnalyticsService:
    """보드 분석 서비스"""

    def __init__(self):
        self.embedding_generator = OpenAIEmbeddingGenerator()

    async def analyze_board(self, board_id: int, force_refresh: bool = False) -> Optional[BoardAnalytics]:
        """
        보드 전체 분석 수행
        """
        try:
            async with AsyncSessionLocal() as session:
                # 보드와 아이템 조회
                board_data = await self._get_board_with_items(session, board_id)
                if not board_data:
                    logger.warning(f"Board {board_id} not found or has no items")
                    return None

                board, items = board_data

                # 기존 분석 확인
                existing_analytics = await self._get_existing_analytics(session, board_id)
                
                # 강제 갱신이 아니고 최근 분석이 있으면 스킵
                if not force_refresh and existing_analytics and not existing_analytics.is_stale:
                    logger.info(f"Board {board_id} analysis is up to date")
                    return existing_analytics

                logger.info(f"Starting analysis for board {board_id} with {len(items)} items")

                # 1. 기본 통계 계산
                basic_stats = await self._calculate_basic_stats(items)
                
                # 2. 콘텐츠 요약 생성
                content_summary = await self._generate_content_summary(board, items)
                
                # 3. 카테고리 및 태그 분석
                category_analysis = await self._analyze_categories_and_tags(items)
                
                # 4. 토픽 임베딩 및 일관성 계산
                topic_analysis = await self._analyze_topics(items)
                
                # 5. 다양성 점수 계산
                diversity_score = await self._calculate_diversity_score(items)
                
                # 6. 아이템 관련도 계산
                relevance_score = await self._calculate_item_relevance(items, topic_analysis.get("embedding"))

                # 분석 결과 저장
                analytics = await self._save_analytics(
                    session=session,
                    board_id=board_id,
                    basic_stats=basic_stats,
                    content_summary=content_summary,
                    category_analysis=category_analysis,
                    topic_analysis=topic_analysis,
                    diversity_score=diversity_score,
                    relevance_score=relevance_score,
                    existing_analytics=existing_analytics
                )

                logger.info(f"Board {board_id} analysis completed successfully")
                return analytics

        except Exception as e:
            logger.error(f"Failed to analyze board {board_id}: {str(e)}")
            return None

    async def _get_board_with_items(self, session: AsyncSession, board_id: int) -> Optional[Tuple[Board, List[Item]]]:
        """보드와 연결된 아이템들 조회"""
        try:
            # 보드 조회
            board_result = await session.execute(
                select(Board).where(Board.id == board_id, Board.is_active == True)
            )
            board = board_result.scalar_one_or_none()
            
            if not board:
                return None

            # 보드 아이템들 조회
            items_result = await session.execute(
                select(Item)
                .join(BoardItem, Item.id == BoardItem.item_id)
                .where(BoardItem.board_id == board_id)
                .order_by(BoardItem.display_order)
            )
            items = items_result.scalars().all()

            return board, list(items)

        except Exception as e:
            logger.error(f"Failed to get board with items for {board_id}: {str(e)}")
            return None

    async def _get_existing_analytics(self, session: AsyncSession, board_id: int) -> Optional[BoardAnalytics]:
        """기존 분석 데이터 조회"""
        try:
            result = await session.execute(
                select(BoardAnalytics).where(BoardAnalytics.board_id == board_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get existing analytics for board {board_id}: {str(e)}")
            return None

    async def _calculate_basic_stats(self, items: List[Item]) -> Dict[str, Any]:
        """기본 통계 계산"""
        total_items = len(items)
        total_content_length = sum(
            (len(item.title or "") + len(item.content or "") + len(item.summary or ""))
            for item in items
        )
        
        return {
            "total_items": total_items,
            "total_content_length": total_content_length
        }

    async def _generate_content_summary(self, board: Board, items: List[Item]) -> Optional[str]:
        """보드 전체 콘텐츠 요약 생성"""
        try:
            if not items:
                return None

            # 상위 5개 아이템의 제목과 요약 추출
            content_snippets = []
            for item in items[:5]:
                snippet = f"제목: {item.title or 'N/A'}"
                if item.summary:
                    snippet += f"\n요약: {item.summary[:200]}..."
                elif item.content:
                    snippet += f"\n내용: {item.content[:200]}..."
                content_snippets.append(snippet)

            combined_content = "\n\n".join(content_snippets)
            
            # OpenAI를 사용해 보드 전체 요약 생성
            prompt = f"""다음은 "{board.title}" 보드의 주요 콘텐츠들입니다:

{combined_content}

이 보드의 전체적인 주제와 내용을 2-3문장으로 요약해주세요. 한국어로 작성해주세요."""

            # AI Router를 사용해 LLM 호출
            messages = [
                {"role": "system", "content": "당신은 콘텐츠 요약 전문가입니다."},
                {"role": "user", "content": prompt}
            ]
            
            ai_response = await ai_router.generate_chat_completion(
                messages=messages,
                model="gpt-4o-mini",  # 비용 효율적인 모델 사용
                max_tokens=200,
                temperature=0.3
            )
            
            response = ai_response.content
            
            return response.strip() if response else None

        except Exception as e:
            logger.error(f"Failed to generate content summary: {str(e)}")
            return None

    async def _analyze_categories_and_tags(self, items: List[Item]) -> Dict[str, Any]:
        """카테고리 및 태그 분석"""
        try:
            # 카테고리 분포
            categories = []
            for item in items:
                if item.categories:
                    if isinstance(item.categories, list):
                        categories.extend(item.categories)
                    elif isinstance(item.categories, dict):
                        categories.extend(item.categories.keys())

            category_counter = Counter(categories)
            dominant_categories = dict(category_counter.most_common(10))

            # 태그 분포 (가중치 기반)
            tags = []
            for item in items:
                if item.tags:
                    if isinstance(item.tags, list):
                        tags.extend(item.tags)
                    elif isinstance(item.tags, dict):
                        # 태그별 가중치가 있는 경우
                        for tag, weight in item.tags.items():
                            tags.extend([tag] * int(weight * 10))  # 가중치 반영

            tag_counter = Counter(tags)
            total_tags = sum(tag_counter.values())
            tag_distribution = {
                tag: count / total_tags for tag, count in tag_counter.most_common(15)
            } if total_tags > 0 else {}

            return {
                "dominant_categories": dominant_categories,
                "tag_distribution": tag_distribution
            }

        except Exception as e:
            logger.error(f"Failed to analyze categories and tags: {str(e)}")
            return {"dominant_categories": {}, "tag_distribution": {}}

    async def _analyze_topics(self, items: List[Item]) -> Dict[str, Any]:
        """토픽 분석 및 임베딩 생성"""
        try:
            if not items:
                return {"embedding": None, "coherence_score": 0.0}

            # 모든 아이템의 텍스트 결합
            combined_texts = []
            for item in items:
                text_parts = []
                if item.title:
                    text_parts.append(item.title)
                if item.summary:
                    text_parts.append(item.summary)
                elif item.content:
                    text_parts.append(item.content[:500])  # 첫 500자만
                
                combined_texts.append(" ".join(text_parts))

            # 전체 보드 텍스트
            board_text = " ".join(combined_texts)
            
            # 보드 주제 임베딩 생성
            board_embedding = await self.embedding_generator.generate(board_text)

            # 개별 아이템 임베딩과 일관성 계산
            coherence_score = 0.0
            if board_embedding and len(combined_texts) > 1:
                # 각 아이템별로 임베딩 생성
                similarities = []
                for text in combined_texts:
                    item_emb = await self.embedding_generator.generate(text)
                    if item_emb:
                        # 코사인 유사도 계산
                        similarity = np.dot(board_embedding, item_emb) / (
                            np.linalg.norm(board_embedding) * np.linalg.norm(item_emb)
                        )
                        similarities.append(similarity)
                
                coherence_score = np.mean(similarities) if similarities else 0.0

            return {
                "embedding": board_embedding if board_embedding is not None else None,
                "coherence_score": float(coherence_score)
            }

        except Exception as e:
            logger.error(f"Failed to analyze topics: {str(e)}")
            return {"embedding": None, "coherence_score": 0.0}

    async def _calculate_diversity_score(self, items: List[Item]) -> float:
        """콘텐츠 다양성 점수 계산"""
        try:
            if len(items) < 2:
                return 0.0

            # 카테고리 다양성
            categories = set()
            for item in items:
                if item.categories:
                    if isinstance(item.categories, list):
                        categories.update(item.categories)
                    elif isinstance(item.categories, dict):
                        categories.update(item.categories.keys())

            category_diversity = len(categories) / len(items)

            # URL 도메인 다양성
            domains = set()
            for item in items:
                url = getattr(item, 'url', None) or getattr(item, 'source_url', None)
                if url:
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc
                        if domain:
                            domains.add(domain)
                    except:
                        pass

            domain_diversity = len(domains) / len(items) if domains else 0.0

            # 콘텐츠 길이 다양성 (정규화된 표준편차)
            lengths = [len(item.content or "") for item in items]
            length_diversity = 0.0
            if lengths and max(lengths) > 0:
                length_std = np.std(lengths)
                length_mean = np.mean(lengths)
                length_diversity = min(length_std / length_mean, 1.0) if length_mean > 0 else 0.0

            # 최종 다양성 점수 (가중 평균)
            diversity_score = (
                category_diversity * 0.4 +
                domain_diversity * 0.3 +
                length_diversity * 0.3
            )

            return min(diversity_score, 1.0)

        except Exception as e:
            logger.error(f"Failed to calculate diversity score: {str(e)}")
            return 0.0

    async def _calculate_item_relevance(self, items: List[Item], board_embedding: Optional[List[float]]) -> float:
        """아이템들의 평균 관련도 계산"""
        try:
            if not items or not board_embedding:
                return 0.0

            # 각 아이템과 보드 주제의 관련도 계산
            relevance_scores = []
            board_vec = np.array(board_embedding)

            for item in items:
                # 아이템 텍스트 생성
                item_text = " ".join([
                    item.title or "",
                    item.summary or item.content[:300] or ""
                ]).strip()

                if item_text:
                    item_embedding = await self.embedding_generator.generate(item_text)
                    if item_embedding is not None:
                        item_vec = np.array(item_embedding)
                        # 코사인 유사도
                        similarity = np.dot(board_vec, item_vec) / (
                            np.linalg.norm(board_vec) * np.linalg.norm(item_vec)
                        )
                        relevance_scores.append(similarity)

            return float(np.mean(relevance_scores)) if relevance_scores else 0.0

        except Exception as e:
            logger.error(f"Failed to calculate item relevance: {str(e)}")
            return 0.0

    async def _save_analytics(
        self,
        session: AsyncSession,
        board_id: int,
        basic_stats: Dict[str, Any],
        content_summary: Optional[str],
        category_analysis: Dict[str, Any],
        topic_analysis: Dict[str, Any],
        diversity_score: float,
        relevance_score: float,
        existing_analytics: Optional[BoardAnalytics]
    ) -> BoardAnalytics:
        """분석 결과 저장"""
        try:
            now = datetime.now()

            if existing_analytics:
                # 기존 분석 업데이트
                existing_analytics.content_summary = content_summary
                existing_analytics.dominant_categories = category_analysis["dominant_categories"]
                existing_analytics.tag_distribution = category_analysis["tag_distribution"]
                existing_analytics.total_items = basic_stats["total_items"]
                existing_analytics.total_content_length = basic_stats["total_content_length"]
                existing_analytics.avg_item_relevance = relevance_score
                existing_analytics.content_diversity_score = diversity_score
                existing_analytics.topic_coherence_score = topic_analysis["coherence_score"]
                existing_analytics.topic_embedding = topic_analysis["embedding"]
                existing_analytics.analytics_version = "1.0"
                existing_analytics.last_analyzed_at = now
                existing_analytics.is_stale = False
                
                analytics = existing_analytics
            else:
                # 새 분석 생성
                analytics = BoardAnalytics(
                    board_id=board_id,
                    content_summary=content_summary,
                    dominant_categories=category_analysis["dominant_categories"],
                    tag_distribution=category_analysis["tag_distribution"],
                    total_items=basic_stats["total_items"],
                    total_content_length=basic_stats["total_content_length"],
                    avg_item_relevance=relevance_score,
                    content_diversity_score=diversity_score,
                    topic_coherence_score=topic_analysis["coherence_score"],
                    topic_embedding=topic_analysis["embedding"],
                    analytics_version="1.0",
                    last_analyzed_at=now,
                    is_stale=False
                )
                session.add(analytics)

            await session.commit()
            
            logger.info(f"Analytics saved for board {board_id}")
            return analytics

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to save analytics for board {board_id}: {str(e)}")
            raise

    async def mark_analytics_stale(self, board_id: int) -> bool:
        """분석 결과를 오래된 것으로 표시"""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(BoardAnalytics).where(BoardAnalytics.board_id == board_id)
                )
                analytics = result.scalar_one_or_none()
                
                if analytics:
                    analytics.is_stale = True
                    await session.commit()
                    logger.info(f"Marked analytics as stale for board {board_id}")
                    return True
                
                return False

        except Exception as e:
            logger.error(f"Failed to mark analytics stale for board {board_id}: {str(e)}")
            return False

    async def get_board_insights(self, board_id: int) -> Optional[Dict[str, Any]]:
        """보드 인사이트 생성"""
        try:
            async with AsyncSessionLocal() as session:
                # 분석 데이터 조회
                result = await session.execute(
                    select(BoardAnalytics).where(BoardAnalytics.board_id == board_id)
                )
                analytics = result.scalar_one_or_none()
                
                if not analytics:
                    return None

                insights = {
                    "board_id": board_id,
                    "content_quality": self._assess_content_quality(analytics),
                    "organization_suggestions": self._generate_organization_suggestions(analytics),
                    "content_gaps": self._identify_content_gaps(analytics),
                    "engagement_potential": self._assess_engagement_potential(analytics)
                }

                return insights

        except Exception as e:
            logger.error(f"Failed to generate insights for board {board_id}: {str(e)}")
            return None

    def _assess_content_quality(self, analytics: BoardAnalytics) -> Dict[str, Any]:
        """콘텐츠 품질 평가"""
        quality_score = (
            (analytics.topic_coherence_score or 0) * 0.4 +
            (analytics.content_diversity_score or 0) * 0.3 +
            (analytics.avg_item_relevance or 0) * 0.3
        )
        
        quality_level = "높음" if quality_score > 0.7 else "보통" if quality_score > 0.4 else "낮음"
        
        return {
            "score": quality_score,
            "level": quality_level,
            "coherence": analytics.topic_coherence_score or 0,
            "diversity": analytics.content_diversity_score or 0,
            "relevance": analytics.avg_item_relevance or 0
        }

    def _generate_organization_suggestions(self, analytics: BoardAnalytics) -> List[str]:
        """조직화 제안 생성"""
        suggestions = []
        
        if analytics.content_diversity_score and analytics.content_diversity_score < 0.3:
            suggestions.append("다양한 관점의 콘텐츠를 추가하여 보드의 다양성을 높여보세요.")
        
        if analytics.topic_coherence_score and analytics.topic_coherence_score < 0.5:
            suggestions.append("주제와 관련성이 낮은 아이템들을 정리하여 일관성을 높여보세요.")
        
        if analytics.total_items < 5:
            suggestions.append("더 많은 콘텐츠를 추가하여 보드를 풍성하게 만들어보세요.")
        
        if analytics.dominant_categories and len(analytics.dominant_categories) > 5:
            suggestions.append("유사한 카테고리들을 그룹핑하여 정리해보세요.")

        return suggestions

    def _identify_content_gaps(self, analytics: BoardAnalytics) -> List[str]:
        """콘텐츠 부족 영역 식별"""
        gaps = []
        
        # 카테고리 분석 기반 제안
        if analytics.dominant_categories:
            total_categorized = sum(analytics.dominant_categories.values())
            if total_categorized < analytics.total_items * 0.8:
                gaps.append("카테고리가 지정되지 않은 콘텐츠가 많습니다.")
        
        # 콘텐츠 길이 기반 제안
        avg_length = analytics.total_content_length / analytics.total_items if analytics.total_items > 0 else 0
        if avg_length < 100:
            gaps.append("콘텐츠의 상세 설명이나 요약이 부족합니다.")

        return gaps

    def _assess_engagement_potential(self, analytics: BoardAnalytics) -> Dict[str, Any]:
        """참여 가능성 평가"""
        engagement_score = 0.0
        
        # 다양성 점수가 높을수록 참여 가능성 높음
        if analytics.content_diversity_score:
            engagement_score += analytics.content_diversity_score * 0.3
        
        # 적절한 아이템 수 (10-20개가 최적)
        item_score = min(analytics.total_items / 15, 1.0) if analytics.total_items <= 15 else max(1.0 - (analytics.total_items - 15) / 20, 0.3)
        engagement_score += item_score * 0.4
        
        # 주제 일관성
        if analytics.topic_coherence_score:
            engagement_score += analytics.topic_coherence_score * 0.3

        engagement_level = "높음" if engagement_score > 0.7 else "보통" if engagement_score > 0.4 else "낮음"

        return {
            "score": engagement_score,
            "level": engagement_level,
            "optimal_item_range": "10-20개",
            "current_items": analytics.total_items
        }


# 싱글톤 서비스 인스턴스
board_analytics_service = BoardAnalyticsService()