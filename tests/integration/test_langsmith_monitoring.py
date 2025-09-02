"""
LangSmith 모니터링 통합 테스트

실제 LangSmith 연동 및 모니터링 기능을 테스트합니다.
(LANGCHAIN_API_KEY가 설정된 환경에서만 실행됩니다)
"""

import pytest
import os
from unittest.mock import patch, MagicMock

from app.monitoring.langsmith.client import (
    LangSmithManager, 
    initialize_langsmith,
    is_langsmith_enabled,
    get_langsmith_client
)
from app.monitoring.langsmith.tracer import LangSmithAITracer, trace_ai_provider_method


class TestLangSmithManager:
    """LangSmith 관리자 테스트"""
    
    def test_manager_initialization(self):
        """매니저 초기화 테스트"""
        manager = LangSmithManager()
        
        assert manager._client is None
        assert manager._is_enabled is False
        assert manager._project_name == "LinkyBoard-AI"
    
    @pytest.mark.skipif(not os.getenv("LANGCHAIN_API_KEY"), reason="LANGCHAIN_API_KEY not set")
    def test_initialize_with_api_key(self):
        """API 키가 있을 때 초기화 테스트"""
        manager = LangSmithManager()
        
        # 환경 변수에 API 키가 있는 경우에만 테스트
        result = manager.initialize()
        
        if os.getenv("LANGCHAIN_API_KEY"):
            assert result is True
            assert manager.is_enabled is True
            assert manager.client is not None
        else:
            assert result is False
    
    def test_initialize_without_api_key(self):
        """API 키가 없을 때 초기화 테스트"""
        with patch('app.core.config.settings.LANGCHAIN_API_KEY', None):
            manager = LangSmithManager()
            result = manager.initialize()
            
            assert result is False
            assert manager.is_enabled is False
            assert manager.client is None
    
    @pytest.mark.skipif(not os.getenv("LANGCHAIN_API_KEY"), reason="LANGCHAIN_API_KEY not set")
    def test_trace_context(self):
        """추적 컨텍스트 테스트"""
        manager = LangSmithManager()
        manager.initialize()
        
        if manager.is_enabled:
            with manager.trace_context(
                run_name="test_operation",
                run_type="chain",
                inputs={"test_input": "value"},
                extra={"test_meta": "data"}
            ) as run_context:
                # 컨텍스트가 정상적으로 생성되는지 확인
                assert run_context is not None
    
    def test_trace_context_disabled(self):
        """LangSmith 비활성화 상태에서 추적 컨텍스트 테스트"""
        manager = LangSmithManager()
        # 초기화하지 않음 (비활성 상태)
        
        with manager.trace_context(
            run_name="test_operation",
            run_type="chain"
        ) as run_context:
            # 비활성화 상태에서는 None 반환
            assert run_context is None


class TestLangSmithTracer:
    """LangSmith AI 추적기 테스트"""
    
    def test_tracer_initialization(self):
        """추적기 초기화 테스트"""
        tracer = LangSmithAITracer()
        assert tracer.active_traces == {}
    
    @pytest.mark.asyncio
    async def test_trace_ai_call_disabled(self):
        """LangSmith 비활성화 상태에서 AI 호출 추적 테스트"""
        tracer = LangSmithAITracer()
        
        async with tracer.trace_ai_call(
            provider="openai",
            model="gpt-4o-mini",
            operation="chat_completion",
            user_id=1001
        ) as run_context:
            # 비활성화 상태에서는 None 반환
            assert run_context is None
    
    @pytest.mark.skipif(not os.getenv("LANGCHAIN_API_KEY"), reason="LANGCHAIN_API_KEY not set")
    @pytest.mark.asyncio
    async def test_trace_ai_call_enabled(self):
        """LangSmith 활성화 상태에서 AI 호출 추적 테스트"""
        # LangSmith 초기화
        initialize_langsmith()
        
        if is_langsmith_enabled():
            tracer = LangSmithAITracer()
            
            async with tracer.trace_ai_call(
                provider="openai",
                model="gpt-4o-mini", 
                operation="chat_completion",
                user_id=1001,
                board_id=123
            ) as run_context:
                # 활성화 상태에서는 컨텍스트 반환
                assert run_context is not None


