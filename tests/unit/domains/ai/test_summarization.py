# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """요약 서비스 단위 테스트"""
# 
# import pytest
# 
# from app.domains.ai.summarization.service import SummarizationService
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_summarize_webpage_with_cache(
#     db_session, mock_llm_completion, mock_embedding
# ):
#     """웹페이지 요약 - 캐시 히트 테스트"""
#     from app.core.llm.types import LLMResult
# 
#     service = SummarizationService(db_session)
# 
#     # Mock LLM 응답 설정
#     def mock_side_effect(*args, **kwargs):
#         prompt = (
#             kwargs.get("messages", [])[0].content
#             if kwargs.get("messages")
#             else ""
#         )
# 
#         if "태그" in prompt or "키워드" in prompt:
#             return LLMResult(
#                 content='["AI", "기술", "트렌드"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         elif "카테고리" in prompt:
#             return LLMResult(
#                 content='["기술"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         else:
#             return LLMResult(
#                 content="Test summary",
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
# 
#     mock_llm_completion.side_effect = mock_side_effect
# 
#     url = "https://example.com/test"
#     html_content = "<html><body><h1>Test</h1><p>Content</p></body></html>"
#     user_id = 1
# 
#     # 첫 번째 요약 (캐시 미스)
#     result1 = await service.summarize_webpage(
#         url=url,
#         html_content=html_content,
#         user_id=user_id,
#         tag_count=5,
#         refresh=False,
#     )
# 
#     assert result1["cached"] is False
#     assert "summary" in result1
# 
#     # 두 번째 요약 (캐시 히트)
#     result2 = await service.summarize_webpage(
#         url=url,
#         html_content=html_content,
#         user_id=user_id,
#         tag_count=5,
#         refresh=False,
#     )
# 
#     assert result2["cached"] is True
#     assert result2["summary"] == result1["summary"]
# 
#     # LLM은 한 번만 호출되어야 함 (캐시 사용)
#     # 첫 호출: summary, tags, category = 3번
#     assert mock_llm_completion.call_count == 3
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_summarize_webpage_with_refresh(
#     db_session, mock_llm_completion, mock_embedding
# ):
#     """웹페이지 요약 - 강제 재생성 테스트"""
#     from app.core.llm.types import LLMResult
# 
#     service = SummarizationService(db_session)
# 
#     # Mock LLM 응답 설정
#     def mock_side_effect(*args, **kwargs):
#         prompt = (
#             kwargs.get("messages", [])[0].content
#             if kwargs.get("messages")
#             else ""
#         )
# 
#         if "태그" in prompt or "키워드" in prompt:
#             return LLMResult(
#                 content='["AI", "기술"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         elif "카테고리" in prompt:
#             return LLMResult(
#                 content='["기술"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         else:
#             return LLMResult(
#                 content="Test summary",
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
# 
#     mock_llm_completion.side_effect = mock_side_effect
# 
#     url = "https://example.com/test"
#     html_content = "<html><body>Content</body></html>"
#     user_id = 1
# 
#     # 첫 번째 요약
#     await service.summarize_webpage(
#         url=url,
#         html_content=html_content,
#         user_id=user_id,
#         tag_count=5,
#         refresh=False,
#     )
# 
#     # refresh=True로 재생성
#     result = await service.summarize_webpage(
#         url=url,
#         html_content=html_content,
#         user_id=user_id,
#         tag_count=5,
#         refresh=True,
#     )
# 
#     assert result["cached"] is False
# 
#     # LLM 두 번 호출 (첫 호출 3번 + 재생성 3번)
#     assert mock_llm_completion.call_count == 6
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_extract_tags_from_summary(
#     db_session, mock_llm_completion, mock_embedding
# ):
#     """요약에서 태그 추출 테스트"""
#     service = SummarizationService(db_session)
# 
#     # JSON 형식 태그 응답 Mock
#     def mock_side_effect(*args, **kwargs):
#         # 프롬프트에 따라 다른 응답
#         from app.core.llm.types import LLMResult
# 
#         prompt = (
#             kwargs.get("messages", [])[0].content
#             if kwargs.get("messages")
#             else ""
#         )
# 
#         if "태그" in prompt or "키워드" in prompt:
#             return LLMResult(
#                 content='["AI", "기술", "트렌드"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         elif "카테고리" in prompt:
#             return LLMResult(
#                 content='["기술"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         else:
#             return LLMResult(
#                 content="Test summary content",
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
# 
#     mock_llm_completion.side_effect = mock_side_effect
# 
#     url = "https://example.com/ai-trends"
#     html_content = "<html><body>AI technology trends</body></html>"
#     user_id = 1
# 
#     result = await service.summarize_webpage(
#         url=url,
#         html_content=html_content,
#         user_id=user_id,
#         tag_count=5,
#         refresh=False,
#     )
# 
#     # 태그가 파싱되어야 함
#     assert "tags" in result
#     assert isinstance(result["tags"], list)
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_summarize_youtube(
#     db_session, mock_llm_completion, mock_embedding, mock_youtube_transcript
# ):
#     """YouTube 요약 테스트"""
#     from app.core.llm.types import LLMResult
# 
#     service = SummarizationService(db_session)
# 
#     # Mock LLM 응답 설정
#     def mock_side_effect(*args, **kwargs):
#         prompt = (
#             kwargs.get("messages", [])[0].content
#             if kwargs.get("messages")
#             else ""
#         )
# 
#         if "태그" in prompt or "키워드" in prompt:
#             return LLMResult(
#                 content='["YouTube", "영상"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         elif "카테고리" in prompt:
#             return LLMResult(
#                 content='["엔터테인먼트"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         else:
#             return LLMResult(
#                 content="YouTube summary",
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
# 
#     mock_llm_completion.side_effect = mock_side_effect
# 
#     url = "https://www.youtube.com/watch?v=test_video_id"
#     user_id = 1
# 
#     result = await service.summarize_youtube(
#         url=url, user_id=user_id, tag_count=5, refresh=False
#     )
# 
#     assert "summary" in result
#     assert "tags" in result
#     assert "category" in result
#     assert result["cached"] is False
# 
#     # YouTube transcript API 호출 확인
#     mock_youtube_transcript.assert_called()
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_summarize_pdf(db_session, mock_llm_completion, mock_embedding):
#     """PDF 요약 테스트"""
#     from unittest.mock import patch
# 
#     from app.core.llm.types import LLMResult
# 
#     service = SummarizationService(db_session)
# 
#     # Mock LLM 응답 설정
#     def mock_side_effect(*args, **kwargs):
#         prompt = (
#             kwargs.get("messages", [])[0].content
#             if kwargs.get("messages")
#             else ""
#         )
# 
#         if "태그" in prompt or "키워드" in prompt:
#             return LLMResult(
#                 content='["PDF", "문서"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         elif "카테고리" in prompt:
#             return LLMResult(
#                 content='["학술"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         else:
#             return LLMResult(
#                 content="PDF summary",
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
# 
#     mock_llm_completion.side_effect = mock_side_effect
# 
#     # 간단한 PDF 내용 (실제로는 bytes이지만 테스트에서는 텍스트로 대체)
#     pdf_content = b"%PDF-1.4\nTest PDF content"
#     user_id = 1
# 
#     # PDF 파서 Mock
#     with patch(
#         "app.domains.ai.utils.parsers.extract_text_from_pdf"
#     ) as mock_pdf_parser:
#         mock_pdf_parser.return_value = "Extracted PDF text content"
# 
#         result = await service.summarize_pdf(
#             pdf_content=pdf_content,
#             user_id=user_id,
#             tag_count=5,
#             refresh=False,
#         )
# 
#         assert "summary" in result
#         assert "tags" in result
#         assert "category" in result
#         assert result["cached"] is False
# 
#         # PDF 파서 호출 확인
#         mock_pdf_parser.assert_called_once_with(pdf_content)
# 
# 
# @pytest.mark.mock_ai
# def test_parse_json_array():
#     """JSON 배열 파싱 테스트"""
#     from app.domains.ai.summarization.service import SummarizationService
# 
#     # 정상 JSON
#     result = SummarizationService._parse_json_array('["tag1", "tag2", "tag3"]')
#     assert result == ["tag1", "tag2", "tag3"]
# 
#     # 마크다운 코드블록
#     result = SummarizationService._parse_json_array(
#         '```json\n["tag1", "tag2"]\n```'
#     )
#     assert result == ["tag1", "tag2"]
# 
#     # 백틱만
#     result = SummarizationService._parse_json_array('```["tag1"]```')
#     assert result == ["tag1"]
# 
#     # 잘못된 JSON은 fallback으로 원본 문자열을 리스트로 반환
#     result = SummarizationService._parse_json_array("invalid json")
#     assert result == ["invalid json"]
# 
#     # 빈 문자열은 빈 리스트 반환
#     result = SummarizationService._parse_json_array("")
#     assert result == []
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_content_hash_detection(
#     db_session, mock_llm_completion, mock_embedding
# ):
#     """콘텐츠 변경 감지 테스트"""
#     from app.core.llm.types import LLMResult
# 
#     service = SummarizationService(db_session)
# 
#     # Mock LLM 응답 설정
#     def mock_side_effect(*args, **kwargs):
#         prompt = (
#             kwargs.get("messages", [])[0].content
#             if kwargs.get("messages")
#             else ""
#         )
# 
#         if "태그" in prompt or "키워드" in prompt:
#             return LLMResult(
#                 content='["테스트", "콘텐츠"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         elif "카테고리" in prompt:
#             return LLMResult(
#                 content='["기술"]',
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
#         else:
#             return LLMResult(
#                 content="Test summary",
#                 model="mock-model",
#                 input_tokens=100,
#                 output_tokens=50,
#                 finish_reason="stop",
#             )
# 
#     mock_llm_completion.side_effect = mock_side_effect
# 
#     url = "https://example.com/article"
#     html_content_v1 = "<html><body>Version 1</body></html>"
#     html_content_v2 = "<html><body>Version 2 - Updated</body></html>"
#     user_id = 1
# 
#     # 첫 번째 버전 요약
#     result1 = await service.summarize_webpage(
#         url=url,
#         html_content=html_content_v1,
#         user_id=user_id,
#         tag_count=5,
#         refresh=False,
#     )
#     assert result1["cached"] is False
# 
#     # 동일한 콘텐츠 - 캐시 히트
#     result2 = await service.summarize_webpage(
#         url=url,
#         html_content=html_content_v1,
#         user_id=user_id,
#         tag_count=5,
#         refresh=False,
#     )
#     assert result2["cached"] is True
# 
#     # 콘텐츠 변경 - 캐시 미스 (content_hash 다름)
#     result3 = await service.summarize_webpage(
#         url=url,
#         html_content=html_content_v2,
#         user_id=user_id,
#         tag_count=5,
#         refresh=False,
#     )
#     assert result3["cached"] is False
# 
#     # LLM 호출: 첫 호출 3번 + 변경 후 3번 = 6번
#     assert mock_llm_completion.call_count == 6
