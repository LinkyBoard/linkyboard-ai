# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# # """AI 도메인 API 통합 테스트 (Mock AI)"""
#
# # import pytest
#
#
# # @pytest.mark.asyncio
# # @pytest.mark.mock_ai
# # async def test_summarize_webpage_api(
# #     client, api_key_header, mock_llm_completion, mock_embedding
# # ):
# #     """웹페이지 요약 API 테스트 (Mock)"""
# #     from io import BytesIO
#
# #     # Mock LLM 응답 설정
# #     def mock_side_effect(*args, **kwargs):
# #         from app.core.llm.types import LLMResult
#
# #         prompt = (
# #             kwargs.get("messages", [])[0].content
# #             if kwargs.get("messages")
# #             else ""
# #         )
#
# #         if "태그" in prompt or "키워드" in prompt:
# #             return LLMResult(
# #                 content='["AI", "기술", "트렌드", "혁신"]',
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
# #         elif "카테고리" in prompt:
# #             return LLMResult(
# #                 content='["기술"]',
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
# #         else:
# #             return LLMResult(
# #                 content="이것은 테스트 요약입니다.",
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
#
# #     mock_llm_completion.side_effect = mock_side_effect
#
# #     # HTML 파일 준비
# #     html_content = """
# #     <html>
# #         <head><title>Test Article</title></head>
# #         <body>
# #             <h1>AI Technology Trends</h1>
# #             <p>Artificial intelligence is rapidly evolving...</p>
# #         </body>
# #     </html>
# #     """
# #     html_file = BytesIO(html_content.encode("utf-8"))
#
# #     # API 호출
# #     response = await client.post(
# #         "/api/v1/ai/summarize/webpage",
# #         data={
# #             "url": "https://example.com/ai-trends",
# #             "user_id": 1,
# #             "tag_count": 5,
# #         },
# #         files={"html_file": ("test.html", html_file, "text/html")},
# #         headers=api_key_header,
# #     )
#
# #     # 응답 검증
# #     assert response.status_code == 200
# #     data = response.json()
#
# #     assert data["success"] is True
# #     assert "summary" in data["data"]
# #     assert "tags" in data["data"]
# #     assert "category" in data["data"]
# #     assert "cached" in data["data"]
# #     assert isinstance(data["data"]["tags"], list)
#
#
# # @pytest.mark.asyncio
# # @pytest.mark.mock_ai
# # async def test_summarize_youtube_api(
# #     client,
# #     api_key_header,
# #     mock_llm_completion,
# #     mock_embedding,
# #     mock_youtube_transcript,
# # ):
# #     """YouTube 요약 API 테스트 (Mock)"""
#
# #     # Mock LLM 응답 설정
# #     def mock_side_effect(*args, **kwargs):
# #         from app.core.llm.types import LLMResult
#
# #         prompt = (
# #             kwargs.get("messages", [])[0].content
# #             if kwargs.get("messages")
# #             else ""
# #         )
#
# #         if "태그" in prompt or "키워드" in prompt:
# #             return LLMResult(
# #                 content='["YouTube", "영상", "콘텐츠"]',
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
# #         elif "카테고리" in prompt:
# #             return LLMResult(
# #                 content='["엔터테인먼트"]',
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
# #         else:
# #             return LLMResult(
# #                 content="YouTube 영상 요약입니다.",
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
#
# #     mock_llm_completion.side_effect = mock_side_effect
#
# #     # API 호출
# #     response = await client.post(
# #         "/api/v1/ai/summarize/youtube",
# #         json={
# #             "url": "https://www.youtube.com/watch?v=test_video_id",
# #             "user_id": 1,
# #             "tag_count": 5,
# #             "refresh": False,
# #         },
# #         headers=api_key_header,
# #     )
#
# #     # 응답 검증
# #     assert response.status_code == 200
# #     data = response.json()
#
# #     assert data["success"] is True
# #     assert "summary" in data["data"]
# #     assert "tags" in data["data"]
# #     assert "category" in data["data"]
#
#
# # @pytest.mark.asyncio
# # @pytest.mark.mock_ai
# # async def test_summarize_pdf_api(
# #     client, api_key_header, mock_llm_completion, mock_embedding
# # ):
# #     """PDF 요약 API 테스트 (Mock)"""
# #     from io import BytesIO
# #     from unittest.mock import patch
#
# #     # Mock LLM 응답 설정
# #     def mock_side_effect(*args, **kwargs):
# #         from app.core.llm.types import LLMResult
#
# #         prompt = (
# #             kwargs.get("messages", [])[0].content
# #             if kwargs.get("messages")
# #             else ""
# #         )
#
# #         if "태그" in prompt or "키워드" in prompt:
# #             return LLMResult(
# #                 content='["PDF", "문서", "연구"]',
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
# #         elif "카테고리" in prompt:
# #             return LLMResult(
# #                 content='["학술"]',
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
# #         else:
# #             return LLMResult(
# #                 content="PDF 문서 요약입니다.",
# #                 model="mock-model",
# #                 input_tokens=100,
# #                 output_tokens=50,
# #                 finish_reason="stop",
# #             )
#
# #     mock_llm_completion.side_effect = mock_side_effect
#
# #     # PDF 파일 준비 (Mock)
# #     pdf_content = b"%PDF-1.4\nMock PDF content"
# #     pdf_file = BytesIO(pdf_content)
#
# #     # PDF 파서 Mock
# #     with patch(
# #         "app.domains.ai.utils.parsers.extract_text_from_pdf"
# #     ) as mock_pdf_parser:
# #         mock_pdf_parser.return_value = (
# #             "Extracted PDF text content for testing"
# #         )
#
# #         # API 호출
# #         response = await client.post(
# #             "/api/v1/ai/summarize/pdf",
# #             data={"user_id": 1, "tag_count": 5},
# #             files={"pdf_file": ("test.pdf", pdf_file, "application/pdf")},
# #             headers=api_key_header,
# #         )
#
# #         # 응답 검증
# #         assert response.status_code == 200
# #         data = response.json()
#
# #         assert data["success"] is True
# #         assert "summary" in data["data"]
# #         assert "tags" in data["data"]
# #         assert "category" in data["data"]
#
#
# # @pytest.mark.asyncio
# # @pytest.mark.mock_ai
# # async def test_search_api_vector_mode(
# #     client, api_key_header, mock_embedding
# # ):
# #     """검색 API 테스트 - 벡터 모드 (Mock)"""
# #     from app.core.utils.datetime import now_utc
# #     from app.domains.ai.models import ContentEmbeddingMetadata
# #     from app.domains.contents.models import Content
#
# #     # 테스트 데이터 생성
# #     async with client.app.dependency_overrides.get(
# #         __import__("app.core.database", fromlist=["get_db"]).get_db
# #     )() as db_session:
# #         content = Content(
# #             id=1,
# #             user_id=1,
# #             content_type="webpage",
# #             source_url="https://example.com",
# #             title="AI Technology",
# #             summary="Latest AI trends",
# #             embedding_status="completed",
# #             created_at=now_utc(),
# #         )
# #         db_session.add(content)
# #         await db_session.flush()
#
# #         embedding = ContentEmbeddingMetadata(
# #             content_id=content.id,
# #             chunk_index=0,
# #             chunk_content="AI technology content",
# #             embedding_vector=[0.1] * 3072,
# #             embedding_model="text-embedding-3-large",
# #             created_at=now_utc(),
# #         )
# #         db_session.add(embedding)
# #         await db_session.commit()
#
# #     # API 호출
# #     response = await client.post(
# #         "/api/v1/ai/search",
# #         json={
# #             "query": "AI technology",
# #             "user_id": 1,
# #             "search_mode": "vector",
# #             "page": 1,
# #             "size": 20,
# #             "threshold": 0.0,
# #         },
# #         headers=api_key_header,
# #     )
#
# #     # 응답 검증
# #     assert response.status_code == 200
# #     data = response.json()
#
# #     assert data["success"] is True
# #     assert isinstance(data["data"], list)
# #     assert "total" in data["meta"]
#
#
# # @pytest.mark.asyncio
# # @pytest.mark.mock_ai
# # async def test_search_api_keyword_mode(client, api_key_header):
# #     """검색 API 테스트 - 키워드 모드 (Mock)"""
# #     from app.core.utils.datetime import now_utc
# #     from app.domains.contents.models import Content
#
# #     # 테스트 데이터 생성
# #     async with client.app.dependency_overrides.get(
# #         __import__("app.core.database", fromlist=["get_db"]).get_db
# #     )() as db_session:
# #         content = Content(
# #             id=2,
# #             user_id=1,
# #             content_type="webpage",
# #             source_url="https://example.com/python",
# #             title="Python Programming Guide",
# #             summary="Learn Python programming",
# #             created_at=now_utc(),
# #         )
# #         db_session.add(content)
# #         await db_session.commit()
#
# #     # API 호출
# #     response = await client.post(
# #         "/api/v1/ai/search",
# #         json={
# #             "query": "Python programming",
# #             "user_id": 1,
# #             "search_mode": "keyword",
# #             "page": 1,
# #             "size": 20,
# #         },
# #         headers=api_key_header,
# #     )
#
# #     # 응답 검증
# #     assert response.status_code == 200
# #     data = response.json()
#
# #     assert data["success"] is True
# #     assert isinstance(data["data"], list)
#
#
# # @pytest.mark.asyncio
# # @pytest.mark.mock_ai
# # async def test_search_api_hybrid_mode(
# #     client, api_key_header, mock_embedding
# # ):
# #     """검색 API 테스트 - 하이브리드 모드 (Mock)"""
# #     from app.core.utils.datetime import now_utc
# #     from app.domains.ai.models import ContentEmbeddingMetadata
# #     from app.domains.contents.models import Content
#
# #     # 테스트 데이터 생성
# #     async with client.app.dependency_overrides.get(
# #         __import__("app.core.database", fromlist=["get_db"]).get_db
# #     )() as db_session:
# #         content = Content(
# #             id=3,
# #             user_id=1,
# #             content_type="webpage",
# #             source_url="https://example.com/ml",
# #             title="Machine Learning Guide",
# #             summary="Machine learning fundamentals",
# #             embedding_status="completed",
# #             created_at=now_utc(),
# #         )
# #         db_session.add(content)
# #         await db_session.flush()
#
# #         embedding = ContentEmbeddingMetadata(
# #             content_id=content.id,
# #             chunk_index=0,
# #             chunk_content="Machine learning algorithms",
# #             embedding_vector=[0.2] * 3072,
# #             embedding_model="text-embedding-3-large",
# #             created_at=now_utc(),
# #         )
# #         db_session.add(embedding)
# #         await db_session.commit()
#
# #     # API 호출
# #     response = await client.post(
# #         "/api/v1/ai/search",
# #         json={
# #             "query": "machine learning",
# #             "user_id": 1,
# #             "search_mode": "hybrid",
# #             "page": 1,
# #             "size": 20,
# #             "threshold": 0.0,
# #         },
# #         headers=api_key_header,
# #     )
#
# #     # 응답 검증
# #     assert response.status_code == 200
# #     data = response.json()
#
# #     assert data["success"] is True
# #     assert isinstance(data["data"], list)
#
#
# # @pytest.mark.asyncio
# # @pytest.mark.mock_ai
# # async def test_api_authentication_required(client):
# #     """API 인증 필수 테스트"""
# #     # API Key 없이 요청
# #     response = await client.post(
# #         "/api/v1/ai/summarize/youtube",
# #         json={
# #             "url": "https://www.youtube.com/watch?v=test",
# #             "user_id": 1,
# #             "tag_count": 5,
# #         },
# #     )
#
# #     # 401 Unauthorized
# #     assert response.status_code == 401
#
#
# # @pytest.mark.asyncio
# # @pytest.mark.mock_ai
# # async def test_summarize_cache_behavior(
# #     client, api_key_header, mock_llm_completion, mock_embedding
# # ):
# #     """요약 캐시 동작 테스트"""
# #     from io import BytesIO
#
# #     # Mock LLM 응답 설정
# #     def mock_side_effect(*args, **kwargs):
# #         from app.core.llm.types import LLMResult
#
# #         return LLMResult(
# #             content="캐시 테스트 요약",
# #             model="mock-model",
# #             input_tokens=100,
# #             output_tokens=50,
# #             finish_reason="stop",
# #         )
#
# #     mock_llm_completion.side_effect = mock_side_effect
#
# #     html_content = "<html><body>Test content</body></html>"
# #     html_file = BytesIO(html_content.encode("utf-8"))
#
# #     # 첫 번째 요청 (캐시 미스)
# #     response1 = await client.post(
# #         "/api/v1/ai/summarize/webpage",
# #         data={
# #             "url": "https://example.com/cache-test",
# #             "user_id": 1,
# #             "tag_count": 5,
# #         },
# #         files={"html_file": ("test.html", html_file, "text/html")},
# #         headers=api_key_header,
# #     )
#
# #     assert response1.status_code == 200
# #     data1 = response1.json()
# #     assert data1["data"]["cached"] is False
#
# #     # 두 번째 요청 (캐시 히트)
# #     html_file.seek(0)  # 파일 포인터 초기화
# #     response2 = await client.post(
# #         "/api/v1/ai/summarize/webpage",
# #         data={
# #             "url": "https://example.com/cache-test",
# #             "user_id": 1,
# #             "tag_count": 5,
# #         },
# #         files={"html_file": ("test.html", html_file, "text/html")},
# #         headers=api_key_header,
# #     )
#
# #     assert response2.status_code == 200
# #     data2 = response2.json()
# #     assert data2["data"]["cached"] is True
# #     assert data2["data"]["summary"] == data1["data"]["summary"]
