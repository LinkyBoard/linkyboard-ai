"""
Metrics 모듈 - WTU 계측 및 사용량 관리

이 모듈은 다음 기능들을 제공합니다:
- WTU (Work Time Unit) 계산
- 모델별 가격 정보 관리  
- 사용량 기록 및 조회
- 토큰 카운팅

사용 예시:
    from app.metrics import record_usage, calculate_wtu
    from app.metrics.pricing_service import pricing_service
"""

from .wtu_calculator import calculate_wtu, calculate_wtu_simple, calculate_embedding_wtu, calculate_llm_wtu
from .usage_recorder import (
    record_usage, 
    record_embedding_usage, 
    record_llm_usage,
    get_monthly_usage, 
    get_total_monthly_wtu,
    get_usage_by_model
)
from .token_counter import count_tokens, count_tokens_batch, estimate_embedding_tokens
from .pricing_service import pricing_service

__all__ = [
    # WTU 계산
    "calculate_wtu",
    "calculate_wtu_simple", 
    "calculate_embedding_wtu",
    "calculate_llm_wtu",
    
    # 사용량 기록
    "record_usage",
    "record_embedding_usage",
    "record_llm_usage",
    
    # 사용량 조회
    "get_monthly_usage",
    "get_total_monthly_wtu", 
    "get_usage_by_model",
    
    # 토큰 카운팅
    "count_tokens",
    "count_tokens_batch",
    "estimate_embedding_tokens",
    
    # 가격 서비스
    "pricing_service",
]
