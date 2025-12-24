"""개인화 서비스

태그/카테고리 추천을 사용자별로 개인화합니다.
"""
import math
from datetime import datetime

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_embedding
from app.core.logging import get_logger
from app.domains.ai.personalization.repository import PersonalizationRepository
from app.domains.ai.personalization.types import ScoredCategory, ScoredTag

logger = get_logger(__name__)


class PersonalizationService:
    """개인화 서비스

    태그/카테고리 추천 시 다음 요소를 고려하여 점수를 계산합니다:
    - base_score: LLM 제안 순서 기반 점수
    - personalization_score: 사용자 과거 태그와의 유사도 × 빈도 가중치
    - recency_score: 최근 사용한 태그일수록 높은 점수
    - global_popularity_score: 전체 사용자의 사용 빈도

    최종 점수:
    final_score =
        base_score + w1*personalization + w2*recency + w3*popularity
    """

    def __init__(
        self,
        session: AsyncSession,
        personalization_weight: float = 0.5,
        recency_weight: float = 0.2,
        popularity_weight: float = 0.1,
    ):
        """
        Args:
            session: DB 세션
            personalization_weight: 개인화 점수 가중치 (기본 0.5)
            recency_weight: 최근성 점수 가중치 (기본 0.2)
            popularity_weight: 인기도 점수 가중치 (기본 0.1)
        """
        self.session = session
        self.repository = PersonalizationRepository(session)
        self.w1 = personalization_weight
        self.w2 = recency_weight
        self.w3 = popularity_weight

    def _cosine_similarity(
        self, vec1: list[float], vec2: list[float]
    ) -> float:
        """코사인 유사도 계산

        Args:
            vec1: 벡터 1
            vec2: 벡터 2

        Returns:
            코사인 유사도 (0.0~1.0)
        """
        vec1_arr = np.array(vec1)
        vec2_arr = np.array(vec2)

        dot_product = np.dot(vec1_arr, vec2_arr)
        norm1 = np.linalg.norm(vec1_arr)
        norm2 = np.linalg.norm(vec2_arr)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _calculate_base_score(self, index: int, total: int) -> float:
        """LLM 제안 순서 기반 점수 계산

        Args:
            index: 후보 태그의 순서 (0부터 시작)
            total: 전체 후보 태그 수

        Returns:
            base_score (0.0~1.0, 첫 번째일수록 높음)
        """
        # 선형 감소: 첫 번째 = 1.0, 마지막 = 0.1
        return 1.0 - (0.9 * index / max(total - 1, 1))

    async def _calculate_personalization_score(
        self, candidate_tag: str, user_id: int
    ) -> float:
        """개인화 점수 계산

        사용자의 과거 태그와 후보 태그의 유사도 및 빈도를 기반으로 점수 계산

        Args:
            candidate_tag: 후보 태그
            user_id: 사용자 ID

        Returns:
            personalization_score (0.0~1.0)
        """
        # 사용자 태그 사용 통계 조회
        user_tags = await self.repository.get_user_tag_stats(user_id)

        if not user_tags:
            # 콜드 스타트: 사용자 태그 없음 → 점수 0
            return 0.0

        # 후보 태그 임베딩 생성
        try:
            candidate_embedding = await create_embedding(
                candidate_tag, self.session
            )
        except Exception as e:
            logger.warning(
                f"Failed to create embedding for tag '{candidate_tag}': {e}"
            )
            return 0.0

        # 각 사용자 태그와의 유사도 계산
        max_score = 0.0
        for user_tag in user_tags:
            if user_tag["embedding_vector"] is None:
                continue

            similarity = self._cosine_similarity(
                candidate_embedding, user_tag["embedding_vector"]
            )

            # 점수 = 유사도 × log(빈도 + 1)
            score = similarity * math.log(user_tag["use_count"] + 1)
            max_score = max(max_score, score)

        # 정규화 (최대값이 1.0이 되도록)
        # log(50 + 1) ≈ 3.93이므로, 최대 점수는 약 1.0 × 3.93 = 3.93
        # 0.25로 나누면 대략 0.0~1.0 범위
        normalized_score = min(max_score / 0.25, 1.0)

        return normalized_score

    async def _calculate_recency_score(
        self, candidate_tag: str, user_id: int
    ) -> float:
        """최근성 점수 계산

        사용자가 최근에 사용한 태그일수록 높은 점수

        Args:
            candidate_tag: 후보 태그
            user_id: 사용자 ID

        Returns:
            recency_score (0.0~1.0)
        """
        user_tags = await self.repository.get_user_tag_stats(user_id)

        if not user_tags:
            return 0.0

        # 후보 태그와 동일한 태그를 사용자가 사용한 적이 있는지 확인
        matching_tag = next(
            (
                t
                for t in user_tags
                if t["tag_name"].lower() == candidate_tag.lower()
            ),
            None,
        )

        if not matching_tag or matching_tag["last_used_at"] is None:
            return 0.0

        # 마지막 사용 시점으로부터 경과 일수
        days_ago = (datetime.now() - matching_tag["last_used_at"]).days

        # 지수 감쇠: 오늘 = 1.0, 30일 전 = ~0.5, 90일 전 = ~0.25
        recency_score = math.exp(-days_ago / 30.0)

        return recency_score

    async def _calculate_popularity_score(self, candidate_tag: str) -> float:
        """전역 인기도 점수 계산

        전체 사용자들이 많이 사용한 태그일수록 높은 점수

        Args:
            candidate_tag: 후보 태그

        Returns:
            popularity_score (0.0~1.0)
        """
        global_stats = await self.repository.get_global_tag_stats(limit=100)

        if not global_stats:
            return 0.0

        # 후보 태그의 전역 사용 횟수 확인
        matching_stat = next(
            (
                s
                for s in global_stats
                if s["tag_name"].lower() == candidate_tag.lower()
            ),
            None,
        )

        if not matching_stat:
            return 0.0

        # 상위 태그의 최대 사용 횟수
        max_use_count = global_stats[0]["total_use_count"]

        # 정규화: 최다 사용 태그 = 1.0
        max_use_count_value = float(max_use_count)
        total_use_count = float(matching_stat["total_use_count"])

        popularity_score = total_use_count / max(max_use_count_value, 1.0)

        return popularity_score

    async def personalize_tags(
        self,
        candidate_tags: list[str],
        user_id: int,
        count: int = 5,
    ) -> list[str]:
        """태그 개인화 추천

        LLM이 제안한 후보 태그들을 개인화하여 상위 N개 반환

        Args:
            candidate_tags: LLM이 제안한 후보 태그 리스트
            user_id: 사용자 ID
            count: 반환할 태그 수

        Returns:
            개인화된 태그 리스트 (최대 count개)
        """
        if not candidate_tags:
            return []

        logger.info(
            f"Personalizing tags for user {user_id}: "
            f"{len(candidate_tags)} candidates → {count} results"
        )

        scored_tags: list[ScoredTag] = []

        for index, tag in enumerate(candidate_tags):
            # 1. Base score (LLM 제안 순서)
            base_score = self._calculate_base_score(index, len(candidate_tags))

            # 2. Personalization score (유사도 × 빈도)
            personalization_score = (
                await self._calculate_personalization_score(tag, user_id)
            )

            # 3. Recency score (최근성)
            recency_score = await self._calculate_recency_score(tag, user_id)

            # 4. Popularity score (전역 인기도)
            popularity_score = await self._calculate_popularity_score(tag)

            # 최종 점수 계산
            final_score = (
                base_score
                + self.w1 * personalization_score
                + self.w2 * recency_score
                + self.w3 * popularity_score
            )

            scored_tags.append(
                {
                    "tag": tag,
                    "final_score": final_score,
                    "base_score": base_score,
                    "personalization_score": personalization_score,
                    "recency_score": recency_score,
                    "popularity_score": popularity_score,
                }
            )

            logger.debug(
                f"Tag '{tag}': final={final_score:.3f} "
                f"(base={base_score:.3f}, "
                f"pers={personalization_score:.3f}, "
                f"rec={recency_score:.3f}, "
                f"pop={popularity_score:.3f})"
            )

        # 최종 점수로 정렬
        scored_tags.sort(key=lambda x: x["final_score"], reverse=True)

        # 상위 N개 반환
        result = [item["tag"] for item in scored_tags[:count]]

        logger.info(f"Personalized tags: {result}")

        return result

    async def personalize_category(
        self,
        candidate_categories: list[str],
        user_id: int,
    ) -> str:
        """카테고리 개인화 추천

        LLM이 제안한 후보 카테고리들 중 최적의 1개 선택

        Args:
            candidate_categories: LLM이 제안한 후보 카테고리 리스트
            user_id: 사용자 ID

        Returns:
            개인화된 카테고리 (1개)
        """
        if not candidate_categories:
            return ""

        logger.info(
            f"Personalizing category for user {user_id}: "
            f"{len(candidate_categories)} candidates"
        )

        # 카테고리도 태그와 동일한 로직 적용
        # (카테고리용 별도 메서드를 만들 수도 있지만, 현재는 태그 메서드 재사용)
        scored_categories: list[ScoredCategory] = []

        for index, category in enumerate(candidate_categories):
            base_score = self._calculate_base_score(
                index, len(candidate_categories)
            )

            # 카테고리용 개인화 점수 (향후 별도 구현 가능)
            # 현재는 태그와 동일한 로직 사용
            personalization_score = (
                await self._calculate_personalization_score(category, user_id)
            )

            final_score = base_score + self.w1 * personalization_score

            scored_categories.append(
                {
                    "category": category,
                    "final_score": final_score,
                }
            )

        # 최종 점수로 정렬
        scored_categories.sort(key=lambda x: x["final_score"], reverse=True)

        result = scored_categories[0]["category"]

        logger.info(f"Personalized category: {result}")

        return result

    async def update_tag_usage(self, user_id: int, tags: list[str]) -> None:
        """콘텐츠 동기화 시 태그 사용 통계 업데이트

        사용자가 선택한 태그들을 마스터 테이블에 추가하고,
        사용자별 태그 사용 통계를 업데이트합니다.

        Args:
            user_id: 사용자 ID
            tags: 사용자가 선택한 태그 리스트
        """
        if not tags:
            return

        logger.info(f"Updating tag usage for user {user_id}: {len(tags)} tags")

        for tag_name in tags:
            # 1. 태그 마스터에 추가 (없으면 생성)
            # 임베딩은 나중에 배치로 생성하거나, 개인화 시 생성
            tag = await self.repository.get_or_create_tag(tag_name)

            # 2. 사용자 태그 사용 통계 업데이트
            await self.repository.upsert_user_tag_usage(
                user_id=user_id,
                tag_id=tag.id,
            )

        logger.info(f"Tag usage updated for user {user_id}: {tags}")

    async def update_category_usage(self, user_id: int, category: str) -> None:
        """콘텐츠 동기화 시 카테고리 사용 통계 업데이트

        사용자가 선택한 카테고리를 마스터 테이블에 추가하고,
        사용자별 카테고리 사용 통계를 업데이트합니다.

        Args:
            user_id: 사용자 ID
            category: 사용자가 선택한 카테고리
        """
        if not category:
            return

        logger.info(
            f"Updating category usage for user {user_id}: '{category}'"
        )

        # 1. 카테고리 마스터에 추가 (없으면 생성)
        # 임베딩은 나중에 배치로 생성하거나, 개인화 시 생성
        category_obj = await self.repository.get_or_create_category(category)

        # 2. 사용자 카테고리 사용 통계 업데이트
        await self.repository.upsert_user_category_usage(
            user_id=user_id,
            category_id=category_obj.id,
        )

        logger.info(f"Category usage updated for user {user_id}: '{category}'")
