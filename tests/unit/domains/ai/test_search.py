"""검색 서비스 단위 테스트"""

import pytest

from app.domains.ai.search.repository import AISearchRepository
from app.domains.ai.search.service import AISearchService
from app.domains.ai.search.types import SearchFilters


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_vector_search(db_session, mock_embedding):
    """벡터 검색 테스트"""
    from app.core.utils.datetime import now_utc
    from app.domains.ai.models import ContentEmbeddingMetadata
    from app.domains.contents.models import Content

    repository = AISearchRepository(db_session)

    # 테스트 콘텐츠 및 임베딩 생성
    content = Content(
        id=1,
        user_id=1,
        content_type="webpage",
        source_url="https://example.com",
        title="AI Technology",
        summary="Latest AI trends",
        embedding_status="completed",
        created_at=now_utc(),
    )
    db_session.add(content)
    await db_session.flush()

    embedding = ContentEmbeddingMetadata(
        content_id=content.id,
        chunk_index=0,
        chunk_content="AI technology content",
        embedding_vector=[0.1] * 3072,
        embedding_model="text-embedding-3-large",
        created_at=now_utc(),
    )
    db_session.add(embedding)
    await db_session.commit()

    # 벡터 검색 실행
    query_embedding = [0.1] * 3072
    results, total = await repository.vector_search(
        query_embedding=query_embedding,
        user_id=1,
        filters=None,
        page=1,
        size=20,
        threshold=0.0,  # 낮은 threshold로 모든 결과 포함
    )

    # 결과 검증
    assert total >= 1
    assert len(results) >= 1
    assert results[0]["content_id"] == content.id
    assert results[0]["title"] == "AI Technology"
    assert "similarity" in results[0]


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_keyword_search(db_session):
    """키워드 검색 테스트"""
    from app.core.utils.datetime import now_utc
    from app.domains.contents.models import Content

    repository = AISearchRepository(db_session)

    # 테스트 콘텐츠 생성
    content = Content(
        id=2,
        user_id=1,
        content_type="webpage",
        source_url="https://example.com/ai",
        title="Artificial Intelligence Trends",
        summary="The latest trends in AI technology",
        created_at=now_utc(),
    )
    db_session.add(content)
    await db_session.commit()

    # 키워드 검색 실행
    results, total = await repository.keyword_search(
        query="AI technology",
        user_id=1,
        filters=None,
        page=1,
        size=20,
    )

    # 결과 검증
    assert total >= 1
    assert len(results) >= 1
    # content_id가 결과에 포함되어야 함
    content_ids = [r["content_id"] for r in results]
    assert content.id in content_ids
    assert "rank" in results[0]


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_hybrid_search_score_combination(db_session, mock_embedding):
    """하이브리드 검색 - 스코어 조합 테스트"""
    from app.core.utils.datetime import now_utc
    from app.domains.ai.models import ContentEmbeddingMetadata
    from app.domains.contents.models import Content

    repository = AISearchRepository(db_session)

    # 테스트 콘텐츠 생성 (벡터 + 키워드 모두 매칭)
    content = Content(
        id=3,
        user_id=1,
        content_type="webpage",
        source_url="https://example.com/ml",
        title="Machine Learning Guide",
        summary="Complete guide to machine learning",
        embedding_status="completed",
        created_at=now_utc(),
    )
    db_session.add(content)
    await db_session.flush()

    embedding = ContentEmbeddingMetadata(
        content_id=content.id,
        chunk_index=0,
        chunk_content="Machine learning algorithms",
        embedding_vector=[0.2] * 3072,
        embedding_model="text-embedding-3-large",
        created_at=now_utc(),
    )
    db_session.add(embedding)
    await db_session.commit()

    # 하이브리드 검색 실행
    query = "machine learning"
    query_embedding = [0.2] * 3072
    results, total = await repository.hybrid_search(
        query=query,
        query_embedding=query_embedding,
        user_id=1,
        filters=None,
        page=1,
        size=20,
        alpha=0.7,  # 벡터 70%, 키워드 30%
        threshold=0.0,
    )

    # 결과 검증
    assert total >= 1
    assert len(results) >= 1

    # 스코어 필드 확인
    result = results[0]
    assert "final_score" in result
    assert "vector_score" in result
    assert "keyword_score" in result

    # final_score = (vector_score * 0.7) + (keyword_score * 0.3)
    expected_score = (result["vector_score"] * 0.7) + (
        result["keyword_score"] * 0.3
    )
    assert abs(result["final_score"] - expected_score) < 0.001


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_search_with_filters(db_session, mock_embedding):
    """필터 적용 검색 테스트"""
    from app.core.utils.datetime import now_utc
    from app.domains.ai.models import ContentEmbeddingMetadata
    from app.domains.contents.models import Content

    repository = AISearchRepository(db_session)

    # 다양한 타입의 콘텐츠 생성
    webpage_content = Content(
        id=4,
        user_id=1,
        content_type="webpage",
        source_url="https://example.com",
        title="Web Article",
        summary="Article content",
        embedding_status="completed",
        created_at=now_utc(),
    )
    youtube_content = Content(
        id=5,
        user_id=1,
        content_type="youtube",
        source_url="https://youtube.com/watch?v=test",
        title="YouTube Video",
        summary="Video content",
        embedding_status="completed",
        created_at=now_utc(),
    )

    db_session.add_all([webpage_content, youtube_content])
    await db_session.flush()

    # 임베딩 추가
    for content in [webpage_content, youtube_content]:
        embedding = ContentEmbeddingMetadata(
            content_id=content.id,
            chunk_index=0,
            chunk_content="test content",
            embedding_vector=[0.3] * 3072,
            embedding_model="text-embedding-3-large",
            created_at=now_utc(),
        )
        db_session.add(embedding)

    await db_session.commit()

    # content_type 필터 적용
    filters = SearchFilters(content_type=["webpage"])

    results, total = await repository.vector_search(
        query_embedding=[0.3] * 3072,
        user_id=1,
        filters=filters,
        page=1,
        size=20,
        threshold=0.0,
    )

    # webpage만 검색되어야 함
    assert all(r["content_type"] == "webpage" for r in results)


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_search_pagination(db_session, mock_embedding):
    """검색 페이지네이션 테스트"""
    from app.core.utils.datetime import now_utc
    from app.domains.ai.models import ContentEmbeddingMetadata
    from app.domains.contents.models import Content

    repository = AISearchRepository(db_session)

    # 다수의 콘텐츠 생성 (10개)
    for i in range(10):
        content = Content(
            id=100 + i,
            user_id=1,
            content_type="webpage",
            source_url=f"https://example.com/page{i}",
            title=f"Article {i}",
            summary=f"Content {i}",
            embedding_status="completed",
            created_at=now_utc(),
        )
        db_session.add(content)
        await db_session.flush()

        embedding = ContentEmbeddingMetadata(
            content_id=content.id,
            chunk_index=0,
            chunk_content=f"content {i}",
            embedding_vector=[0.4] * 3072,
            embedding_model="text-embedding-3-large",
            created_at=now_utc(),
        )
        db_session.add(embedding)

    await db_session.commit()

    # 페이지 1 (5개)
    results_page1, total = await repository.vector_search(
        query_embedding=[0.4] * 3072,
        user_id=1,
        filters=None,
        page=1,
        size=5,
        threshold=0.0,
    )

    # 페이지 2 (5개)
    results_page2, _ = await repository.vector_search(
        query_embedding=[0.4] * 3072,
        user_id=1,
        filters=None,
        page=2,
        size=5,
        threshold=0.0,
    )

    # 전체 개수 확인
    assert total >= 10

    # 페이지당 5개씩
    assert len(results_page1) == 5
    assert len(results_page2) == 5

    # 다른 결과여야 함
    ids_page1 = {r["content_id"] for r in results_page1}
    ids_page2 = {r["content_id"] for r in results_page2}
    assert ids_page1.isdisjoint(ids_page2)


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_search_service_integration(db_session, mock_embedding):
    """검색 서비스 통합 테스트"""
    from app.core.utils.datetime import now_utc
    from app.domains.ai.models import ContentEmbeddingMetadata
    from app.domains.contents.models import Content

    service = AISearchService(db_session)

    # 테스트 콘텐츠 생성
    content = Content(
        id=6,
        user_id=1,
        content_type="webpage",
        source_url="https://example.com",
        title="Test Article",
        summary="Test content",
        embedding_status="completed",
        created_at=now_utc(),
    )
    db_session.add(content)
    await db_session.flush()

    embedding = ContentEmbeddingMetadata(
        content_id=content.id,
        chunk_index=0,
        chunk_content="test content",
        embedding_vector=[0.5] * 3072,
        embedding_model="text-embedding-3-large",
        created_at=now_utc(),
    )
    db_session.add(embedding)
    await db_session.commit()

    # 하이브리드 검색
    results, total = await service.search(
        query="test",
        user_id=1,
        mode="hybrid",
        filters=None,
        page=1,
        size=20,
        threshold=0.0,
        include_chunks=False,
    )

    # 결과 검증
    assert total >= 1
    assert len(results) >= 1
    assert results[0]["content_id"] == content.id
