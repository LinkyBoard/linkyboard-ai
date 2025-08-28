"""
Agent Coordinator - 에이전트 조정 및 워크플로우 관리

여러 에이전트의 실행을 조정하고 결과를 통합합니다.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from uuid import uuid4
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from .base_agent import AIAgent, AgentResponse
from ..schemas import AgentContext, UserModelPreferences

logger = get_logger(__name__)


class CoordinatedResponse:
    """조정된 에이전트 응답"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time = datetime.now()
        self.agent_responses: List[Tuple[str, AgentResponse]] = []
        self.final_content: Any = None
        self.metadata: Dict[str, Any] = {}
        self.total_wtu_consumed = 0.0
        self.total_cost_usd = 0.0
        self.total_execution_time_ms = 0
        self.success = True
        self.error_messages: List[str] = []
    
    def add_agent_response(self, agent_name: str, response: AgentResponse):
        """에이전트 응답 추가"""
        self.agent_responses.append((agent_name, response))
        self.total_wtu_consumed += response.wtu_consumed
        self.total_cost_usd += response.cost_usd
        self.total_execution_time_ms += response.execution_time_ms
        
        if not response.success:
            self.success = False
            if response.error_message:
                self.error_messages.append(f"{agent_name}: {response.error_message}")
    
    def finalize(self, final_content: Any, metadata: Dict[str, Any] = None):
        """최종 응답 완료"""
        self.final_content = final_content
        self.metadata.update(metadata or {})
        self.metadata.update({
            'session_id': self.session_id,
            'total_agents': len(self.agent_responses),
            'execution_summary': {
                'total_wtu_consumed': self.total_wtu_consumed,
                'total_cost_usd': self.total_cost_usd,
                'total_execution_time_ms': self.total_execution_time_ms,
                'success_rate': sum(1 for _, r in self.agent_responses if r.success) / len(self.agent_responses) if self.agent_responses else 0
            }
        })
    
    def to_agent_response(self) -> AgentResponse:
        """표준 AgentResponse로 변환"""
        total_tokens = sum(
            response.tokens_used.get('total', 0) 
            for _, response in self.agent_responses
        )
        
        return AgentResponse(
            content=self.final_content,
            metadata=self.metadata,
            model_used=f"multi_agent_coordination({len(self.agent_responses)})",
            tokens_used={'total': total_tokens},
            wtu_consumed=self.total_wtu_consumed,
            cost_usd=self.total_cost_usd,
            execution_time_ms=self.total_execution_time_ms,
            success=self.success,
            error_message="; ".join(self.error_messages) if self.error_messages else None
        )


