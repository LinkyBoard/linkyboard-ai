from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.ai.embedding.interfaces import (
    ContentProcessor, 
    ChunkingStrategy, 
    EmbeddingGenerator,
    EmbeddingResult,
    ChunkData
)
from app.ai.embedding.processors.content_processors import HTMLProcessor, TextProcessor
from app.ai.embedding.chunking.strategies import TokenBasedChunking, SentenceBasedChunking
from app.ai.embedding.generators.openai_generator import OpenAIEmbeddingGenerator
from app.ai.embedding.repository import EmbeddingRepository
from app.core.repository import ItemRepository
from app.core.logging import get_logger
from app.core.utils.observability import trace_embedding_generation, record_ai_tokens

logger = get_logger(__name__)


class EmbeddingService:
    """임베딩 서비스 - 임베딩 생성의 전체 프로세스 관리"""
    
    def __init__(self):
        # 컴포넌트 초기화
        self.processors: Dict[str, ContentProcessor] = {
            "html": HTMLProcessor(),
            "text": TextProcessor(),
        }
        
        self.chunking_strategies: Dict[str, ChunkingStrategy] = {
            "token_based": TokenBasedChunking(),
            "sentence_based": SentenceBasedChunking(),
        }
        
        self.embedding_generators: Dict[str, EmbeddingGenerator] = {
            "openai": OpenAIEmbeddingGenerator(),
        }
        
        self.embedding_repository = EmbeddingRepository()
        self.item_repository = ItemRepository()
        
        logger.info("Embedding service initialized with all components")
    
    async def create_embeddings(
        self,
        session: AsyncSession,
        item_id: int,
        content: str,
        content_type: str = "html",
        chunking_strategy: str = "token_based",
        embedding_generator: str = "openai",
        max_chunk_size: int = 8000,
        user_id: int = None  # WTU 계측을 위한 사용자 ID
    ) -> List[EmbeddingResult]:
        """
        전체 임베딩 생성 프로세스 실행 (관측성 포함)
        """
        async with trace_embedding_generation(
            item_id=item_id,
            content_length=len(content),
            content_type=content_type,
            chunking_strategy=chunking_strategy,
            embedding_generator=embedding_generator,
            user_id=user_id or "unknown"
        ) as span:
            start_time = datetime.now()
            logger.bind(
                task_type="embedding",
                item_id=item_id,
                content_type=content_type,
                chunking_strategy=chunking_strategy,
                embedding_generator=embedding_generator
            ).info(f"Starting embedding creation for item {item_id}")
            
            try:
                # 1. 상태 업데이트 - 처리 시작
                await self.item_repository.update_processing_status(
                    session, item_id, "processing"
                )
                
                # 2. 콘텐츠 전처리
                processor = self._get_processor(content_type)
                processed_content = await processor.process(content)
                
                logger.info(f"Content processed: {len(content)} -> {len(processed_content)} chars")
                logger.info(f"Max chunk size: {max_chunk_size}")
                span.set_attribute("embedding.processed_content_length", len(processed_content))
                
                # 콘텐츠가 너무 짧은 경우 확인
                if len(processed_content) <= max_chunk_size:
                    logger.info(f"Content length ({len(processed_content)}) is within single chunk size ({max_chunk_size})")
                else:
                    logger.info(f"Content will be chunked: {len(processed_content)} chars > {max_chunk_size} max_chunk_size")
                
                # 3. 청킹
                chunker = self._get_chunking_strategy(chunking_strategy)
                chunks = await chunker.chunk(processed_content, max_chunk_size)
                
                logger.info(f"Content chunked into {len(chunks)} pieces")
                span.set_attribute("embedding.chunk_count", len(chunks))
                
                # 각 청크 크기 로깅
                for i, chunk in enumerate(chunks):
                    logger.info(f"Chunk {i}: {len(chunk.content)} chars, start: {chunk.start_position}, end: {chunk.end_position}")
                
                # 4. 임베딩 생성
                generator = self._get_embedding_generator(embedding_generator)
                embedding_results = []
                total_embed_tokens = 0
                
                for chunk in chunks:
                    try:
                        # user_id를 generator에 전달하여 WTU 계측 가능하게 함
                        embedding_vector = await generator.generate(chunk.content, user_id=user_id)
                        
                        result = EmbeddingResult(
                            chunk_data=chunk,
                            embedding_vector=embedding_vector,
                            model_name=generator.get_model_name(),
                            model_version=generator.get_model_version()
                        )
                        embedding_results.append(result)
                        
                        # 토큰 수 추정 (관측성 메트릭용)
                        from app.metrics import count_tokens
                        chunk_tokens = count_tokens(chunk.content, generator.get_model_name())
                        total_embed_tokens += chunk_tokens
                        
                        logger.debug(f"Generated embedding for chunk {chunk.chunk_number}")
                        
                    except Exception as e:
                        logger.error(f"Failed to generate embedding for chunk {chunk.chunk_number}: {str(e)}")
                        # 개별 청크 실패 시 전체를 실패시키지 않고 계속 진행
                        continue
                
                if not embedding_results:
                    raise Exception("No embeddings were generated successfully")
                
                # 관측성 메트릭 기록
                record_ai_tokens(generator.get_model_name(), embed_tokens=total_embed_tokens)
                span.set_attribute("embedding.total_tokens", total_embed_tokens)
                
                # 5. 데이터베이스 저장
                saved_embeddings = await self.embedding_repository.save_embeddings(
                    session, item_id, embedding_results
                )
                
                # 6. 상태 업데이트 - 완료
                await self.item_repository.update_processing_status(
                    session, item_id, "completed"
                )
                
                # 성공 로깅
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                span.set_attribute("embedding.embeddings_saved", len(saved_embeddings))
                span.set_attribute("embedding.success", True)
                
                logger.bind(
                    task_type="embedding",
                    item_id=item_id,
                    status="completed",
                    duration_seconds=duration,
                    chunks_created=len(embedding_results),
                    total_embeddings=len(saved_embeddings)
                ).info(f"Embedding creation completed for item {item_id} in {duration:.2f}s")
                
                return embedding_results
                
            except Exception as e:
                # 실패 처리
                span.set_attribute("embedding.success", False)
                span.set_attribute("embedding.error", str(e))
                
                try:
                    await self.item_repository.update_processing_status(
                        session, item_id, "failed"
                    )
                except Exception as db_error:
                    logger.error(f"Failed to update error status: {str(db_error)}")
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.bind(
                    task_type="embedding",
                    item_id=item_id,
                    status="failed",
                    error=str(e),
                    duration_seconds=duration
                ).error(f"Embedding creation failed for item {item_id}: {str(e)}")
                
                raise
    
    async def get_embedding_status(
        self, 
        session: AsyncSession, 
        item_id: int
    ) -> Dict[str, Any]:
        """임베딩 처리 상태 조회"""
        try:
            # 아이템 정보 조회
            item = await self.item_repository.get_by_id(session, item_id)
            if not item:
                raise Exception("Item not found")
            
            # 임베딩 통계 조회
            embedding_stats = await self.embedding_repository.get_embedding_stats(
                session, item_id
            )
            
            status = {
                "item_id": item_id,
                "processing_status": item.processing_status,
                "has_embeddings": embedding_stats is not None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None
            }
            
            if embedding_stats:
                status.update(embedding_stats)
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get embedding status for item {item_id}: {str(e)}")
            raise
    
    def _get_processor(self, content_type: str) -> ContentProcessor:
        """콘텐츠 타입에 맞는 프로세서 반환"""
        processor = self.processors.get(content_type)
        if not processor:
            logger.warning(f"Unknown content type: {content_type}, using text processor")
            processor = self.processors["text"]
        return processor
    
    def _get_chunking_strategy(self, strategy_name: str) -> ChunkingStrategy:
        """청킹 전략 반환"""
        strategy = self.chunking_strategies.get(strategy_name)
        if not strategy:
            logger.warning(f"Unknown chunking strategy: {strategy_name}, using token_based")
            strategy = self.chunking_strategies["token_based"]
        return strategy
    
    def _get_embedding_generator(self, generator_name: str) -> EmbeddingGenerator:
        """임베딩 생성기 반환"""
        generator = self.embedding_generators.get(generator_name)
        if not generator:
            logger.warning(f"Unknown embedding generator: {generator_name}, using openai")
            generator = self.embedding_generators["openai"]
        return generator
    
    async def delete_embeddings(self, session: AsyncSession, item_id: int) -> bool:
        """아이템의 모든 임베딩 삭제"""
        try:
            deleted_count = await self.embedding_repository.delete_embeddings_by_item_id(
                session, item_id
            )
            
            # 아이템 상태 업데이트
            await self.item_repository.update_processing_status(
                session, item_id, "raw"
            )
            
            logger.info(f"Deleted {deleted_count} embeddings for item {item_id}")
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete embeddings for item {item_id}: {str(e)}")
            raise

    async def test_chunking(self, content: str, max_chunk_size: int = 8000) -> List[ChunkData]:
        """청킹 테스트용 메서드"""
        try:
            logger.info(f"Testing chunking with content length: {len(content)}, max_chunk_size: {max_chunk_size}")
            
            # HTML 전처리
            processor = self._get_processor("html")
            processed_content = await processor.process(content)
            
            logger.info(f"After processing: {len(processed_content)} chars")
            
            # 청킹
            chunker = self._get_chunking_strategy("token_based")
            chunks = await chunker.chunk(processed_content, max_chunk_size)
            
            logger.info(f"Chunking result: {len(chunks)} chunks")
            
            for i, chunk in enumerate(chunks):
                logger.info(f"  Chunk {i}: {len(chunk.content)} chars")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Test chunking failed: {str(e)}")
            raise


# 서비스 인스턴스 생성
embedding_service = EmbeddingService()
