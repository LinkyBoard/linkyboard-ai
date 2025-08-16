import pytest
from unittest.mock import AsyncMock, patch
from app.ai.embedding.generators.category_generator import _preprocess_category, CategoryEmbeddingGenerator


@pytest.mark.parametrize(
    "input_category, expected_category",
    [
        ("  테스트 카테고리  ", "테스트 카테고리"),
        ("  Test  Category  ", "Test Category"),
        ("   leading and trailing spaces  ", "leading and trailing spaces"),
        ("  ", ""),
    ],
)
def test_preprocess_category(input_category, expected_category):
    assert _preprocess_category(input_category) == expected_category


@pytest.fixture
def category_generator():
    with patch('app.ai.embedding.generators.category_generator.OpenAIEmbeddingGenerator.generate', new_callable=AsyncMock) as mock_generate:
        generator = CategoryEmbeddingGenerator()
        generator.generate = mock_generate
        yield generator


@pytest.mark.asyncio
async def test_generate_category_embedding(category_generator):
    # Given
    category = "  Test Category  "
    description = "A test description."
    expected_embedding = [0.1, 0.2, 0.3]
    category_generator.generate.return_value = expected_embedding

    # When
    embedding = await category_generator.generate_category_embedding(category, description)

    # Then
    assert embedding == expected_embedding
    category_generator.generate.assert_called_once_with(f"카테고리: Test Category\n설명: {description}")


@pytest.mark.asyncio
async def test_generate_batch_category_embeddings(category_generator):
    # Given
    categories = ["Category 1", "Category 2", "  "]
    descriptions = ["Desc 1", "Desc 2", ""]
    expected_embeddings = [[0.1], [0.2], None]
    category_generator.generate.side_effect = [[0.1], [0.2], ValueError("Invalid category")]

    # When
    embeddings = await category_generator.generate_batch_category_embeddings(categories, descriptions)

    # Then
    assert embeddings == expected_embeddings
    assert category_generator.generate.call_count == 2
