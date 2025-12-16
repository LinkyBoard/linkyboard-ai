"""임베딩 서비스 단위 테스트"""

import pytest

from app.domains.ai.embedding.service import EmbeddingService
from app.domains.ai.models import ChunkStrategy, ContentEmbeddingMetadata


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_chunk_text_basic(db_session):
    """기본 텍스트 청크 분할 테스트"""
    service = EmbeddingService(db_session)

    # 청크 전략 생성
    strategy = ChunkStrategy(
        id=1,
        name="test_strategy",
        content_type="webpage",
        chunk_size=50,
        chunk_overlap=10,
        split_method="token",
        is_active=True,
    )

    # 짧은 텍스트
    text = "This is a short text for testing."
    chunks = service.chunk_text(text, strategy)

    # 짧은 텍스트는 1개 청크
    assert len(chunks) == 1
    # chunk_text는 (text, start_pos, end_pos) 튜플 반환
    assert chunks[0][0] == text
    assert isinstance(chunks[0][1], int)
    assert isinstance(chunks[0][2], int)


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_chunk_text_with_overlap(db_session):
    """청크 오버랩 테스트"""
    service = EmbeddingService(db_session)

    # 긴 텍스트 생성 (토큰 기준 100개 이상)
    long_text = " ".join([f"word{i}" for i in range(100)])

    strategy = ChunkStrategy(
        id=1,
        name="test_strategy",
        content_type="webpage",
        chunk_size=50,
        chunk_overlap=10,
        split_method="token",
        is_active=True,
    )

    chunks = service.chunk_text(long_text, strategy)

    # 여러 청크로 분할되어야 함
    assert len(chunks) > 1

    # 각 청크가 비어있지 않아야 함
    for chunk in chunks:
        assert len(chunk) > 0


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_create_embedding_with_mock(db_session):
    """임베딩 생성 테스트 (Mock)"""
    from unittest.mock import AsyncMock, patch

    service = EmbeddingService(db_session)

    text = "Test text for embedding"

    # 임베딩 서비스 내부에서 사용하는 함수를 Mock
    with patch(
        "app.domains.ai.embedding.service.create_embedding",
        new_callable=AsyncMock,
    ) as mock_embed:
        mock_embed.return_value = [0.1] * 3072

        embedding = await service.create_embedding_vector(text)

        # Mock은 3072 차원 벡터 반환
        assert len(embedding) == 3072
        assert all(isinstance(v, float) for v in embedding)

        # Mock 호출 확인
        mock_embed.assert_called_once_with(text)


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_create_embeddings_for_content(db_session):
    """콘텐츠 임베딩 생성 테스트 (Mock)"""
    from unittest.mock import AsyncMock, patch

    from app.core.utils.datetime import now_utc
    from app.domains.contents.models import Content

    service = EmbeddingService(db_session)

    # 테스트 콘텐츠 생성
    content = Content(
        id=1,
        user_id=1,
        content_type="webpage",
        source_url="https://example.com",
        title="Test Content",
        summary="Test Summary",
        created_at=now_utc(),
    )
    db_session.add(content)
    await db_session.flush()

    # 청크 전략 생성
    strategy = ChunkStrategy(
        id=1,
        name="test_strategy",
        content_type="webpage",
        chunk_size=100,
        chunk_overlap=20,
        split_method="token",
        is_active=True,
    )
    db_session.add(strategy)
    await db_session.flush()

    # 임베딩 Mock
    with patch(
        "app.domains.ai.embedding.service.create_embedding",
        new_callable=AsyncMock,
    ) as mock_embed:
        mock_embed.return_value = [0.1] * 3072

        # 임베딩 생성
        text = "Short test text for embedding generation."
        embeddings = await service.create_embeddings_for_content(
            content_id=content.id,
            text=text,
            strategy_id=strategy.id,
        )

        # 짧은 텍스트는 1개 청크
        assert len(embeddings) == 1
        assert embeddings[0].content_id == content.id
        assert embeddings[0].strategy_id == strategy.id
        assert embeddings[0].chunk_index == 0
        assert len(embeddings[0].embedding_vector) == 3072


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_create_embeddings_removes_existing(db_session):
    """기존 임베딩 삭제 후 새로 생성 테스트"""
    from unittest.mock import AsyncMock, patch

    from sqlalchemy import select

    from app.core.utils.datetime import now_utc
    from app.domains.contents.models import Content

    service = EmbeddingService(db_session)

    # 테스트 콘텐츠 생성
    content = Content(
        id=2,
        user_id=1,
        content_type="webpage",
        source_url="https://example.com",
        title="Test Content",
        summary="Test Summary",
        created_at=now_utc(),
    )
    db_session.add(content)
    await db_session.flush()

    # 기존 임베딩 생성
    existing_embedding = ContentEmbeddingMetadata(
        content_id=content.id,
        chunk_index=0,
        chunk_content="Old chunk",
        embedding_vector=[0.5] * 3072,
        embedding_model="text-embedding-3-large",
        created_at=now_utc(),
    )
    db_session.add(existing_embedding)
    await db_session.flush()

    # 임베딩 Mock
    with patch(
        "app.domains.ai.embedding.service.create_embedding",
        new_callable=AsyncMock,
    ) as mock_embed:
        mock_embed.return_value = [0.1] * 3072

        # 새 임베딩 생성
        new_embeddings = await service.create_embeddings_for_content(
            content_id=content.id,
            text="New test text",
            strategy_id=None,
        )

        # 기존 임베딩이 삭제되고 새로 생성되어야 함
        query = select(ContentEmbeddingMetadata).where(
            ContentEmbeddingMetadata.content_id == content.id
        )
        result = await db_session.execute(query)
        all_embeddings = result.scalars().all()

        # 새 임베딩만 존재
        assert len(all_embeddings) == len(new_embeddings)
        assert all_embeddings[0].chunk_content != "Old chunk"
