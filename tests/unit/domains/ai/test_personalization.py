"""개인화 서비스 단위 테스트"""

import pytest

from app.domains.ai.personalization.service import PersonalizationService


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_personalize_tags_cold_start(db_session):
    """태그 개인화 - 콜드 스타트 (사용자 태그 없음)"""
    service = PersonalizationService(db_session)

    candidate_tags = ["AI", "머신러닝", "딥러닝", "Python", "데이터"]
    user_id = 9999  # 새 사용자 (태그 사용 이력 없음)

    # 콜드 스타트 시 LLM 추천 그대로 반환 (상위 3개)
    result = await service.personalize_tags(
        candidate_tags=candidate_tags, user_id=user_id, count=3
    )

    # 결과 검증
    assert len(result) == 3
    assert all(tag in candidate_tags for tag in result)
    # 순서는 LLM이 제안한 순서대로
    assert result == candidate_tags[:3]


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_personalize_tags_with_history(db_session, mock_embedding):
    """태그 개인화 - 사용 이력 있음"""
    from app.core.utils.datetime import now_utc
    from app.domains.ai.models import Tag, UserTagUsage

    service = PersonalizationService(db_session)

    user_id = 1

    # 기존 태그 생성
    tag1 = Tag(
        id=1,
        tag_name="AI",
        embedding_vector=[0.9] * 1536,
        created_at=now_utc(),
    )
    tag2 = Tag(
        id=2,
        tag_name="Python",
        embedding_vector=[0.1] * 1536,
        created_at=now_utc(),
    )

    db_session.add_all([tag1, tag2])
    await db_session.flush()

    # 사용자 태그 사용 통계
    usage1 = UserTagUsage(
        user_id=user_id,
        tag_id=tag1.id,
        use_count=10,
        last_used_at=now_utc(),
    )
    usage2 = UserTagUsage(
        user_id=user_id,
        tag_id=tag2.id,
        use_count=5,
        last_used_at=now_utc(),
    )

    db_session.add_all([usage1, usage2])
    await db_session.commit()

    # 후보 태그 (AI와 유사한 태그 포함)
    candidate_tags = ["머신러닝", "딥러닝", "JavaScript", "Java", "SQL"]

    # 개인화 추천
    result = await service.personalize_tags(
        candidate_tags=candidate_tags, user_id=user_id, count=3
    )

    # 결과 검증
    assert len(result) <= 3
    assert all(tag in candidate_tags for tag in result)


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_personalize_category_cold_start(db_session):
    """카테고리 개인화 - 콜드 스타트"""
    service = PersonalizationService(db_session)

    candidate_categories = ["기술", "경제", "문화", "스포츠"]
    user_id = 9999  # 새 사용자

    # 콜드 스타트 시 첫 번째 카테고리 반환
    result = await service.personalize_category(
        candidate_categories=candidate_categories, user_id=user_id
    )

    # 결과 검증
    assert result == "기술"  # 첫 번째 카테고리


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_update_tag_usage(db_session):
    """태그 사용 통계 업데이트 테스트"""
    from unittest.mock import patch

    from sqlalchemy import select

    from app.domains.ai.models import Tag, UserTagUsage

    service = PersonalizationService(db_session)

    user_id = 2
    tags = ["Python", "Django", "FastAPI"]

    # 임베딩 Mock
    async def mock_create_embedding(_text):
        return [0.1] * 1536  # 태그는 1536 차원

    with patch(
        "app.domains.ai.personalization.service.create_embedding",
        side_effect=mock_create_embedding,
    ):
        # 태그 사용 통계 업데이트
        await service.update_tag_usage(user_id=user_id, tags=tags)

        # 태그 마스터 확인
        query = select(Tag).where(Tag.tag_name.in_(tags))
        result = await db_session.execute(query)
        tag_models = result.scalars().all()

        # 모든 태그가 생성되어야 함
        assert len(tag_models) == 3

        # 사용 통계 확인
        query = select(UserTagUsage).where(UserTagUsage.user_id == user_id)
        result = await db_session.execute(query)
        usages = result.scalars().all()

        # 3개의 태그 사용 통계
        assert len(usages) == 3
        assert all(u.use_count == 1 for u in usages)


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_update_tag_usage_increment(db_session, mock_embedding):
    """태그 사용 카운트 증가 테스트"""
    from sqlalchemy import select

    from app.domains.ai.models import Tag, UserTagUsage

    service = PersonalizationService(db_session)

    user_id = 3
    tags = ["Python"]

    # 첫 번째 업데이트
    await service.update_tag_usage(user_id=user_id, tags=tags)

    # 두 번째 업데이트 (같은 태그)
    await service.update_tag_usage(user_id=user_id, tags=tags)

    # 사용 카운트 확인
    query = (
        select(UserTagUsage)
        .join(Tag)
        .where(UserTagUsage.user_id == user_id, Tag.tag_name == "Python")
    )
    result = await db_session.execute(query)
    usage = result.scalar_one()

    # 카운트가 2로 증가해야 함
    assert usage.use_count == 2


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_update_category_usage(db_session):
    """카테고리 사용 통계 업데이트 테스트"""
    from unittest.mock import patch

    from sqlalchemy import select

    from app.domains.ai.models import Category, UserCategoryUsage

    service = PersonalizationService(db_session)

    user_id = 4
    category = "기술"

    # 임베딩 Mock
    async def mock_create_embedding(_text):
        return [0.1] * 1536  # 카테고리는 1536 차원

    with patch(
        "app.domains.ai.personalization.service.create_embedding",
        side_effect=mock_create_embedding,
    ):
        # 카테고리 사용 통계 업데이트
        await service.update_category_usage(user_id=user_id, category=category)

        # 카테고리 마스터 확인
        query = select(Category).where(Category.category_name == category)
        result = await db_session.execute(query)
        category_model = result.scalar_one()

        assert category_model.category_name == "기술"

        # 사용 통계 확인
        query = select(UserCategoryUsage).where(
            UserCategoryUsage.user_id == user_id,
            UserCategoryUsage.category_id == category_model.id,
        )
        result = await db_session.execute(query)
        usage = result.scalar_one()

        assert usage.use_count == 1


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_personalization_scoring_algorithm(db_session):
    """개인화 스코어링 알고리즘 테스트"""
    from unittest.mock import patch

    from app.core.utils.datetime import now_utc
    from app.domains.ai.models import Tag, UserTagUsage

    service = PersonalizationService(db_session)

    user_id = 5

    # 기존 태그: "Python" (높은 빈도)
    tag = Tag(
        id=10,
        tag_name="Python",
        embedding_vector=[0.8] * 1536,
        created_at=now_utc(),
    )
    db_session.add(tag)
    await db_session.flush()

    usage = UserTagUsage(
        user_id=user_id,
        tag_id=tag.id,
        use_count=20,  # 높은 빈도
        last_used_at=now_utc(),
    )
    db_session.add(usage)
    await db_session.commit()

    # 후보 태그
    candidate_tags = ["Django", "FastAPI", "JavaScript"]

    # 임베딩 Mock
    async def mock_create_embedding(_text):
        return [0.1] * 1536

    with patch(
        "app.domains.ai.personalization.service.create_embedding",
        side_effect=mock_create_embedding,
    ):
        # 개인화 추천
        result = await service.personalize_tags(
            candidate_tags=candidate_tags, user_id=user_id, count=3
        )

        # 결과 검증 (스코어 계산이 정상 작동)
        assert len(result) <= 3


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_get_or_create_tag(db_session):
    """태그 조회 또는 생성 테스트"""
    from unittest.mock import patch

    from sqlalchemy import select

    from app.domains.ai.models import Tag
    from app.domains.ai.personalization.repository import (
        PersonalizationRepository,
    )

    repository = PersonalizationRepository(db_session)

    tag_name = "NewTag"

    # 임베딩 Mock
    async def mock_create_embedding(_text):
        return [0.1] * 1536

    with patch(
        "app.domains.ai.personalization.repository.create_embedding",
        side_effect=mock_create_embedding,
    ):
        # 첫 번째 호출 - 생성
        tag1 = await repository.get_or_create_tag(tag_name)
        assert tag1.tag_name == tag_name
        assert tag1.id is not None

        # 두 번째 호출 - 조회
        tag2 = await repository.get_or_create_tag(tag_name)
        assert tag2.id == tag1.id

        # DB에 한 개만 존재해야 함
        query = select(Tag).where(Tag.tag_name == tag_name)
        result = await db_session.execute(query)
        all_tags = result.scalars().all()
        assert len(all_tags) == 1


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_upsert_user_tag_usage(db_session):
    """사용자 태그 사용 카운트 UPSERT 테스트"""
    from sqlalchemy import select

    from app.core.utils.datetime import now_utc
    from app.domains.ai.models import Tag, UserTagUsage
    from app.domains.ai.personalization.repository import (
        PersonalizationRepository,
    )

    repository = PersonalizationRepository(db_session)

    user_id = 6
    tag = Tag(
        id=20,
        tag_name="TestTag",
        embedding_vector=[0.5] * 1536,
        created_at=now_utc(),
    )
    db_session.add(tag)
    await db_session.flush()

    # 첫 번째 UPSERT - INSERT
    await repository.upsert_user_tag_usage(user_id=user_id, tag_id=tag.id)

    query = select(UserTagUsage).where(
        UserTagUsage.user_id == user_id, UserTagUsage.tag_id == tag.id
    )
    result = await db_session.execute(query)
    usage = result.scalar_one()
    assert usage.use_count == 1

    # 두 번째 UPSERT - UPDATE
    await repository.upsert_user_tag_usage(user_id=user_id, tag_id=tag.id)

    result = await db_session.execute(query)
    usage = result.scalar_one()
    assert usage.use_count == 2  # 증가
