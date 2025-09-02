"""
LangGraph 통합 테스트

LangGraph 기반 에이전트 시스템의 기본 기능을 테스트합니다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.agents.langgraph.adapter import LangGraphAgentAdapter, AgentMode
from app.agents.langgraph.state import create_initial_state, AgentState
from app.agents.langgraph.nodes.content_analysis_node import ContentAnalysisNode
from app.agents.langgraph.nodes.tag_extraction_node import TagExtractionNode
from app.agents.schemas import AgentContext, UserModelPreferences


@pytest.fixture
def sample_user_preferences():
    """테스트용 사용자 선호도"""
    return UserModelPreferences(
        default_llm_model="gpt-4o-mini",
        preferred_providers=["openai"],
        avoid_models=[],
        quality_preference="balance",
        cost_sensitivity="medium"
    )


@pytest.fixture
def sample_agent_context(sample_user_preferences):
    """테스트용 에이전트 컨텍스트"""
    return AgentContext(
        user_id=1001,
        board_id=123,
        complexity=3,
        user_model_preferences=sample_user_preferences
    )


@pytest.fixture
def sample_webpage_input():
    """테스트용 웹페이지 입력 데이터"""
    return {
        "content_type": "webpage",
        "url": "https://example.com/react-tutorial",
        "title": "React Hooks 완벽 가이드",
        "html_content": "React Hooks는 함수형 컴포넌트에서 상태와 생명주기를 관리할 수 있게 해주는 강력한 기능입니다...",
        "similar_tags": ["React", "JavaScript", "프론트엔드"],
        "tag_count": 5
    }


class TestLangGraphAgentAdapter:
    """LangGraph 에이전트 어댑터 테스트"""
    
    def test_adapter_initialization(self):
        """어댑터 초기화 테스트"""
        adapter = LangGraphAgentAdapter()
        
        assert adapter.default_mode == AgentMode.AUTO
        assert adapter.execution_stats["legacy_executions"] == 0
        assert adapter.execution_stats["langgraph_executions"] == 0
    
    @pytest.mark.asyncio
    async def test_determine_execution_mode_auto_langgraph(self, sample_agent_context, sample_webpage_input):
        """자동 모드 선택 테스트 - LangGraph 선택"""
        adapter = LangGraphAgentAdapter()
        
        # 복잡도 3 이상, 품질 중시 -> LangGraph 선택
        sample_agent_context.complexity = 4
        sample_agent_context.user_model_preferences.quality_preference = "quality"
        
        mode = await adapter._determine_execution_mode(
            mode=AgentMode.AUTO,
            context=sample_agent_context,
            input_data=sample_webpage_input
        )
        
        assert mode == AgentMode.LANGGRAPH
    
    @pytest.mark.asyncio
    async def test_determine_execution_mode_auto_legacy(self, sample_agent_context, sample_webpage_input):
        """자동 모드 선택 테스트 - 레거시 선택"""
        adapter = LangGraphAgentAdapter()
        
        # 복잡도 낮음, 속도 중시 -> Legacy 선택
        sample_agent_context.complexity = 2
        sample_agent_context.user_model_preferences.quality_preference = "speed"
        
        mode = await adapter._determine_execution_mode(
            mode=AgentMode.AUTO,
            context=sample_agent_context,
            input_data={}
        )
        
        assert mode == AgentMode.LEGACY
    
    def test_convert_langgraph_result_success(self):
        """LangGraph 성공 결과 변환 테스트"""
        adapter = LangGraphAgentAdapter()
        
        langgraph_result = {
            "success": True,
            "summary": "React Hooks 사용법을 설명한 튜토리얼",
            "tags": ["React", "Hooks", "JavaScript"],
            "category": "프로그래밍",
            "validation_passed": True,
            "validation_score": 0.92,
            "execution_stats": {
                "total_tokens_used": 450,
                "total_wtu_consumed": 1.2,
                "total_cost_usd": 0.003,
                "execution_time_seconds": 2.5
            },
            "detailed_results": {
                "content_analysis": {"summary": "React Hooks 사용법을 설명한 튜토리얼"},
                "tag_extraction": {"tags": ["React", "Hooks", "JavaScript"]},
                "category_classification": {"category": "프로그래밍"}
            }
        }
        
        agent_response = adapter._convert_langgraph_result_to_agent_response(langgraph_result)
        
        assert agent_response.success is True
        assert agent_response.content["summary"] == "React Hooks 사용법을 설명한 튜토리얼"
        assert agent_response.content["tags"] == ["React", "Hooks", "JavaScript"]
        assert agent_response.wtu_consumed == 1.2
        assert agent_response.execution_time_ms == 2500
        assert agent_response.metadata["execution_mode"] == "langgraph"
    
    def test_convert_langgraph_result_failure(self):
        """LangGraph 실패 결과 변환 테스트"""
        adapter = LangGraphAgentAdapter()
        
        langgraph_result = {
            "success": False,
            "error": "AI API 호출 실패"
        }
        
        agent_response = adapter._convert_langgraph_result_to_agent_response(langgraph_result)
        
        assert agent_response.success is False
        assert "AI API 호출 실패" in agent_response.content
        assert agent_response.error_message == "AI API 호출 실패"


class TestAgentState:
    """에이전트 상태 관리 테스트"""
    
    def test_create_initial_state(self, sample_agent_context, sample_webpage_input):
        """초기 상태 생성 테스트"""
        session_id = "test-session-123"
        
        state = create_initial_state(
            user_id=1001,
            input_data=sample_webpage_input,
            context=sample_agent_context,
            session_id=session_id
        )
        
        assert state["user_id"] == 1001
        assert state["board_id"] == 123
        assert state["session_id"] == session_id
        assert state["input_data"] == sample_webpage_input
        assert state["complexity_level"] == 3
        assert state["should_validate"] is True  # complexity >= 3
        assert state["success"] is False  # 초기값
        assert len(state["completed_nodes"]) == 0
        assert len(state["errors"]) == 0


class TestContentAnalysisNode:
    """콘텐츠 분석 노드 테스트"""
    
    def test_node_initialization(self):
        """노드 초기화 테스트"""
        node = ContentAnalysisNode()
        
        assert node.node_name == "content_analysis"
        assert node.get_node_type() == "content_analysis"
        assert node.execution_count == 0
    
    @pytest.mark.asyncio
    @patch('app.ai.providers.router.ai_router')
    async def test_analyze_webpage_success(self, mock_router, sample_agent_context, sample_webpage_input):
        """웹페이지 분석 성공 테스트"""
        node = ContentAnalysisNode()
        
        # Mock AI router response
        mock_router.generate_webpage_summary.return_value = "React Hooks 사용법을 설명한 튜토리얼"
        
        # 테스트 상태 생성
        state = create_initial_state(
            user_id=1001,
            input_data=sample_webpage_input,
            context=sample_agent_context,
            session_id="test-session"
        )
        
        # 노드 실행
        result = await node.process(state)
        
        assert result["content_type"] == "webpage"
        assert result["url"] == "https://example.com/react-tutorial"
        assert "React Hooks" in result["summary"]
        assert result["model_used"] == "gpt-4o-mini"
        assert result["tokens_used"] > 0
        assert result["wtu_consumed"] > 0
        
        # AI router 호출 확인
        mock_router.generate_webpage_summary.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_webpage_missing_content(self, sample_agent_context):
        """웹페이지 분석 실패 테스트 - 콘텐츠 누락"""
        node = ContentAnalysisNode()
        
        # HTML 콘텐츠가 없는 입력 데이터
        empty_input = {
            "content_type": "webpage",
            "url": "https://example.com",
            "html_content": ""  # 빈 콘텐츠
        }
        
        state = create_initial_state(
            user_id=1001,
            input_data=empty_input,
            context=sample_agent_context,
            session_id="test-session"
        )
        
        # 예외 발생 확인
        with pytest.raises(ValueError, match="HTML 콘텐츠가 제공되지 않았습니다"):
            await node.process(state)


class TestTagExtractionNode:
    """태그 추출 노드 테스트"""
    
    def test_node_initialization(self):
        """노드 초기화 테스트"""
        node = TagExtractionNode()
        
        assert node.node_name == "tag_extraction"
        assert node.get_node_type() == "tag_extraction"
    
    def test_refine_tags(self):
        """태그 정제 기능 테스트"""
        node = TagExtractionNode()
        
        # 중복 및 빈 태그가 있는 테스트 데이터
        raw_tags = [
            "React",
            "react",  # 대소문자 중복
            "JavaScript",
            "",  # 빈 태그
            "  Hooks  ",  # 공백 포함
            "프론트엔드",
            "React",  # 완전 중복
            "개발"
        ]
        
        refined = node._refine_tags(raw_tags, max_count=5)
        
        assert len(refined) == 5
        assert "React" in refined
        assert "react" not in refined  # 중복 제거됨
        assert "Hooks" in refined  # 공백 제거됨
        assert "" not in refined  # 빈 태그 제거됨
        assert "JavaScript" in refined
        assert "프론트엔드" in refined
    
    @pytest.mark.asyncio
    async def test_process_without_content_analysis(self, sample_agent_context, sample_webpage_input):
        """콘텐츠 분석 결과 없이 태그 추출 시도 - 실패 테스트"""
        node = TagExtractionNode()
        
        # content_analysis 결과가 없는 상태
        state = create_initial_state(
            user_id=1001,
            input_data=sample_webpage_input,
            context=sample_agent_context,
            session_id="test-session"
        )
        
        # 예외 발생 확인
        with pytest.raises(ValueError, match="콘텐츠 분석 결과가 없습니다"):
            await node.process(state)


@pytest.mark.asyncio
class TestLangGraphIntegration:
    """LangGraph 통합 기능 테스트"""
    
    @patch('app.agents.langgraph.adapter.content_processing_graph')
    async def test_process_content_with_langgraph_success(self, mock_graph, sample_agent_context, sample_webpage_input):
        """LangGraph를 통한 콘텐츠 처리 성공 테스트"""
        from app.agents.langgraph.adapter import process_content_with_langgraph
        
        # Mock graph response
        mock_graph.process_content.return_value = {
            "success": True,
            "summary": "React Hooks 튜토리얼 요약",
            "tags": ["React", "Hooks", "JavaScript"],
            "category": "프로그래밍",
            "execution_stats": {
                "total_tokens_used": 350,
                "total_wtu_consumed": 0.8,
                "total_cost_usd": 0.002,
                "execution_time_seconds": 1.5
            }
        }
        
        result = await process_content_with_langgraph(
            user_id=1001,
            input_data=sample_webpage_input,
            context=sample_agent_context,
            mode="langgraph"
        )
        
        assert result.success is True
        assert result.content["summary"] == "React Hooks 튜토리얼 요약"
        assert result.content["tags"] == ["React", "Hooks", "JavaScript"]
        assert result.wtu_consumed == 0.8
        assert result.execution_time_ms == 1500
        
        # Graph 호출 확인
        mock_graph.process_content.assert_called_once_with(
            user_id=1001,
            input_data=sample_webpage_input,
            context=sample_agent_context,
            mode="langgraph",
            session=None
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])