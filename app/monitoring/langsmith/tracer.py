"""
LangSmith AI 호출 추적 래퍼

기존 AI Provider와 통합하여 모든 AI 호출을 LangSmith로 추적합니다.
WTU 계산과 연동하여 비용 및 성능 모니터링을 제공합니다.
"""

from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
import asyncio
import time
from functools import wraps
from contextlib import asynccontextmanager

from langsmith import traceable
from langsmith.run_helpers import tracing_context
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from app.core.logging import get_logger
from app.metrics import calculate_llm_wtu, record_llm_usage
from .client import langsmith_manager, is_langsmith_enabled

logger = get_logger(__name__)


class LangSmithAITracer:
    """LangSmith AI 호출 추적기"""
    
    def __init__(self):
        self.active_traces: Dict[str, Any] = {}
    
    @asynccontextmanager
    async def trace_ai_call(self,
                          provider: str,
                          model: str,
                          operation: str,
                          user_id: Optional[int] = None,
                          board_id: Optional[int] = None,
                          **metadata):
        """
        AI 호출 추적 컨텍스트 매니저
        
        Args:
            provider: AI 공급자 (openai, claude, google)
            model: 모델 이름
            operation: 작업 타입 (chat_completion, embedding, etc)
            user_id: 사용자 ID
            board_id: 보드 ID
            **metadata: 추가 메타데이터
        """
        if not is_langsmith_enabled():
            yield None
            return
        
        trace_name = f"{provider}.{operation}"
        start_time = time.time()
        
        trace_inputs = {
            "provider": provider,
            "model": model,
            "operation": operation,
            "user_id": user_id,
            "board_id": board_id,
            **metadata
        }
        
        extra_data = {
            "provider": provider,
            "model": model,
            "operation": operation,
            "user_id": str(user_id) if user_id else None,
            "board_id": str(board_id) if board_id else None,
            "timestamp": datetime.now().isoformat(),
            **metadata
        }
        
        try:
            with langsmith_manager.trace_context(
                run_name=trace_name,
                run_type="llm",
                inputs=trace_inputs,
                extra=extra_data
            ) as run_context:
                
                # 추적 정보 저장
                trace_id = str(id(run_context)) if run_context else None
                if trace_id:
                    self.active_traces[trace_id] = {
                        "start_time": start_time,
                        "provider": provider,
                        "model": model,
                        "operation": operation,
                        "user_id": user_id,
                        "board_id": board_id
                    }
                
                try:
                    yield run_context
                except Exception as e:
                    # 에러 기록
                    if run_context:
                        run_context.end(error=str(e))
                    raise
                finally:
                    # 추적 정보 정리
                    if trace_id and trace_id in self.active_traces:
                        del self.active_traces[trace_id]
                        
        except Exception as e:
            logger.error(f"Error in LangSmith trace context: {e}")
            yield None
    
    async def record_ai_response(self,
                               run_context: Any,
                               response: Dict[str, Any],
                               input_tokens: int = 0,
                               output_tokens: int = 0,
                               embed_tokens: int = 0,
                               user_id: Optional[int] = None,
                               model_name: Optional[str] = None,
                               board_id: Optional[int] = None,
                               session: Optional[Any] = None):
        """
        AI 응답 및 사용량 기록
        
        Args:
            run_context: LangSmith 실행 컨텍스트
            response: AI 응답 데이터
            input_tokens: 입력 토큰 수
            output_tokens: 출력 토큰 수
            embed_tokens: 임베딩 토큰 수
            user_id: 사용자 ID
            model_name: 모델 이름
            board_id: 보드 ID
            session: 데이터베이스 세션
        """
        try:
            # LangSmith에 응답 기록
            if run_context and is_langsmith_enabled():
                # 토큰 사용량 메타데이터
                token_usage = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "embed_tokens": embed_tokens,
                    "total_tokens": input_tokens + output_tokens + embed_tokens
                }
                
                # WTU 계산
                wtu_consumed = 0.0
                cost_usd = 0.0
                
                if model_name and (input_tokens > 0 or output_tokens > 0):
                    try:
                        wtu_consumed = await calculate_llm_wtu(
                            model_name=model_name,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            session=session
                        )
                        
                        # 실제 비용 계산 (간단한 추정)
                        # 실제로는 model catalog에서 가져와야 함
                        cost_usd = wtu_consumed * 0.0001  # 임시 환율
                        
                    except Exception as e:
                        logger.warning(f"Failed to calculate WTU: {e}")
                
                # 최종 출력 데이터
                outputs = {
                    **response,
                    "usage": token_usage,
                    "wtu_consumed": wtu_consumed,
                    "cost_usd": cost_usd,
                    "execution_time_ms": getattr(run_context, "execution_time_ms", 0)
                }
                
                # LangSmith에 기록
                run_context.end(outputs=outputs)
                
                logger.info(
                    f"LangSmith recorded: model={model_name}, "
                    f"tokens={input_tokens}+{output_tokens}, "
                    f"wtu={wtu_consumed:.3f}, cost=${cost_usd:.4f}"
                )
            
            # 기존 WTU 시스템에도 기록
            if user_id and model_name and (input_tokens > 0 or output_tokens > 0):
                await record_llm_usage(
                    user_id=user_id,
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    board_id=board_id,
                    session=session
                )
                
        except Exception as e:
            logger.error(f"Failed to record AI response: {e}")


