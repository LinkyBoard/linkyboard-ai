"""
Validator Agent - 검증 전문 에이전트

다른 에이전트의 결과를 검증하고 신뢰도를 평가합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.logging import get_logger
from app.ai.providers.router import ai_router
from ..core.base_agent import AIAgent
from ..schemas import AgentContext, TrustScore

logger = get_logger(__name__)


class ValidatorAgent(AIAgent):
    """검증 에이전트"""
    
    def __init__(self):
        super().__init__(
            agent_name="ValidatorAgent",
            default_model="gpt-4o"  # 검증은 고성능 모델 사용
        )
        self.validation_types = [
            "factual_accuracy",
            "logical_consistency",
            "completeness_check",
            "bias_detection",
            "quality_assessment"
        ]
    
    def get_agent_type(self) -> str:
        return "validator"
    
    def get_capabilities(self) -> List[str]:
        return [
            "사실 정확성 검증",
            "논리적 일관성 확인", 
            "완성도 평가",
            "편향 탐지",
            "품질 평가",
            "신뢰도 점수 계산",
            "레퍼런스 기반 검증"
        ]
    
    async def validate_input(self, input_data: Dict[str, Any], context: AgentContext) -> bool:
        """입력 데이터 유효성 검증"""
        try:
            # 검증할 결과가 있는지 확인
            if not input_data.get('agent_result') and not input_data.get('content_to_validate'):
                logger.warning("No result or content provided for validation")
                return False
            
            # 검증 타입 확인
            validation_type = input_data.get('validation_type', 'quality_assessment')
            if validation_type not in self.validation_types:
                logger.warning(f"Invalid validation type: {validation_type}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Validator agent input validation failed: {e}")
            return False
    
    async def execute_ai_task(
        self,
        input_data: Dict[str, Any],
        model_name: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """검증 AI 작업 실행"""
        try:
            # TODO: 실제 검증 로직 구현
            # 현재는 플레이스홀더 응답 반환
            
            agent_result = input_data.get('agent_result', input_data.get('content_to_validate', ''))
            validation_type = input_data.get('validation_type', 'quality_assessment')
            
            logger.info(f"Performing {validation_type} validation with {model_name}")
            
            # 임시 검증 결과
            trust_score = TrustScore(
                semantic_similarity=0.85,
                factual_consistency=0.90,
                completeness=0.80,
                overall_trust=0.85,
                reference_coverage=0.75,
                confidence_interval=(0.80, 0.90),
                validation_details={
                    'validation_type': validation_type,
                    'validated_at': datetime.now().isoformat(),
                    'validator_model': model_name
                }
            )
            
            validation_result = {
                'trust_score': trust_score.dict(),
                'validation_passed': True,
                'issues_found': [],
                'recommendations': [
                    "Content quality is acceptable",
                    "Minor improvements possible in completeness"
                ],
                'confidence_level': 'high'
            }
            
            return {
                'content': validation_result,
                'metadata': {
                    'validation_type': validation_type,
                    'agent_name': self.agent_name,
                    'model_selection_reason': 'validation_accuracy_priority'
                },
                'usage': {'input_tokens': 200, 'output_tokens': 100}
            }
            
        except Exception as e:
            logger.error(f"Validation execution failed: {e}")
            raise