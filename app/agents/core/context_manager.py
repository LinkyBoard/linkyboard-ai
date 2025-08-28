"""
Agent Context Manager - 에이전트 실행 컨텍스트 관리

에이전트 실행에 필요한 컨텍스트 정보를 관리하고 공유합니다.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.database import AsyncSessionLocal
from ..schemas import AgentContext, UserModelPreferences

logger = get_logger(__name__)


class AgentContextManager:
    """에이전트 컨텍스트 관리자"""
    
    def __init__(self):
        self.active_contexts: Dict[str, AgentContext] = {}
        self.context_data: Dict[str, Dict[str, Any]] = {}
        self.context_locks: Dict[str, asyncio.Lock] = {}
        
    async def create_context(
        self,
        user_id: int,
        task_type: str,
        board_id: Optional[int] = None,
        complexity: int = 1,
        user_preferences: Optional[UserModelPreferences] = None,
        reference_materials: List[str] = None,
        custom_session_id: Optional[str] = None
    ) -> AgentContext:
        """
        새로운 에이전트 실행 컨텍스트 생성
        
        Args:
            user_id: 사용자 ID
            task_type: 작업 유형
            board_id: 보드 ID (선택사항)
            complexity: 작업 복잡도 (1-5)
            user_preferences: 사용자 모델 선호도
            reference_materials: 레퍼런스 자료 목록
            custom_session_id: 커스텀 세션 ID (선택사항)
            
        Returns:
            생성된 에이전트 컨텍스트
        """
        session_id = custom_session_id or str(uuid4())
        
        # 기본 사용자 선호도 설정
        if not user_preferences:
            user_preferences = UserModelPreferences(
                user_id=user_id,
                quality_preference="balanced",
                cost_sensitivity="medium"
            )
        
        context = AgentContext(
            user_id=user_id,
            board_id=board_id,
            session_id=session_id,
            task_type=task_type,
            complexity=max(1, min(5, complexity)),
            user_model_preferences=user_preferences,
            reference_materials=reference_materials or []
        )
        
        # 컨텍스트 등록
        self.active_contexts[session_id] = context
        self.context_data[session_id] = {
            'created_at': datetime.now(),
            'shared_data': {},
            'execution_history': [],
            'metrics': {
                'total_agents_executed': 0,
                'total_wtu_consumed': 0.0,
                'total_execution_time_ms': 0
            }
        }
        self.context_locks[session_id] = asyncio.Lock()
        
        logger.info(f"Created agent context {session_id} for user {user_id}, task: {task_type}")
        
        return context
    
    async def get_context(self, session_id: str) -> Optional[AgentContext]:
        """컨텍스트 조회"""
        return self.active_contexts.get(session_id)
    
    async def update_context(
        self,
        session_id: str,
        **updates
    ) -> bool:
        """
        컨텍스트 정보 업데이트
        
        Args:
            session_id: 세션 ID
            **updates: 업데이트할 필드들
            
        Returns:
            업데이트 성공 여부
        """
        if session_id not in self.active_contexts:
            logger.warning(f"Context {session_id} not found for update")
            return False
            
        try:
            async with self.context_locks[session_id]:
                context = self.active_contexts[session_id]
                
                # 허용된 필드만 업데이트
                updatable_fields = {
                    'complexity', 'reference_materials', 'user_model_preferences'
                }
                
                for field, value in updates.items():
                    if field in updatable_fields and hasattr(context, field):
                        setattr(context, field, value)
                        logger.debug(f"Updated context {session_id} field {field}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to update context {session_id}: {e}")
            return False
    
    async def share_data(
        self,
        session_id: str,
        key: str,
        value: Any
    ) -> bool:
        """
        컨텍스트 간 데이터 공유
        
        Args:
            session_id: 세션 ID
            key: 데이터 키
            value: 데이터 값
            
        Returns:
            공유 성공 여부
        """
        if session_id not in self.context_data:
            logger.warning(f"Context {session_id} not found for data sharing")
            return False
            
        try:
            async with self.context_locks[session_id]:
                self.context_data[session_id]['shared_data'][key] = {
                    'value': value,
                    'timestamp': datetime.now(),
                    'type': type(value).__name__
                }
                logger.debug(f"Shared data {key} in context {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to share data in context {session_id}: {e}")
            return False
    
    async def get_shared_data(
        self,
        session_id: str,
        key: str,
        default: Any = None
    ) -> Any:
        """공유된 데이터 조회"""
        if session_id not in self.context_data:
            return default
            
        try:
            shared_data = self.context_data[session_id]['shared_data']
            if key in shared_data:
                return shared_data[key]['value']
            return default
            
        except Exception as e:
            logger.error(f"Failed to get shared data from context {session_id}: {e}")
            return default
    
    async def record_agent_execution(
        self,
        session_id: str,
        agent_name: str,
        execution_time_ms: int,
        wtu_consumed: float,
        success: bool,
        result_summary: str = ""
    ) -> bool:
        """
        에이전트 실행 기록 저장
        
        Args:
            session_id: 세션 ID
            agent_name: 에이전트 이름
            execution_time_ms: 실행 시간 (밀리초)
            wtu_consumed: WTU 소비량
            success: 성공 여부
            result_summary: 결과 요약
            
        Returns:
            기록 성공 여부
        """
        if session_id not in self.context_data:
            return False
            
        try:
            async with self.context_locks[session_id]:
                execution_record = {
                    'agent_name': agent_name,
                    'timestamp': datetime.now(),
                    'execution_time_ms': execution_time_ms,
                    'wtu_consumed': wtu_consumed,
                    'success': success,
                    'result_summary': result_summary
                }
                
                self.context_data[session_id]['execution_history'].append(execution_record)
                
                # 메트릭 업데이트
                metrics = self.context_data[session_id]['metrics']
                metrics['total_agents_executed'] += 1
                metrics['total_wtu_consumed'] += wtu_consumed
                metrics['total_execution_time_ms'] += execution_time_ms
                
                logger.debug(f"Recorded execution for agent {agent_name} in context {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to record agent execution: {e}")
            return False
    
    async def get_context_metrics(self, session_id: str) -> Dict[str, Any]:
        """컨텍스트 메트릭 조회"""
        if session_id not in self.context_data:
            return {}
            
        try:
            data = self.context_data[session_id]
            metrics = data['metrics'].copy()
            
            # 추가 통계 계산
            execution_history = data['execution_history']
            if execution_history:
                successful_executions = sum(1 for exec in execution_history if exec['success'])
                metrics['success_rate'] = successful_executions / len(execution_history)
                metrics['avg_execution_time_ms'] = metrics['total_execution_time_ms'] / len(execution_history)
                metrics['avg_wtu_per_agent'] = metrics['total_wtu_consumed'] / len(execution_history)
            else:
                metrics['success_rate'] = 0.0
                metrics['avg_execution_time_ms'] = 0
                metrics['avg_wtu_per_agent'] = 0.0
                
            metrics['agents_executed'] = [exec['agent_name'] for exec in execution_history]
            metrics['context_age_seconds'] = (datetime.now() - data['created_at']).total_seconds()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get context metrics: {e}")
            return {}
    
    @asynccontextmanager
    async def managed_context(
        self,
        user_id: int,
        task_type: str,
        **context_kwargs
    ):
        """
        관리되는 컨텍스트 생성 (자동 정리)
        
        사용 예:
        async with context_manager.managed_context(user_id=1, task_type="analysis") as context:
            # 에이전트 실행
            pass
        """
        context = await self.create_context(
            user_id=user_id,
            task_type=task_type,
            **context_kwargs
        )
        
        try:
            yield context
        finally:
            await self.cleanup_context(context.session_id)
    
    async def cleanup_context(self, session_id: str) -> bool:
        """
        컨텍스트 정리
        
        Args:
            session_id: 세션 ID
            
        Returns:
            정리 성공 여부
        """
        try:
            # 실행 기록 로그
            if session_id in self.context_data:
                metrics = await self.get_context_metrics(session_id)
                logger.info(
                    f"Cleaning up context {session_id}: "
                    f"agents={metrics.get('total_agents_executed', 0)}, "
                    f"wtu={metrics.get('total_wtu_consumed', 0):.3f}, "
                    f"success_rate={metrics.get('success_rate', 0):.2f}"
                )
            
            # 컨텍스트 데이터 제거
            self.active_contexts.pop(session_id, None)
            self.context_data.pop(session_id, None)
            self.context_locks.pop(session_id, None)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup context {session_id}: {e}")
            return False
    
    async def list_active_contexts(self) -> List[Dict[str, Any]]:
        """활성 컨텍스트 목록 조회"""
        contexts = []
        
        for session_id, context in self.active_contexts.items():
            context_info = {
                'session_id': session_id,
                'user_id': context.user_id,
                'task_type': context.task_type,
                'board_id': context.board_id,
                'complexity': context.complexity,
                'created_at': self.context_data.get(session_id, {}).get('created_at'),
                'metrics': await self.get_context_metrics(session_id)
            }
            contexts.append(context_info)
        
        return contexts
    
    async def cleanup_expired_contexts(self, max_age_hours: int = 24) -> int:
        """
        만료된 컨텍스트 정리
        
        Args:
            max_age_hours: 최대 보존 시간 (시간)
            
        Returns:
            정리된 컨텍스트 수
        """
        cleaned_count = 0
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        expired_sessions = []
        for session_id, data in self.context_data.items():
            if data.get('created_at', datetime.now()) < cutoff_time:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            if await self.cleanup_context(session_id):
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired contexts")
        
        return cleaned_count


# 글로벌 컨텍스트 매니저 인스턴스
context_manager = AgentContextManager()