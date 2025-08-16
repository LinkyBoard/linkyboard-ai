
import pytest
import re
from app.ai.embedding.chunking.strategies import TokenBasedChunking, SentenceBasedChunking


@pytest.fixture
def token_chunker():
    return TokenBasedChunking()


@pytest.fixture
def sentence_chunker():
    return SentenceBasedChunking()


@pytest.mark.asyncio
async def test_token_chunking_single_chunk(token_chunker):
    # Given
    content = "This is a short content."
    max_chunk_size = 100

    # When
    chunks = await token_chunker.chunk(content, max_chunk_size)

    # Then
    assert len(chunks) == 1
    assert chunks[0].content == content


@pytest.mark.asyncio
async def test_token_chunking_multiple_chunks(token_chunker):
    # Given
    content = "This is a long content. " * 10
    max_chunk_size = 50

    # When
    chunks = await token_chunker.chunk(content, max_chunk_size)

    # Then
    assert len(chunks) > 1
    reconstructed_content = "".join(c.content for c in chunks)
    assert re.sub(r'[\s.!?]', '', reconstructed_content) == re.sub(r'[\s.!?]', '', content)


def test_find_best_cut_point(token_chunker):
    # Given
    content = "This is a sentence. This is another one. And a third."
    start = 0
    end = 40

    # When
    cut_point = token_chunker._find_best_cut_point(content, start, end)

    # Then
    assert cut_point == 36 # After "one. "


@pytest.mark.asyncio
async def test_sentence_chunking_split_sentences(sentence_chunker):
    # Given
    content = "This is a sentence. This is another one! And a third?"
    
    # When
    sentences = sentence_chunker._split_sentences(content)
    
    # Then
    assert len(sentences) == 3
    assert sentences[0] == "This is a sentence"


@pytest.mark.asyncio
async def test_sentence_chunking_single_chunk(sentence_chunker):
    # Given
    content = "This is a short content."
    max_chunk_size = 100

    # When
    chunks = await sentence_chunker.chunk(content, max_chunk_size)

    # Then
    assert len(chunks) == 1
    assert chunks[0].content == content


@pytest.mark.asyncio
async def test_sentence_chunking_multiple_chunks(sentence_chunker):
    # Given
    content = "This is a sentence. " * 5
    max_chunk_size = 40

    # When
    chunks = await sentence_chunker.chunk(content, max_chunk_size)

    # Then
    assert len(chunks) > 1
    reconstructed_content = "".join(c.content for c in chunks)
    assert re.sub(r'[\s.!?]', '', reconstructed_content) == re.sub(r'[\s.!?]', '', content)