class AgentCoordinator:
    """에이전트 조정자"""
    
    def __init__(self):
        self.registered_agents: Dict[str, AIAgent] = {}
        self.execution_count = 0
    
    def register_agent(self, agent: AIAgent):
        """에이전트 등록"""
        agent_type = agent.get_agent_type()
        self.registered_agents[agent_type] = agent
        logger.info(f"Registered agent: {agent_type} ({agent.agent_name})")
    
    def get_available_agents(self) -> List[str]:
        """사용 가능한 에이전트 목록 반환"""
        return list(self.registered_agents.keys())
    
    async def execute_agent_chain(
        self,
        agent_chain: List[str],
        initial_input: Dict[str, Any],
        context: AgentContext,
        session: Optional[AsyncSession] = None
    ) -> CoordinatedResponse:
        """
        에이전트 체인 순차 실행
        
        Args:
            agent_chain: 실행할 에이전트 타입 목록 (순서대로)
            initial_input: 초기 입력 데이터
            context: 실행 컨텍스트
            session: 데이터베이스 세션
            
        Returns:
            조정된 응답 결과
        """
        session_id = str(uuid4())
        coordinated_response = CoordinatedResponse(session_id)
        
        logger.info(f"Starting agent chain execution: {agent_chain} (session: {session_id})")
        
        try:
            current_input = initial_input.copy()
            
            for agent_type in agent_chain:
                if agent_type not in self.registered_agents:
                    error_msg = f"Agent type '{agent_type}' not registered"
                    logger.error(error_msg)
                    coordinated_response.error_messages.append(error_msg)
                    coordinated_response.success = False
                    continue
                
                agent = self.registered_agents[agent_type]
                
                logger.info(f"Executing agent: {agent_type}")
                
                # 에이전트 실행
                response = await agent.process_with_wtu(
                    input_data=current_input,
                    context=context,
                    session=session
                )
                
                coordinated_response.add_agent_response(agent.agent_name, response)
                
                if response.success:
                    # 다음 에이전트를 위해 출력을 입력으로 전달
                    if isinstance(response.content, dict):
                        current_input.update(response.content)
                    else:
                        current_input['previous_output'] = response.content
                        
                    logger.info(
                        f"Agent {agent_type} completed successfully: "
                        f"WTU={response.wtu_consumed:.3f}"
                    )
                else:
                    logger.warning(
                        f"Agent {agent_type} failed: {response.error_message}"
                    )
            
            # 최종 결과 설정
            if coordinated_response.agent_responses:
                last_response = coordinated_response.agent_responses[-1][1]
                coordinated_response.finalize(
                    final_content=last_response.content,
                    metadata={
                        'chain_execution': True,
                        'agent_chain': agent_chain,
                        'context': context.dict()
                    }
                )
            
            self.execution_count += 1
            
            logger.info(
                f"Agent chain completed: success={coordinated_response.success}, "
                f"total_wtu={coordinated_response.total_wtu_consumed:.3f}"
            )
            
            return coordinated_response
            
        except Exception as e:
            error_msg = f"Agent chain execution failed: {str(e)}"
            logger.error(error_msg)
            coordinated_response.error_messages.append(error_msg)
            coordinated_response.success = False
            coordinated_response.finalize(
                final_content=f"에이전트 체인 실행 중 오류 발생: {error_msg}"
            )
            return coordinated_response
    
    async def execute_parallel_agents(
        self,
        agent_tasks: List[Tuple[str, Dict[str, Any]]],  # (agent_type, input_data)
        context: AgentContext,
        session: Optional[AsyncSession] = None
    ) -> CoordinatedResponse:
        """
        에이전트 병렬 실행
        
        Args:
            agent_tasks: (에이전트 타입, 입력 데이터) 튜플 리스트
            context: 실행 컨텍스트
            session: 데이터베이스 세션
            
        Returns:
            병렬 실행 결과
        """
        session_id = str(uuid4())
        coordinated_response = CoordinatedResponse(session_id)
        
        logger.info(f"Starting parallel agent execution: {len(agent_tasks)} agents (session: {session_id})")
        
        try:
            # 병렬 실행을 위한 태스크 생성
            tasks = []
            for agent_type, input_data in agent_tasks:
                if agent_type not in self.registered_agents:
                    error_msg = f"Agent type '{agent_type}' not registered"
                    logger.error(error_msg)
                    coordinated_response.error_messages.append(error_msg)
                    continue
                
                agent = self.registered_agents[agent_type]
                task = asyncio.create_task(
                    agent.process_with_wtu(
                        input_data=input_data,
                        context=context,
                        session=session
                    )
                )
                tasks.append((agent.agent_name, task))
            
            # 병렬 실행 및 결과 수집
            results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            parallel_results = {}
            for i, ((agent_name, _), result) in enumerate(zip(tasks, results)):
                if isinstance(result, Exception):
                    error_response = AgentResponse(
                        content=f"에이전트 실행 중 예외 발생: {str(result)}",
                        success=False,
                        error_message=str(result)
                    )
                    coordinated_response.add_agent_response(agent_name, error_response)
                else:
                    coordinated_response.add_agent_response(agent_name, result)
                    parallel_results[agent_name] = result.content
            
            # 병렬 결과 통합
            coordinated_response.finalize(
                final_content=parallel_results,
                metadata={
                    'parallel_execution': True,
                    'agent_count': len(agent_tasks),
                    'context': context.dict()
                }
            )
            
            logger.info(
                f"Parallel execution completed: success={coordinated_response.success}, "
                f"total_wtu={coordinated_response.total_wtu_consumed:.3f}"
            )
            
            return coordinated_response
            
        except Exception as e:
            error_msg = f"Parallel agent execution failed: {str(e)}"
            logger.error(error_msg)
            coordinated_response.error_messages.append(error_msg)
            coordinated_response.success = False
            coordinated_response.finalize(
                final_content=f"병렬 에이전트 실행 중 오류 발생: {error_msg}"
            )
            return coordinated_response
    
    async def build_optimal_agent_chain(
        self,
        task_type: str,
        complexity: int,
        user_preferences: UserModelPreferences
    ) -> List[str]:
        """
        작업 유형과 복잡도에 따른 최적 에이전트 체인 구성
        
        Args:
            task_type: 작업 유형 (board_analysis, clipper, summary 등)
            complexity: 작업 복잡도 (1-5)
            user_preferences: 사용자 선호도
            
        Returns:
            최적화된 에이전트 체인
        """
        try:
            agent_chain = []
            
            if task_type == "board_analysis":
                agent_chain = ["content_analysis", "summary_generation"]
                if complexity >= 3:
                    agent_chain.append("validator")
                if user_preferences.quality_preference == "quality":
                    agent_chain.insert(-1, "qa_enhancement")
            
            elif task_type == "clipper":
                agent_chain = ["content_extraction", "summary_generation", "category_classification"]
                if complexity >= 4:
                    agent_chain.append("validator")
            
            elif task_type == "summary":
                agent_chain = ["summary_generation"]
                if complexity >= 3:
                    agent_chain.append("validator")
            
            else:
                # 기본 체인
                agent_chain = ["content_analysis", "summary_generation"]
            
            # 등록되지 않은 에이전트 필터링
            available_chain = [
                agent_type for agent_type in agent_chain 
                if agent_type in self.registered_agents
            ]
            
            logger.info(f"Built agent chain for {task_type}: {available_chain}")
            return available_chain
            
        except Exception as e:
            logger.error(f"Failed to build agent chain: {e}")
            return ["content_analysis"]  # 기본 폴백
    
    def get_coordinator_stats(self) -> Dict[str, Any]:
        """조정자 통계 반환"""
        return {
            'registered_agents': list(self.registered_agents.keys()),
            'agent_count': len(self.registered_agents),
            'execution_count': self.execution_count,
            'agent_stats': {
                agent_type: agent.get_stats() 
                for agent_type, agent in self.registered_agents.items()
            }
        }


# 글로벌 조정자 인스턴스
agent_coordinator = AgentCoordinator()