"""
Summary Generation Agent - 요약 생성 전문 에이전트

콘텐츠를 분석하여 다양한 형태의 요약을 생성합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.logging import get_logger
from app.ai.providers.router import ai_router
from ..core.base_agent import AIAgent
from ..schemas import AgentContext

logger = get_logger(__name__)


class SummaryGenerationAgent(AIAgent):
    """요약 생성 에이전트"""
    
    def __init__(self):
        super().__init__(
            agent_name="SummaryGenerationAgent",
            default_model="gpt-4o-mini"
        )
        self.summary_types = [
            "executive_summary",
            "bullet_points", 
            "abstract",
            "key_insights",
            "structured_summary"
        ]
    
    def get_agent_type(self) -> str:
        return "summary_generation"
    
    def get_capabilities(self) -> List[str]:
        return [
            "임원 요약 생성",
            "불릿 포인트 요약",
            "학술 초록 스타일 요약", 
            "핵심 인사이트 추출",
            "구조화된 요약 생성",
            "다국어 요약 지원",
            "요약 길이 조절"
        ]
    
    async def validate_input(self, input_data: Dict[str, Any], context: AgentContext) -> bool:
        """입력 데이터 유효성 검증"""
        try:
            # 요약할 콘텐츠가 있는지 확인
            if not input_data.get('content') and not input_data.get('analysis_result'):
                logger.warning("No content or analysis result provided for summary")
                return False
            
            # 요약 타입 유효성 확인
            summary_type = input_data.get('summary_type', 'executive_summary')
            if summary_type not in self.summary_types:
                logger.warning(f"Invalid summary type: {summary_type}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Summary agent input validation failed: {e}")
            return False
    
    async def execute_ai_task(
        self,
        input_data: Dict[str, Any],
        model_name: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """요약 생성 AI 작업 실행"""
        try:
            # TODO: 실제 요약 생성 로직 구현
            # 현재는 플레이스홀더 응답 반환
            
            content = input_data.get('content', input_data.get('analysis_result', ''))
            summary_type = input_data.get('summary_type', 'executive_summary')
            
            logger.info(f"Generating {summary_type} summary with {model_name}")
            
            # 임시 응답
            summary_result = {
                'summary': f"Generated {summary_type} summary for the given content",
                'summary_type': summary_type,
                'key_points': [
                    "Key point 1 extracted from content",
                    "Key point 2 identified in analysis", 
                    "Key point 3 derived from structure"
                ],
                'word_count': 150,
                'compression_ratio': 0.1
            }
            
            return {
                'content': summary_result,
                'metadata': {
                    'summary_type': summary_type,
                    'original_content_length': len(str(content)),
                    'agent_name': self.agent_name,
                    'model_selection_reason': 'summary_optimization'
                },
                'usage': {'input_tokens': 100, 'output_tokens': 150}
            }
            
        except Exception as e:
            logger.error(f"Summary generation execution failed: {e}")
            raise