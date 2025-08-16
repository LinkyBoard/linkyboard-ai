
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.openai_service import OpenAIService

@pytest.fixture
def openai_service():
    with patch('openai.AsyncOpenAI') as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create = AsyncMock()
        mock_client.embeddings.create = AsyncMock()
        service = OpenAIService(api_key="test_key")
        service.client = mock_client
        yield service


@pytest.mark.asyncio
async def test_generate_webpage_tags(openai_service):
    # Given
    summary = "This is a test summary."
    mock_choice = MagicMock()
    mock_choice.message.content = "tag1, tag2, tag3"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    openai_service.client.chat.completions.create.return_value = mock_response

    # When
    tags = await openai_service.generate_webpage_tags(summary)

    # Then
    assert tags == ["tag1", "tag2", "tag3"]
    openai_service.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_recommend_webpage_category(openai_service):
    # Given
    summary = "This is a test summary."
    mock_choice = MagicMock()
    mock_choice.message.content = "Technology"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    openai_service.client.chat.completions.create.return_value = mock_response

    # When
    category = await openai_service.recommend_webpage_category(summary)

    # Then
    assert category == "Technology"
    openai_service.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_webpage_summary(openai_service):
    # Given
    url = "http://example.com"
    html_content = "<html><body><p>This is a test.</p></body></html>"
    mock_choice = MagicMock()
    mock_choice.message.content = "This is a test summary."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    openai_service.client.chat.completions.create.return_value = mock_response

    # When
    summary = await openai_service.generate_webpage_summary(url, html_content)

    # Then
    assert summary == "This is a test summary."
    openai_service.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_webpage_embedding(openai_service):
    # Given
    html_content = "<html><body><p>This is a test.</p></body></html>"
    mock_embedding = [0.1, 0.2, 0.3]
    mock_embedding_obj = MagicMock()
    mock_embedding_obj.embedding = mock_embedding
    mock_response = MagicMock()
    mock_response.data = [mock_embedding_obj]
    openai_service.client.embeddings.create.return_value = mock_response

    # When
    embedding = await openai_service.generate_webpage_embedding(html_content)

    # Then
    assert embedding == mock_embedding
    openai_service.client.embeddings.create.assert_called_once()
