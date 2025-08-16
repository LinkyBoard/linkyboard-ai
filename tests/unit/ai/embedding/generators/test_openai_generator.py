
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.ai.embedding.generators.openai_generator import OpenAIEmbeddingGenerator


@pytest.fixture
def openai_generator():
    with patch('openai.AsyncOpenAI') as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.embeddings.create = AsyncMock()
        generator = OpenAIEmbeddingGenerator()
        generator.client = mock_client
        yield generator


@pytest.mark.asyncio
async def test_generate_embedding_success(openai_generator):
    # Given
    text = "This is a test text."
    mock_embedding = [0.1, 0.2, 0.3]
    mock_embedding_obj = MagicMock()
    mock_embedding_obj.embedding = mock_embedding
    mock_response = MagicMock()
    mock_response.data = [mock_embedding_obj]
    openai_generator.client.embeddings.create.return_value = mock_response

    # When
    embedding = await openai_generator.generate(text)

    # Then
    assert embedding == mock_embedding
    openai_generator.client.embeddings.create.assert_called_once_with(model=openai_generator.model_name, input=text)


@pytest.mark.asyncio
async def test_generate_embedding_empty_text(openai_generator):
    # Given
    text = "   "

    # When / Then
    with pytest.raises(Exception, match="OpenAI 임베딩 생성 실패: Empty text provided for embedding"):
        await openai_generator.generate(text)


def test_get_embedding_dimension():
    # Given
    generator = OpenAIEmbeddingGenerator()
    
    # When / Then
    generator.model_name = "text-embedding-ada-002"
    assert generator.get_embedding_dimension() == 1536

    generator.model_name = "text-embedding-3-small"
    assert generator.get_embedding_dimension() == 1536

    generator.model_name = "text-embedding-3-large"
    assert generator.get_embedding_dimension() == 3072

    generator.model_name = "unknown-model"
    assert generator.get_embedding_dimension() == 1536