def trace_ai_provider_method(operation_type: str):
    """
    AI Provider 메서드 추적 데코레이터
    
    Args:
        operation_type: 작업 타입 (chat_completion, embedding, etc)
    """
    def decorator(func: Callable) -> Callable:
        if not is_langsmith_enabled():
            return func
        
        @wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            provider_name = getattr(self, 'provider_name', 'unknown')
            model_name = kwargs.get('model', 'unknown')
            
            tracer = LangSmithAITracer()
            
            async with tracer.trace_ai_call(
                provider=provider_name,
                model=model_name,
                operation=operation_type,
                user_id=kwargs.get('user_id'),
                board_id=kwargs.get('board_id'),
                function_name=func.__name__,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            ) as run_context:
                
                start_time = time.time()
                result = await func(self, *args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                # 실행 시간 추가
                if run_context:
                    run_context.execution_time_ms = execution_time
                
                # 토큰 사용량 추출
                input_tokens = 0
                output_tokens = 0
                embed_tokens = 0
                
                if hasattr(result, 'input_tokens'):
                    input_tokens = result.input_tokens
                if hasattr(result, 'output_tokens'):
                    output_tokens = result.output_tokens
                if hasattr(result, 'embed_tokens'):
                    embed_tokens = result.embed_tokens
                
                # 응답 기록
                response_data = {
                    "content": getattr(result, 'content', str(result)),
                    "execution_time_ms": execution_time,
                    "success": True
                }
                
                await tracer.record_ai_response(
                    run_context=run_context,
                    response=response_data,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    embed_tokens=embed_tokens,
                    user_id=kwargs.get('user_id'),
                    model_name=model_name,
                    board_id=kwargs.get('board_id'),
                    session=kwargs.get('session')
                )
                
                return result
        
        @wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            # 동기 함수용 래퍼 (필요한 경우)
            return func(self, *args, **kwargs)
        
        # 비동기 함수인지 확인
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def convert_messages_for_langsmith(messages: List[Dict[str, str]]) -> List[BaseMessage]:
    """
    일반 메시지를 LangChain 메시지 형식으로 변환
    
    Args:
        messages: 일반 메시지 리스트 [{"role": "user", "content": "..."}]
        
    Returns:
        LangChain BaseMessage 리스트
    """
    converted_messages = []
    
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        
        if role == "system":
            converted_messages.append(SystemMessage(content=content))
        elif role == "user":
            converted_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            converted_messages.append(AIMessage(content=content))
        else:
            # 기본적으로 user 메시지로 처리
            converted_messages.append(HumanMessage(content=content))
    
    return converted_messages


class LangChainCompatibleResponse:
    """LangChain 호환 응답 클래스"""
    
    def __init__(self, content: str, usage: Dict[str, int] = None):
        self.content = content
        self.usage = usage or {}
        self.input_tokens = self.usage.get("input_tokens", 0)
        self.output_tokens = self.usage.get("output_tokens", 0)
        self.total_tokens = self.usage.get("total_tokens", 0)


# 전역 추적기 인스턴스
ai_tracer = LangSmithAITracer()