
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.classification.tag_extractor import TagExtractionService


@pytest.fixture
def tag_extraction_service():
    with patch('openai.AsyncOpenAI') as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create = AsyncMock()
        service = TagExtractionService()
        service.client = mock_client
        yield service


@pytest.mark.asyncio
async def test_extract_tags_from_summary(tag_extraction_service):
    # Given
    summary = "This is a test summary."
    mock_choice = MagicMock()
    mock_choice.message.content = "tag1, tag2, tag3"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    tag_extraction_service.client.chat.completions.create.return_value = mock_response

    # When
    tags = await tag_extraction_service.extract_tags_from_summary(summary)

    # Then
    assert tags == ["tag1", "tag2", "tag3"]
    tag_extraction_service.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_extract_tags_from_content(tag_extraction_service):
    # Given
    content = "This is a long content..." * 100
    mock_choice = MagicMock()
    mock_choice.message.content = "tagA, tagB"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    tag_extraction_service.client.chat.completions.create.return_value = mock_response

    # When
    tags = await tag_extraction_service.extract_tags_from_content(content)

    # Then
    assert tags == ["tagA", "tagB"]
    tag_extraction_service.client.chat.completions.create.assert_called_once()
    # Check if content was truncated
    assert len(tag_extraction_service.client.chat.completions.create.call_args[1]['messages'][1]['content']) < len(content)
