"""
Reference Materials Management - 레퍼런스 자료 관리 시스템

사용자 레퍼런스 자료를 관리하고 AI 응답과의 비교 검증을 수행합니다.
"""

from .reference_manager import ReferenceManager, reference_manager
from .quality_validator import QualityValidator

# 순환 참조 방지를 위해 늦은 초기화
def get_quality_validator() -> QualityValidator:
    """품질 검증기 인스턴스 반환"""
    global _quality_validator_instance
    if '_quality_validator_instance' not in globals():
        _quality_validator_instance = QualityValidator(reference_manager)
    return _quality_validator_instance

__all__ = [
    "ReferenceManager",
    "reference_manager", 
    "QualityValidator",
    "get_quality_validator"
]