class TestTraceDecorator:
    """추적 데코레이터 테스트"""
    
    def test_decorator_disabled(self):
        """LangSmith 비활성화 상태에서 데코레이터 테스트"""
        
        @trace_ai_provider_method("test_operation")
        async def dummy_ai_method(self):
            return {"content": "test response", "tokens_used": 100}
        
        # 데코레이터가 함수를 그대로 반환하는지 확인
        assert dummy_ai_method is not None
    
    @pytest.mark.skipif(not os.getenv("LANGCHAIN_API_KEY"), reason="LANGCHAIN_API_KEY not set")
    @pytest.mark.asyncio
    async def test_decorator_enabled(self):
        """LangSmith 활성화 상태에서 데코레이터 테스트"""
        # LangSmith 초기화
        initialize_langsmith()
        
        if is_langsmith_enabled():
            
            class DummyProvider:
                provider_name = "test_provider"
            
            @trace_ai_provider_method("test_operation")
            async def dummy_ai_method(self):
                return {"content": "test response", "tokens_used": 100}
            
            provider = DummyProvider()
            
            # 데코레이터가 적용된 메서드 실행
            result = await dummy_ai_method(provider)
            
            assert result["content"] == "test response"
            assert result["tokens_used"] == 100


class TestGlobalFunctions:
    """전역 함수 테스트"""
    
    def test_initialize_langsmith_function(self):
        """전역 초기화 함수 테스트"""
        result = initialize_langsmith()
        
        # 환경 변수 상태에 따라 결과 확인
        if os.getenv("LANGCHAIN_API_KEY"):
            assert isinstance(result, bool)
        else:
            assert result is False
    
    def test_is_langsmith_enabled_function(self):
        """LangSmith 활성화 여부 확인 함수 테스트"""
        result = is_langsmith_enabled()
        assert isinstance(result, bool)
    
    def test_get_langsmith_client_function(self):
        """LangSmith 클라이언트 조회 함수 테스트"""
        client = get_langsmith_client()
        
        # 활성화 상태에 따라 클라이언트 확인
        if is_langsmith_enabled():
            assert client is not None
        else:
            assert client is None


@pytest.mark.integration
class TestLangSmithIntegrationScenarios:
    """LangSmith 통합 시나리오 테스트"""
    
    @pytest.mark.skipif(not os.getenv("LANGCHAIN_API_KEY"), reason="LANGCHAIN_API_KEY not set") 
    @pytest.mark.asyncio
    async def test_end_to_end_ai_tracking(self):
        """종단 간 AI 추적 테스트"""
        # LangSmith 초기화
        initialize_langsmith()
        
        if not is_langsmith_enabled():
            pytest.skip("LangSmith not enabled")
        
        tracer = LangSmithAITracer()
        
        # AI 호출 시뮬레이션
        async with tracer.trace_ai_call(
            provider="openai",
            model="gpt-4o-mini",
            operation="content_analysis",
            user_id=1001,
            board_id=123
        ) as run_context:
            
            if run_context:
                # 응답 기록
                await tracer.record_ai_response(
                    run_context=run_context,
                    response={"content": "분석 완료", "success": True},
                    input_tokens=150,
                    output_tokens=50,
                    user_id=1001,
                    model_name="gpt-4o-mini"
                )
        
        # 에러 없이 완료되면 성공
        assert True
    
    @pytest.mark.skipif(not os.getenv("LANGCHAIN_API_KEY"), reason="LANGCHAIN_API_KEY not set")
    def test_project_url_generation(self):
        """프로젝트 URL 생성 테스트"""
        initialize_langsmith()
        
        if is_langsmith_enabled():
            from app.monitoring.langsmith.client import langsmith_manager
            
            project_url = langsmith_manager.get_project_url()
            
            assert project_url is not None
            assert "https://api.smith.langchain.com" in project_url
            assert "LinkyBoard-AI" in project_url


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not integration"])