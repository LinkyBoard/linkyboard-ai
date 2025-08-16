
import pytest
from unittest.mock import AsyncMock, patch
from app.ai.embedding.generators.keyword_generator import _preprocess_keyword, KeywordEmbeddingGenerator


@pytest.mark.parametrize(
    "input_keyword, expected_keyword",
    [
        ("  테스트 키워드  ", "테스트-키워드"),
        ("  (Test)  Keyword!@#", "test-keyword"),
        ("---multiple---hyphens---", "multiple-hyphens"),
        ("__multiple__underscores__", "multiple-underscores"),
        ("   leading and trailing spaces  ", "leading-and-trailing-spaces"),
        ("한글과 English", "한글과-english"),
        ("  ", ""),
    ],
)
def test_preprocess_keyword(input_keyword, expected_keyword):
    assert _preprocess_keyword(input_keyword) == expected_keyword


@pytest.fixture
def keyword_generator():
    with patch('app.ai.embedding.generators.keyword_generator.OpenAIEmbeddingGenerator.generate', new_callable=AsyncMock) as mock_generate:
        generator = KeywordEmbeddingGenerator()
        generator.generate = mock_generate
        yield generator


@pytest.mark.asyncio
async def test_generate_keyword_embedding(keyword_generator):
    # Given
    keyword = "  Test Keyword!  "
    expected_embedding = [0.1, 0.2, 0.3]
    keyword_generator.generate.return_value = expected_embedding

    # When
    embedding = await keyword_generator.generate_keyword_embedding(keyword)

    # Then
    assert embedding == expected_embedding
    keyword_generator.generate.assert_called_once_with("주제: test-keyword")


@pytest.mark.asyncio
async def test_generate_batch_keyword_embeddings(keyword_generator):
    # Given
    keywords = ["Keyword 1", "Keyword 2", "  "]
    expected_embeddings = [[0.1], [0.2], None]
    keyword_generator.generate.side_effect = [[0.1], [0.2], ValueError("Invalid keyword")]

    # When
    embeddings = await keyword_generator.generate_batch_keyword_embeddings(keywords)

    # Then
    assert embeddings == expected_embeddings
    assert keyword_generator.generate.call_count == 2
