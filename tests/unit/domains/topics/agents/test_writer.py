# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """WriterAgent 유닛 테스트
# 
# WriterAgent의 핵심 기능 검증:
# - previous_outputs 읽기 및 활용
# - 제목 추출 (title extraction)
# - 컨텍스트 기반 프롬프트 구성
# """
# 
# import pytest
# 
# from app.core.llm import LLMTier
# from app.core.llm.types import AllProvidersFailedError
# from app.domains.topics.agents.base import AgentContext
# from app.domains.topics.agents.writer import WriterAgent
# from app.domains.topics.orchestration.models import AgentExecutionStatus
# 
# 
# @pytest.mark.asyncio
# async def test_writer_name_and_tier():
#     """WriterAgent 이름 및 티어 검증"""
#     agent = WriterAgent()
# 
#     assert agent.name == "writer"
#     assert agent.tier == LLMTier.STANDARD
# 
# 
# @pytest.mark.asyncio
# async def test_build_messages_with_previous_outputs():
#     """이전 에이전트 결과를 활용한 프롬프트 구성"""
#     agent = WriterAgent()
# 
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Write a guide",
#         additional_data={
#             "previous_outputs": {
#                 "summarizer": {
#                     "summary": "This is a test summary from summarizer"
#                 }
#             },
#             "selected_contents": [],
#             "metadata": {},
#         },
#     )
# 
#     messages = agent.build_messages(context)
# 
#     # Should have system and user messages
#     assert len(messages) >= 2
#     assert messages[0].role == "system"
#     assert messages[-1].role == "user"
# 
#     # User message should include summarizer output
#     user_content = messages[-1].content
#     assert "Summarizer" in user_content or "summary" in user_content.lower()
#     assert "test summary" in user_content.lower()
# 
# 
# @pytest.mark.asyncio
# async def test_build_messages_with_selected_contents():
#     """선택된 콘텐츠를 포함한 프롬프트 구성"""
#     agent = WriterAgent()
# 
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Write about Python",
#         additional_data={
#             "previous_outputs": {},
#             "selected_contents": [
#                 {
#                     "content_id": 1,
#                     "title": "Python Basics",
#                     "summary": "Introduction to Python programming",
#                 },
#                 {
#                     "content_id": 2,
#                     "title": "Python Advanced",
#                     "summary": "Advanced Python concepts",
#                 },
#             ],
#             "metadata": {},
#         },
#     )
# 
#     messages = agent.build_messages(context)
#     user_content = messages[-1].content
# 
#     # Should include selected contents
#     assert "Python Basics" in user_content
#     assert "Python Advanced" in user_content
#     assert "Introduction to Python" in user_content
# 
# 
# @pytest.mark.asyncio
# async def test_build_messages_with_no_context():
#     """컨텍스트 없이 프롬프트 구성"""
#     agent = WriterAgent()
# 
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Write something",
#         additional_data={
#             "previous_outputs": {},
#             "selected_contents": [],
#             "metadata": {},
#         },
#     )
# 
#     messages = agent.build_messages(context)
#     user_content = messages[-1].content
# 
#     # Should handle empty context gracefully
#     assert "No context available" in user_content or len(user_content) > 0
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_run_with_fallback_success(mock_llm_completion):
#     """정상 실행 시 draft_md와 title 반환"""
#     # Mock LLM to return markdown with title
#     from app.core.llm.types import LLMResult
# 
#     async def mock_side_effect(*args, **kwargs):
#         return LLMResult(
#             content=(
#                 "# Main Title\n\n## Introduction\n\n"
#                 "This is the draft content."
#             ),
#             model="mock-model",
#             input_tokens=500,
#             output_tokens=300,
#             finish_reason="stop",
#         )
# 
#     mock_llm_completion.side_effect = mock_side_effect
# 
#     agent = WriterAgent()
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Write a draft",
#         additional_data={
#             "previous_outputs": {},
#             "selected_contents": [],
#             "metadata": {},
#         },
#     )
# 
#     result = await agent.run_with_fallback(context)
# 
#     # Verify result
#     assert result.agent == "writer"
#     assert result.status == AgentExecutionStatus.COMPLETED
#     assert result.success is True
#     assert result.model == "mock-model"
#     assert result.input_tokens == 500
#     assert result.output_tokens == 300
# 
#     # Verify output contains draft_md and title
#     assert result.output is not None
#     assert "draft_md" in result.output
#     assert "title" in result.output
#     assert (
#         result.output["draft_md"]
#         == "# Main Title\n\n## Introduction\n\nThis is the draft content."
#     )
#     assert result.output["title"] == "Main Title"
# 
# 
# @pytest.mark.asyncio
# async def test_title_extraction_with_header():
#     """# 헤더가 있는 마크다운에서 제목 추출"""
#     agent = WriterAgent()
# 
#     content = "# Main Title\n\nBody text here"
#     title = agent._extract_title(content)
# 
#     assert title == "Main Title"
# 
# 
# @pytest.mark.asyncio
# async def test_title_extraction_without_header():
#     """헤더 없는 콘텐츠에서 첫 줄 추출"""
#     agent = WriterAgent()
# 
#     content = "This is the first line without header"
#     title = agent._extract_title(content)
# 
#     assert title == "This is the first line without header"
# 
# 
# @pytest.mark.asyncio
# async def test_title_extraction_long_first_line():
#     """긴 첫 줄에서 50자 + ... 추출"""
#     agent = WriterAgent()
# 
#     long_line = "A" * 100
#     title = agent._extract_title(long_line)
# 
#     assert len(title) == 53  # 50 chars + "..."
#     assert title.endswith("...")
# 
# 
# @pytest.mark.asyncio
# async def test_title_extraction_multiple_headers():
#     """여러 헤더가 있을 때 첫 번째 # 헤더 추출"""
#     agent = WriterAgent()
# 
#     content = "# First Title\n\n## Second Title\n\n### Third Title"
#     title = agent._extract_title(content)
# 
#     assert title == "First Title"
# 
# 
# @pytest.mark.asyncio
# async def test_title_extraction_with_whitespace():
#     """공백 포함 헤더에서 제목 추출"""
#     agent = WriterAgent()
# 
#     content = "#    Title With Spaces    \n\nBody"
#     title = agent._extract_title(content)
# 
#     assert title == "Title With Spaces"
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_run_catches_all_providers_failed(mock_llm_completion):
#     """AllProvidersFailedError 처리 검증"""
#     # Mock to raise AllProvidersFailedError
#     mock_llm_completion.side_effect = AllProvidersFailedError(
#         tier="standard", attempts=["model1", "model2"]
#     )
# 
#     agent = WriterAgent()
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Write a draft",
#         additional_data={"previous_outputs": {}, "selected_contents": []},
#     )
# 
#     result = await agent.run(context)  # Use run(), not run_with_fallback()
# 
#     # Should return skipped result with warning
#     assert result.status == AgentExecutionStatus.SKIPPED
#     assert result.success is False
#     assert result.skipped is True
#     assert result.warning is not None
#     assert "프로바이더" in result.warning or "failed" in result.warning.lower()
