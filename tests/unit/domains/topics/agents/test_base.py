# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """BaseAgent 유닛 테스트
#
# BaseAgent의 에러 처리 로직 검증
# """
#
# import pytest
#
# from app.core.llm import LLMMessage, LLMTier
# from app.core.llm.types import AllProvidersFailedError
# from app.domains.topics.agents.base import AgentContext, BaseAgent
# from app.domains.topics.orchestration.models import (
#     AgentExecutionStatus,
#     AgentResult,
# )
#
#
# class TestAgent(BaseAgent):
#     """테스트용 Agent 구현"""
#
#     def __init__(self, should_raise: Exception | None = None):
#         super().__init__(tier=LLMTier.LIGHT)
#         self.should_raise = should_raise
#
#     @property
#     def name(self) -> str:
#         return "test_agent"
#
#     def build_messages(self, context: AgentContext) -> list[LLMMessage]:
#         return []
#
#     async def run_with_fallback(self, context: AgentContext) -> AgentResult:
#         if self.should_raise:
#             raise self.should_raise
#
#         return AgentResult(
#             agent=self.name,
#             status=AgentExecutionStatus.COMPLETED,
#             success=True,
#             model="mock-model",
#             input_tokens=100,
#             output_tokens=50,
#         )
#
#
# @pytest.mark.asyncio
# async def test_base_agent_run_catches_all_providers_failed():
#     """AllProvidersFailedError → SKIPPED 결과 반환"""
#     agent = TestAgent(
#         should_raise=AllProvidersFailedError(
#             tier="light", attempts=["model1", "model2"]
#         )
#     )
#
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Test",
#         additional_data={},
#     )
#
#     result = await agent.run(context)
#
#     assert result.status == AgentExecutionStatus.SKIPPED
#     assert result.success is False
#     assert result.skipped is True
#     assert result.warning == "모든 프로바이더가 실패했습니다."
#     assert result.error is not None
#
#
# @pytest.mark.asyncio
# async def test_base_agent_run_catches_generic_exceptions():
#     """일반 예외 → FAILED 결과 반환"""
#     agent = TestAgent(should_raise=ValueError("Test error"))
#
#     context = AgentContext(
#         request_id="test",
#         user_id=1,
#         prompt="Test",
#         additional_data={},
#     )
#
#     result = await agent.run(context)
#
#     assert result.status == AgentExecutionStatus.FAILED
#     assert result.success is False
#     assert result.error == "Test error"
#
#
# @pytest.mark.asyncio
# async def test_build_failure_result():
#     """실패 결과 생성 검증"""
#     agent = TestAgent()
#
#     result = agent._build_failure_result("Error message")
#
#     assert result.agent == "test_agent"
#     assert result.status == AgentExecutionStatus.FAILED
#     assert result.success is False
#     assert result.error == "Error message"
#
#
# @pytest.mark.asyncio
# async def test_build_skipped_result():
#     """스킵 결과 생성 검증"""
#     agent = TestAgent()
#
#     result = agent._build_skipped_result(
#         warning="Skipped reason", error="Error detail"
#     )
#
#     assert result.agent == "test_agent"
#     assert result.status == AgentExecutionStatus.SKIPPED
#     assert result.success is False
#     assert result.skipped is True
#     assert result.warning == "Skipped reason"
#     assert result.error == "Error detail"
