"""임베딩 서비스

콘텐츠를 청크로 분할하고 각 청크의 임베딩을 생성하여 저장합니다.
"""

from typing import Optional, cast

import tiktoken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_embedding
from app.core.logging import get_logger
from app.domains.ai.exceptions import EmbeddingFailedException
from app.domains.ai.models import ChunkStrategy, ContentEmbeddingMetadata

logger = get_logger(__name__)


class EmbeddingService:
    """임베딩 생성 및 관리 서비스"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.default_encoding = tiktoken.get_encoding("cl100k_base")

    def chunk_text(
        self, text: str, strategy: ChunkStrategy
    ) -> list[tuple[str, int, int]]:
        """텍스트를 청크로 분할

        Args:
            text: 분할할 텍스트
            strategy: 청크 분할 전략

        Returns:
            list[tuple[str, int, int]]: (청크 텍스트, 시작 위치, 종료 위치) 리스트

        Note:
            현재는 token 기반 분할만 지원합니다.
            나중에 sentence, paragraph 기반 분할을 추가할 수 있습니다.

        TODO : 전략에 따른 분할 적용
        """
        if strategy.split_method != "token":
            logger.warning(
                f"Unsupported split method: {strategy.split_method}. "
                "Falling back to token-based splitting."
            )

        # 텍스트를 토큰으로 변환
        tokens = self.default_encoding.encode(text)
        chunks: list[tuple[str, int, int]] = []

        chunk_size = strategy.chunk_size
        chunk_overlap = strategy.chunk_overlap

        start_idx = 0

        while start_idx < len(tokens):
            # 청크의 끝 인덱스 계산
            end_idx = min(start_idx + chunk_size, len(tokens))

            # 토큰을 텍스트로 디코딩
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self.default_encoding.decode(chunk_tokens)

            # 원본 텍스트에서의 대략적인 위치 (바이트 기준)
            # 정확한 위치는 나중에 필요하면 개선
            start_pos = start_idx
            end_pos = end_idx

            chunks.append((chunk_text, start_pos, end_pos))

            # 다음 청크로 이동 (오버랩 고려)
            start_idx += chunk_size - chunk_overlap

            # 마지막 청크에 도달했으면 종료
            if end_idx >= len(tokens):
                break

        logger.info(
            f"Text chunked into {len(chunks)} chunks "
            f"(strategy={strategy.name}, size={chunk_size}, "
            f"overlap={chunk_overlap})"
        )

        return chunks

    async def create_embedding_vector(self, text: str) -> list[float]:
        """텍스트의 임베딩 벡터 생성

        Args:
            text: 임베딩할 텍스트

        Returns:
            list[float]: 임베딩 벡터 (3072 차원)

        Raises:
            EmbeddingFailedException: 임베딩 생성 실패 시
        """
        try:
            vector = await create_embedding(text)
            return vector
        except Exception as e:
            logger.error(f"Embedding creation failed: {e}")
            raise EmbeddingFailedException(detail_msg=f"임베딩 생성 실패: {str(e)}")

    async def create_embeddings_for_content(
        self,
        content_id: int,
        text: str,
        strategy_id: Optional[int] = None,
    ) -> list[ContentEmbeddingMetadata]:
        """콘텐츠의 임베딩 생성 및 저장

        콘텐츠를 청크로 분할하고 각 청크의 임베딩을 생성하여 DB에 저장합니다.
        기존 임베딩이 있으면 삭제 후 재생성합니다.

        Args:
            content_id: 콘텐츠 ID
            text: 임베딩할 텍스트
            strategy_id: 청크 분할 전략 ID (None이면 기본 전략 사용)

        Returns:
            list[ContentEmbeddingMetadata]: 생성된 임베딩 메타데이터 리스트

        Raises:
            EmbeddingFailedException: 임베딩 생성 실패 시
        """
        logger.info(
            f"Creating embeddings for content_id={content_id}, "
            f"text_length={len(text)}, strategy_id={strategy_id}"
        )

        # 청크 전략 가져오기
        if strategy_id is not None:
            result = await self.session.execute(
                select(ChunkStrategy).where(ChunkStrategy.id == strategy_id)
            )
            strategy = result.scalar_one_or_none()
            if not strategy:
                logger.warning(
                    f"Strategy {strategy_id} not found. Using default."
                )
                strategy = await self._get_default_strategy()
        else:
            strategy = await self._get_default_strategy()

        # 기존 임베딩 삭제 (중복 방지)
        await self.session.execute(
            delete(ContentEmbeddingMetadata).where(
                ContentEmbeddingMetadata.content_id == content_id
            )
        )
        await self.session.flush()
        logger.info(f"Deleted existing embeddings for content_id={content_id}")

        # 텍스트를 청크로 분할
        chunks = self.chunk_text(text, strategy)

        # 각 청크의 임베딩 생성 및 저장
        embeddings: list[ContentEmbeddingMetadata] = []

        for idx, (chunk_text, start_pos, end_pos) in enumerate(chunks):
            # 임베딩 벡터 생성
            embedding_vector = await self.create_embedding_vector(chunk_text)

            # DB 객체 생성
            embedding_metadata = ContentEmbeddingMetadata(
                content_id=content_id,
                strategy_id=strategy.id,
                chunk_index=idx,
                chunk_content=chunk_text,
                start_position=start_pos,
                end_position=end_pos,
                embedding_vector=embedding_vector,
                embedding_model="text-embedding-3-large",
            )

            self.session.add(embedding_metadata)
            embeddings.append(embedding_metadata)

        # DB에 저장
        await self.session.flush()
        logger.info(
            f"Created {len(embeddings)} embeddings for content_id={content_id}"
        )

        return embeddings

    async def get_chunk_strategy(
        self,
        content_type: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Optional[ChunkStrategy]:
        """청크 분할 전략 조회

        우선순위:
        1) content_type + domain
        2) content_type + domain IS NULL (타입 기본값)
        3) content_type IS NULL + domain IS NULL (글로벌 기본값)
        """

        base_query = select(ChunkStrategy).where(
            ChunkStrategy.is_active.is_(True)
        )

        # 1. content_type가 있는 경우
        if content_type is not None:
            base_query = base_query.where(
                ChunkStrategy.content_type == content_type
            )

            # 1-1. domain까지 있는 경우: 정확히 일치하는 전략 우선
            if domain:
                q_exact = base_query.where(ChunkStrategy.domain == domain)
                result = await self.session.execute(q_exact)
                strategy_exact: Optional[
                    ChunkStrategy
                ] = result.scalars().first()
                if strategy_exact:
                    return strategy_exact

            # 1-2. 타입 기본값 (domain IS NULL) fallback
            q_type_default = base_query.where(ChunkStrategy.domain.is_(None))
            result = await self.session.execute(q_type_default)
            strategy_default: Optional[
                ChunkStrategy
            ] = result.scalars().first()
            if strategy_default:
                return strategy_default

            # 2. content_type이 없거나, 타입별 전략이 하나도 없으면
            #    글로벌 기본 전략으로 fallback
            return await self._get_default_strategy()
        return await self._get_default_strategy()

    async def _get_default_strategy(self) -> ChunkStrategy:
        """기본 청크 전략 가져오기

        DB에 'default' 전략이 없으면 생성합니다.

        Returns:
            ChunkStrategy: 기본 청크 전략
        """
        result = await self.session.execute(
            select(ChunkStrategy).where(ChunkStrategy.name == "default")
        )
        strategy = cast(Optional[ChunkStrategy], result.scalar_one_or_none())

        if strategy is None:
            logger.info("Creating default chunk strategy")
            strategy = ChunkStrategy(
                name="default",
                content_type=None,
                domain=None,
                chunk_size=500,
                chunk_overlap=50,
                split_method="token",
                is_active=True,
            )
            self.session.add(strategy)
            await self.session.flush()

        return strategy
