# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """SummarizerAgent 유닛 테스트"""
# 
# import pytest
# 
# from app.core.llm import LLMTier
# from app.core.llm.types import AllProvidersFailedError
# from app.domains.topics.agents.base import AgentContext
# from app.domains.topics.agents.summarizer import SummarizerAgent
# from app.domains.topics.orchestration.models import AgentExecutionStatus
# 
# 
# @pytest.mark.asyncio
# async def test_summarizer_name():
#     """SummarizerAgent 이름 검증"""
#     agent = SummarizerAgent()
#     assert agent.name == "summarizer"
# 
# 
# @pytest.mark.asyncio
# async def test_summarizer_tier():
#     """SummarizerAgent 티어 검증"""
#     agent = SummarizerAgent()
#     assert agent.tier == LLMTier.LIGHT
# 
# 
# @pytest.mark.asyncio
# async def test_build_messages_structure():
#     """프롬프트 구조 검증"""
#     agent = SummarizerAgent()
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Content to summarize",
#         additional_data={},
#     )
# 
#     messages = agent.build_messages(context)
# 
#     # Should have system and user messages
#     assert len(messages) == 2
#     assert messages[0].role == "system"
#     assert messages[1].role == "user"
# 
#     # System message should mention summarizing
#     assert "summar" in messages[0].content.lower()
# 
#     # User message should contain prompt
#     assert "Content to summarize" in messages[1].content
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_run_with_fallback_success(mock_llm_completion):
#     """정상 실행 시 summary 반환"""
#     from app.core.llm.types import LLMResult
# 
#     async def mock_side_effect(*args, **kwargs):
#         return LLMResult(
#             content="This is a test summary of the content.",
#             model="mock-model",
#             input_tokens=100,
#             output_tokens=50,
#             finish_reason="stop",
#         )
# 
#     mock_llm_completion.side_effect = mock_side_effect
# 
#     agent = SummarizerAgent()
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Content to summarize",
#         additional_data={},
#     )
# 
#     result = await agent.run_with_fallback(context)
# 
#     # Verify result
#     assert result.agent == "summarizer"
#     assert result.status == AgentExecutionStatus.COMPLETED
#     assert result.success is True
#     assert result.model == "mock-model"
#     assert result.input_tokens == 100
#     assert result.output_tokens == 50
# 
#     # Verify output contains summary
#     assert result.output is not None
#     assert "summary" in result.output
#     assert result.output["summary"] == "This is a test summary of the content."
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_run_with_fallback_failure(mock_llm_completion):
#     """LLM 실패 시 처리"""
#     # Mock to raise AllProvidersFailedError
#     mock_llm_completion.side_effect = AllProvidersFailedError(
#         tier="light", attempts=["model1", "model2"]
#     )
# 
#     agent = SummarizerAgent()
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Content to summarize",
#         additional_data={},
#     )
# 
#     result = await agent.run(context)  # Use run(), not run_with_fallback()
# 
#     # Should return skipped result
#     assert result.status == AgentExecutionStatus.SKIPPED
#     assert result.success is False
#     assert result.skipped is True
#     assert result.warning is not None
