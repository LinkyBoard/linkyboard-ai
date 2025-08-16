import pytest
import re
from app.ai.embedding.processors.content_processors import HTMLProcessor, TextProcessor


@pytest.fixture
def html_processor():
    return HTMLProcessor()


@pytest.fixture
def text_processor():
    return TextProcessor()


@pytest.mark.asyncio
async def test_html_processor_remove_tags(html_processor):
    # Given
    html = "<html><head><title>Title</title></head><body><p>Hello</p></body></html>"
    expected_text = "Title Hello"

    # When
    text = html_processor._remove_html_tags(html)

    # Then
    assert re.sub(r'\s+', ' ', text).strip() == expected_text.strip()


@pytest.mark.asyncio
async def test_html_processor_remove_script_style(html_processor):
    # Given
    html = "<script>alert('hello')</script><div>Content</div><style>body{color:red}</style>"
    expected_text = "Content"

    # When
    text = html_processor._remove_html_tags(html)

    # Then
    assert text.strip() == expected_text


@pytest.mark.asyncio
async def test_html_processor_decode_entities(html_processor):
    # Given
    html = "&lt;div&gt;Test&amp;More&lt;/div&gt;"
    expected_text = '<div>Test&More</div>'

    # When
    text = html_processor._decode_html_entities(html)

    # Then
    assert text == expected_text


@pytest.mark.asyncio
async def test_html_processor_process(html_processor):
    # Given
    html = "<html><head><script>alert('XSS')</script></head><body><h1>Title</h1><p>Content here.</p></body></html>"
    expected_text = "Title Content here."

    # When
    text = await html_processor.process(html)

    # Then
    assert text == expected_text


@pytest.mark.asyncio
async def test_text_processor_process(text_processor):
    # Given
    text = "  Hello   World  \n\n  Test  "
    expected_text = "Hello World\nTest"

    # When
    processed_text = await text_processor.process(text)

    # Then
    assert processed_text == expected_text
