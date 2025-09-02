"""
콘텐츠 처리 워크플로우 그래프

웹페이지나 YouTube 콘텐츠를 분석하고 태그, 카테고리를 추출하는 워크플로우입니다.
"""

from typing import Dict, Any, Optional, Literal
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor

from app.core.logging import get_logger
from app.agents.schemas import AgentContext
from app.monitoring.langsmith.client import langsmith_manager

from ..state import AgentState, create_initial_state, finalize_state
from ..nodes.content_analysis_node import ContentAnalysisNode
from ..nodes.tag_extraction_node import TagExtractionNode
from ..nodes.category_classification_node import CategoryClassificationNode
from ..nodes.validation_node import ValidationNode

logger = get_logger(__name__)


class ContentProcessingGraph:
    """콘텐츠 처리 LangGraph 워크플로우"""
    
    def __init__(self):
        self.graph = None
        self.nodes = {
            "content_analysis": ContentAnalysisNode(),
            "tag_extraction": TagExtractionNode(),
            "category_classification": CategoryClassificationNode(),
            "validation": ValidationNode()
        }
        self._build_graph()
    
    def _build_graph(self):
        """그래프 구조 구축"""
        # StateGraph 생성
        workflow = StateGraph(AgentState)
        
        # 노드 추가
        workflow.add_node("content_analysis", self._execute_content_analysis)
        workflow.add_node("tag_extraction", self._execute_tag_extraction)
        workflow.add_node("category_classification", self._execute_category_classification)
        workflow.add_node("validation", self._execute_validation)
        workflow.add_node("finalize", self._finalize_results)
        
        # 엣지 정의 (실행 순서)
        workflow.set_entry_point("content_analysis")
        
        # content_analysis -> 병렬 실행 (tag_extraction, category_classification)
        workflow.add_edge("content_analysis", "tag_extraction")
        workflow.add_edge("content_analysis", "category_classification")
        
        # 조건부 검증 실행
        workflow.add_conditional_edges(
            "tag_extraction",
            self._should_validate,
            {
                True: "validation",
                False: "finalize"
            }
        )
        
        workflow.add_conditional_edges(
            "category_classification", 
            self._should_validate,
            {
                True: "validation",
                False: "finalize"
            }
        )
        
        # validation -> finalize
        workflow.add_edge("validation", "finalize")
        
        # finalize -> END
        workflow.add_edge("finalize", END)
        
        # 그래프 컴파일
        self.graph = workflow.compile()
        
        logger.info("Content processing graph built successfully")
    
    async def _execute_content_analysis(self, state: AgentState) -> Dict[str, Any]:
        """콘텐츠 분석 노드 실행"""
        session = getattr(state, '_session', None)
        return await self.nodes["content_analysis"].execute(state, session)
    
    async def _execute_tag_extraction(self, state: AgentState) -> Dict[str, Any]:
        """태그 추출 노드 실행"""
        # content_analysis가 완료되었는지 확인
        if "content_analysis" not in state["completed_nodes"]:
            return {"errors": ["Content analysis must be completed before tag extraction"]}
        
        session = getattr(state, '_session', None)
        return await self.nodes["tag_extraction"].execute(state, session)
    
    async def _execute_category_classification(self, state: AgentState) -> Dict[str, Any]:
        """카테고리 분류 노드 실행"""
        # content_analysis가 완료되었는지 확인
        if "content_analysis" not in state["completed_nodes"]:
            return {"errors": ["Content analysis must be completed before category classification"]}
        
        session = getattr(state, '_session', None)
        return await self.nodes["category_classification"].execute(state, session)
    
    async def _execute_validation(self, state: AgentState) -> Dict[str, Any]:
        """검증 노드 실행"""
        # 필요한 노드들이 완료되었는지 확인
        required_nodes = ["content_analysis"]
        completed = state["completed_nodes"]
        
        if not all(node in completed for node in required_nodes):
            return {"errors": ["Required nodes must be completed before validation"]}
        
        session = getattr(state, '_session', None)
        return await self.nodes["validation"].execute(state, session)
    
    def _should_validate(self, state: AgentState) -> Literal[True, False]:
        """검증 실행 여부 결정"""
        # 복잡도가 3 이상이거나 사용자가 품질을 중시하는 경우 검증 실행
        should_validate = (
            state.get("should_validate", False) or
            state.get("complexity_level", 0) >= 3 or
            state.get("user_preferences", {}).get("quality_preference") == "quality"
        )
        
        # 두 노드 모두 완료된 경우에만 검증 진행
        completed_nodes = state.get("completed_nodes", [])
        both_completed = ("tag_extraction" in completed_nodes and 
                         "category_classification" in completed_nodes)
        
        return should_validate and both_completed
    
    async def _finalize_results(self, state: AgentState) -> Dict[str, Any]:
        """최종 결과 조합"""
        try:
            # 모든 노드 결과 수집
            results = state.get("results", {})
            
            # 최종 출력 구성
            final_output = {
                "content_analysis": results.get("content_analysis", {}),
                "tag_extraction": results.get("tag_extraction", {}),
                "category_classification": results.get("category_classification", {}),
                "validation": results.get("validation", {})
            }
            
            # 주요 결과 추출
            summary = results.get("content_analysis", {}).get("summary", "")
            tags = results.get("tag_extraction", {}).get("tags", [])
            category = results.get("category_classification", {}).get("category", "")
            
            # 검증 결과가 있으면 포함
            validation_passed = True
            validation_score = 1.0
            if "validation" in results:
                validation_data = results["validation"]
                validation_passed = validation_data.get("validation_passed", True)
                validation_score = validation_data.get("overall_score", 1.0)
            
            # 성공 여부 결정
            success = (len(state.get("errors", [])) == 0 and 
                      bool(summary) and 
                      validation_passed)
            
            final_result = {
                "summary": summary,
                "tags": tags,
                "category": category,
                "validation_passed": validation_passed,
                "validation_score": validation_score,
                "detailed_results": final_output,
                "success": success
            }
            
            return finalize_state(state, final_result, success)
            
        except Exception as e:
            logger.error(f"Failed to finalize results: {e}")
            error_result = {
                "error": str(e),
                "success": False
            }
            return finalize_state(state, error_result, False)
    
    async def process_content(self,
                            user_id: int,
                            input_data: Dict[str, Any],
                            context: AgentContext,
                            session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        콘텐츠 처리 워크플로우 실행
        
        Args:
            user_id: 사용자 ID
            input_data: 입력 데이터
            context: 에이전트 컨텍스트
            session: 데이터베이스 세션
            
        Returns:
            처리 결과
        """
        session_id = str(uuid4())
        
        logger.info(f"Starting content processing workflow: session={session_id}, user={user_id}")
        
        # LangSmith 추적 시작
        with langsmith_manager.trace_context(
            run_name="content_processing_workflow",
            run_type="chain",
            inputs={
                "user_id": user_id,
                "input_data": input_data,
                "context": context.dict(),
                "session_id": session_id
            },
            extra={
                "workflow_type": "content_processing",
                "user_id": str(user_id),
                "session_id": session_id
            }
        ) as run_context:
            
            try:
                # 초기 상태 생성
                initial_state = create_initial_state(
                    user_id=user_id,
                    input_data=input_data,
                    context=context,
                    session_id=session_id
                )
                
                # 세션을 상태에 첨부 (노드에서 사용할 수 있도록)
                initial_state["_session"] = session
                
                # 그래프 실행
                final_state = await self.graph.ainvoke(initial_state)
                
                # 결과 추출
                result = final_state.get("final_output", {})
                success = final_state.get("success", False)
                
                # LangSmith에 결과 기록
                if run_context:
                    run_context.end(outputs={
                        "success": success,
                        "result": result,
                        "total_tokens": final_state.get("total_tokens_used", 0),
                        "total_wtu": final_state.get("total_wtu_consumed", 0),
                        "total_cost": final_state.get("total_cost_usd", 0),
                        "completed_nodes": final_state.get("completed_nodes", []),
                        "errors": final_state.get("errors", [])
                    })
                
                logger.info(
                    f"Content processing completed: success={success}, "
                    f"tokens={final_state.get('total_tokens_used', 0)}, "
                    f"wtu={final_state.get('total_wtu_consumed', 0):.3f}"
                )
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Content processing workflow failed: {error_msg}")
                
                # LangSmith에 에러 기록
                if run_context:
                    run_context.end(error=error_msg)
                
                return {
                    "success": False,
                    "error": error_msg,
                    "summary": "",
                    "tags": [],
                    "category": ""
                }
    
    def get_graph_info(self) -> Dict[str, Any]:
        """그래프 정보 반환"""
        return {
            "graph_type": "content_processing",
            "nodes": list(self.nodes.keys()),
            "node_stats": {name: node.get_stats() for name, node in self.nodes.items()},
            "workflow_description": "콘텐츠 분석 -> 태그 추출 & 카테고리 분류 -> [검증] -> 결과 조합"
        }


# 전역 그래프 인스턴스
content_processing_graph = ContentProcessingGraph()