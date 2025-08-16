
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.classification.category_classifier import CategoryClassificationService


@pytest.fixture
def category_classification_service():
    with patch('openai.AsyncOpenAI') as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create = AsyncMock()
        service = CategoryClassificationService()
        service.client = mock_client
        yield service


@pytest.mark.asyncio
async def test_classify_category_from_summary(category_classification_service):
    # Given
    summary = "This is a test summary."
    mock_choice = MagicMock()
    mock_choice.message.content = "Technology"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    category_classification_service.client.chat.completions.create.return_value = mock_response

    # When
    category = await category_classification_service.classify_category_from_summary(summary)

    # Then
    assert category == "Technology"
    category_classification_service.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_classify_category_from_content(category_classification_service):
    # Given
    content = "This is a long content..." * 100
    mock_choice = MagicMock()
    mock_choice.message.content = "Science"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    category_classification_service.client.chat.completions.create.return_value = mock_response

    # When
    category = await category_classification_service.classify_category_from_content(content)

    # Then
    assert category == "Science"
    category_classification_service.client.chat.completions.create.assert_called_once()
    assert len(category_classification_service.client.chat.completions.create.call_args[1]['messages'][1]['content']) < len(content)
