
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.ai.embedding.service import EmbeddingService
from app.ai.embedding.interfaces import EmbeddingResult, ChunkData
from app.core.models import Item
from datetime import datetime


@pytest.fixture
def embedding_service():
    with patch('app.ai.embedding.service.HTMLProcessor') as MockHTMLProcessor, \
         patch('app.ai.embedding.service.TextProcessor') as MockTextProcessor, \
         patch('app.ai.embedding.service.TokenBasedChunking') as MockTokenChunking, \
         patch('app.ai.embedding.service.SentenceBasedChunking') as MockSentenceChunking, \
         patch('app.ai.embedding.service.OpenAIEmbeddingGenerator') as MockOpenAIGenerator, \
         patch('app.ai.embedding.service.EmbeddingRepository') as MockEmbeddingRepository, \
         patch('app.ai.embedding.service.ItemRepository') as MockItemRepository:

        service = EmbeddingService()
        
        # Mock processors
        service.processors['html'] = MockHTMLProcessor.return_value
        service.processors['text'] = MockTextProcessor.return_value

        # Mock chunking strategies
        service.chunking_strategies['token_based'] = MockTokenChunking.return_value
        service.chunking_strategies['sentence_based'] = MockSentenceChunking.return_value

        # Mock embedding generators
        service.embedding_generators['openai'] = MockOpenAIGenerator.return_value

        # Mock repositories
        service.embedding_repository = MockEmbeddingRepository.return_value
        service.item_repository = MockItemRepository.return_value
        
        yield service


@pytest.mark.asyncio
async def test_create_embeddings_success(embedding_service):
    # Given
    session = AsyncMock()
    item_id = 1
    content = "<html><p>Test content</p></html>"

    # Mock dependencies
    embedding_service.item_repository.update_processing_status = AsyncMock()
    embedding_service.processors['html'].process = AsyncMock(return_value="Test content")
    
    mock_chunk = ChunkData(content="Test content", chunk_number=1, start_position=0, end_position=12, chunk_size=12)
    embedding_service.chunking_strategies['token_based'].chunk = AsyncMock(return_value=[mock_chunk])
    
    embedding_service.embedding_generators['openai'].generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
    embedding_service.embedding_generators['openai'].get_model_name.return_value = "test_model"
    embedding_service.embedding_generators['openai'].get_model_version.return_value = "v1"

    mock_embedding_result = EmbeddingResult(chunk_data=mock_chunk, embedding_vector=[0.1, 0.2, 0.3], model_name="test_model", model_version="v1")
    embedding_service.embedding_repository.save_embeddings = AsyncMock(return_value=[mock_embedding_result])

    # When
    results = await embedding_service.create_embeddings(session, item_id, content)

    # Then
    assert len(results) == 1
    assert results[0].embedding_vector == [0.1, 0.2, 0.3]
    embedding_service.item_repository.update_processing_status.assert_any_call(session, item_id, "processing")
    embedding_service.item_repository.update_processing_status.assert_any_call(session, item_id, "completed")
    embedding_service.embedding_repository.save_embeddings.assert_called_once()

@pytest.mark.asyncio
async def test_create_embeddings_failure(embedding_service):
    # Given
    session = AsyncMock()
    item_id = 1
    content = "Test content"

    embedding_service.processors['html'].process = AsyncMock(return_value="Test content")
    embedding_service.chunking_strategies['token_based'].chunk = AsyncMock(return_value=[ChunkData(content="Test content", chunk_number=1, start_position=0, end_position=12, chunk_size=12)])
    embedding_service.embedding_generators['openai'].generate = AsyncMock(side_effect=Exception("Embedding failed"))
    embedding_service.item_repository.update_processing_status = AsyncMock()

    # When / Then
    with pytest.raises(Exception, match="No embeddings were generated successfully"):
        await embedding_service.create_embeddings(session, item_id, content)
    
    embedding_service.item_repository.update_processing_status.assert_any_call(session, item_id, "processing")
    embedding_service.item_repository.update_processing_status.assert_any_call(session, item_id, "failed")

@pytest.mark.asyncio
async def test_get_embedding_status(embedding_service):
    # Given
    session = AsyncMock()
    item_id = 1
    mock_item = Item(id=item_id, processing_status="completed", updated_at=datetime.now())
    embedding_service.item_repository.get_by_id = AsyncMock(return_value=mock_item)
    embedding_service.embedding_repository.get_embedding_stats = AsyncMock(return_value={"count": 1, "avg_dimension": 1536})

    # When
    status = await embedding_service.get_embedding_status(session, item_id)

    # Then
    assert status['item_id'] == item_id
    assert status['processing_status'] == "completed"
    assert status['has_embeddings'] is True
    assert status['count'] == 1

@pytest.mark.asyncio
async def test_delete_embeddings(embedding_service):
    # Given
    session = AsyncMock()
    item_id = 1
    embedding_service.embedding_repository.delete_embeddings_by_item_id = AsyncMock(return_value=1)
    embedding_service.item_repository.update_processing_status = AsyncMock()

    # When
    result = await embedding_service.delete_embeddings(session, item_id)

    # Then
    assert result is True
    embedding_service.embedding_repository.delete_embeddings_by_item_id.assert_called_once_with(session, item_id)
    embedding_service.item_repository.update_processing_status.assert_called_once_with(session, item_id, "raw")

@pytest.mark.asyncio
async def test_test_chunking(embedding_service):
    # Given
    content = "<html><p>Test content</p></html>"
    embedding_service.processors['html'].process = AsyncMock(return_value="Test content")
    embedding_service.chunking_strategies['token_based'].chunk = AsyncMock(return_value=[ChunkData(content="Test content", chunk_number=1, start_position=0, end_position=12, chunk_size=12)])

    # When
    chunks = await embedding_service.test_chunking(content)

    # Then
    assert len(chunks) == 1
    assert chunks[0].content == "Test content"

