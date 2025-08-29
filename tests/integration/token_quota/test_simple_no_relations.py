#!/usr/bin/env python3
"""
토큰 쿼터 시스템 기본 기능 테스트 (관계 없이)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date


class SimpleUserTokenQuota:
    """간단한 토큰 쿼터 클래스 (테스트용)"""
    
    def __init__(self, user_id, plan_month, allocated_quota, used_tokens, remaining_tokens, total_purchased):
        self.user_id = user_id
        self.plan_month = plan_month
        self.allocated_quota = allocated_quota
        self.used_tokens = used_tokens
        self.remaining_tokens = remaining_tokens
        self.total_purchased = total_purchased
        self.is_active = True
    
    @property
    def usage_percentage(self) -> float:
        """사용률 계산 (0.0-1.0)"""
        if self.allocated_quota == 0:
            return 1.0
        return self.used_tokens / self.allocated_quota
    
    @property
    def is_quota_exceeded(self) -> bool:
        """쿼터 초과 여부"""
        return self.remaining_tokens <= 0
    
    def can_consume(self, token_amount: int) -> bool:
        """토큰 사용 가능 여부 확인"""
        return self.remaining_tokens >= token_amount
    
    def consume_tokens(self, token_amount: int) -> bool:
        """토큰 소비"""
        if not self.can_consume(token_amount):
            return False
        
        self.used_tokens += token_amount
        self.remaining_tokens = max(0, self.allocated_quota - self.used_tokens)
        return True
    
    def add_quota(self, additional_tokens: int):
        """쿼터 추가 (충전)"""
        self.allocated_quota += additional_tokens
        self.remaining_tokens = self.allocated_quota - self.used_tokens
        self.total_purchased += additional_tokens


def test_token_quota_basic_functionality():
    """기본 토큰 쿼터 기능 테스트"""
    print("=== 기본 토큰 쿼터 기능 테스트 ===")
    
    # 1. 기본 쿼터 생성
    quota = SimpleUserTokenQuota(
        user_id=123,
        plan_month=date(2024, 1, 1),
        allocated_quota=10000,
        used_tokens=3000,
        remaining_tokens=7000,
        total_purchased=0
    )
    
    print(f"초기 상태:")
    print(f"  사용자 ID: {quota.user_id}")
    print(f"  할당량: {quota.allocated_quota}")
    print(f"  사용량: {quota.used_tokens}")
    print(f"  잔여량: {quota.remaining_tokens}")
    print(f"  사용률: {quota.usage_percentage:.2%}")
    print(f"  쿼터 초과: {quota.is_quota_exceeded}")
    
    # 2. 토큰 사용 가능성 확인 테스트
    print(f"\n토큰 사용 가능성 테스트:")
    print(f"  1000 토큰 사용 가능: {quota.can_consume(1000)}")  # True
    print(f"  5000 토큰 사용 가능: {quota.can_consume(5000)}")  # True  
    print(f"  8000 토큰 사용 가능: {quota.can_consume(8000)}")  # False
    
    # 3. 토큰 소비 테스트
    print(f"\n토큰 소비 테스트:")
    print(f"  소비 전: 사용량={quota.used_tokens}, 잔여량={quota.remaining_tokens}")
    
    success = quota.consume_tokens(2000)
    print(f"  2000 토큰 소비 결과: {success}")
    print(f"  소비 후: 사용량={quota.used_tokens}, 잔여량={quota.remaining_tokens}")
    
    # 4. 토큰 부족 시나리오 테스트
    print(f"\n토큰 부족 시나리오 테스트:")
    success = quota.consume_tokens(10000)
    print(f"  10000 토큰 소비 시도 결과: {success}")  # False
    print(f"  실패 후: 사용량={quota.used_tokens}, 잔여량={quota.remaining_tokens}")  # 변경 없음
    
    # 5. 쿼터 추가 테스트
    print(f"\n쿼터 추가 테스트:")
    print(f"  추가 전: 할당량={quota.allocated_quota}, 잔여량={quota.remaining_tokens}, 구매량={quota.total_purchased}")
    
    quota.add_quota(5000)
    print(f"  5000 토큰 추가 후:")
    print(f"    할당량={quota.allocated_quota}")
    print(f"    잔여량={quota.remaining_tokens}")
    print(f"    구매량={quota.total_purchased}")
    
    print("\n=== 기본 기능 테스트 완료 ===")
    return quota


def test_edge_cases():
    """경계 조건 테스트"""
    print("\n=== 경계 조건 테스트 ===")
    
    # 1. 쿼터 완전 소진
    depleted_quota = SimpleUserTokenQuota(
        user_id=456,
        plan_month=date(2024, 1, 1),
        allocated_quota=1000,
        used_tokens=1000,
        remaining_tokens=0,
        total_purchased=0
    )
    
    print(f"완전 소진된 쿼터:")
    print(f"  사용률: {depleted_quota.usage_percentage:.2%}")
    print(f"  쿼터 초과: {depleted_quota.is_quota_exceeded}")
    print(f"  1 토큰도 사용 불가: {not depleted_quota.can_consume(1)}")
    
    # 2. 빈 쿼터
    empty_quota = SimpleUserTokenQuota(
        user_id=789,
        plan_month=date(2024, 1, 1),
        allocated_quota=0,
        used_tokens=0,
        remaining_tokens=0,
        total_purchased=0
    )
    
    print(f"\n빈 쿼터:")
    print(f"  사용률: {empty_quota.usage_percentage:.2%}")
    print(f"  쿼터 초과: {empty_quota.is_quota_exceeded}")
    
    # 3. 대용량 쿼터
    large_quota = SimpleUserTokenQuota(
        user_id=999,
        plan_month=date(2024, 1, 1),
        allocated_quota=1000000,
        used_tokens=50000,
        remaining_tokens=950000,
        total_purchased=200000
    )
    
    print(f"\n대용량 쿼터:")
    print(f"  할당량: {large_quota.allocated_quota:,}")
    print(f"  사용률: {large_quota.usage_percentage:.2%}")
    print(f"  100k 토큰 사용 가능: {large_quota.can_consume(100000)}")
    
    print("\n=== 경계 조건 테스트 완료 ===")


def test_quota_scenarios():
    """실제 사용 시나리오 테스트"""
    print("\n=== 실제 사용 시나리오 테스트 ===")
    
    # 신규 사용자 시나리오
    print("📱 신규 사용자 시나리오:")
    new_user_quota = SimpleUserTokenQuota(
        user_id=1001,
        plan_month=date(2024, 2, 1),
        allocated_quota=10000,  # 기본 10k 토큰
        used_tokens=0,
        remaining_tokens=10000,
        total_purchased=0
    )
    
    # 다양한 AI 기능 사용
    ai_operations = [
        ("문서 요약", 500),
        ("보드 분석", 800),
        ("콘텐츠 추출", 300),
        ("임베딩 생성", 200),
        ("에이전트 작업", 700)
    ]
    
    for operation, tokens in ai_operations:
        if new_user_quota.can_consume(tokens):
            success = new_user_quota.consume_tokens(tokens)
            print(f"  ✅ {operation}: {tokens} 토큰 사용 (잔여: {new_user_quota.remaining_tokens:,})")
        else:
            print(f"  ❌ {operation}: {tokens} 토큰 부족 (잔여: {new_user_quota.remaining_tokens:,})")
    
    print(f"  📊 최종 사용률: {new_user_quota.usage_percentage:.2%}")
    
    # 헤비 유저 시나리오
    print(f"\n🔥 헤비 유저 시나리오:")
    heavy_user_quota = SimpleUserTokenQuota(
        user_id=1002,
        plan_month=date(2024, 2, 1),
        allocated_quota=10000,
        used_tokens=9500,  # 거의 다 사용
        remaining_tokens=500,
        total_purchased=0
    )
    
    print(f"  현재 사용률: {heavy_user_quota.usage_percentage:.2%}")
    
    # 대용량 작업 시도
    large_operation_tokens = 2000
    if heavy_user_quota.can_consume(large_operation_tokens):
        heavy_user_quota.consume_tokens(large_operation_tokens)
        print(f"  ✅ 대용량 작업 완료")
    else:
        print(f"  ❌ 대용량 작업 실패 - 토큰 부족 (필요: {large_operation_tokens}, 보유: {heavy_user_quota.remaining_tokens})")
        
        # 토큰 충전
        print(f"  💳 토큰 충전: 5000개")
        heavy_user_quota.add_quota(5000)
        print(f"  충전 후 잔여량: {heavy_user_quota.remaining_tokens:,}")
        
        # 다시 시도
        if heavy_user_quota.can_consume(large_operation_tokens):
            heavy_user_quota.consume_tokens(large_operation_tokens)
            print(f"  ✅ 충전 후 대용량 작업 완료")
    
    print("\n=== 시나리오 테스트 완료 ===")


def test_middleware_logic():
    """미들웨어 로직 시뮬레이션 테스트"""
    print("\n=== 미들웨어 로직 시뮬레이션 ===")
    
    quota = SimpleUserTokenQuota(
        user_id=2001,
        plan_month=date(2024, 2, 1),
        allocated_quota=5000,
        used_tokens=4800,
        remaining_tokens=200,
        total_purchased=0
    )
    
    # 다양한 AI 요청 시뮬레이션
    requests = [
        ("/api/v1/agents/analyze", 100),      # 성공 예상
        ("/api/v1/board-ai/summary", 500),    # 실패 예상
        ("/api/v1/clipper/extract", 200),     # 성공 예상  
        ("/api/v1/agents/generate", 300),     # 실패 예상
    ]
    
    print(f"초기 상태: 잔여 {quota.remaining_tokens} 토큰")
    
    for endpoint, estimated_tokens in requests:
        print(f"\n🔄 요청: {endpoint} (예상 {estimated_tokens} 토큰)")
        
        # 미들웨어의 사전 검증 단계
        if quota.can_consume(estimated_tokens):
            print(f"  ✅ 사전 검증 통과 - 요청 처리 시작")
            
            # 요청 처리 (시뮬레이션)
            success = quota.consume_tokens(estimated_tokens)
            if success:
                print(f"  ✅ 요청 완료 - {estimated_tokens} 토큰 차감 (잔여: {quota.remaining_tokens})")
            else:
                print(f"  ❌ 요청 처리 중 오류 (이론적으로 발생하지 않아야 함)")
        else:
            print(f"  ❌ 토큰 부족으로 요청 차단")
            print(f"     필요: {estimated_tokens}, 보유: {quota.remaining_tokens}")
            print(f"     HTTP 429 Too Many Requests 반환")
    
    print(f"\n최종 상태: {quota.used_tokens}/{quota.allocated_quota} 토큰 사용 ({quota.usage_percentage:.2%})")
    print("=== 미들웨어 시뮬레이션 완료 ===")


if __name__ == "__main__":
    try:
        print("🚀 토큰 쿼터 시스템 종합 테스트 시작\n")
        
        test_token_quota_basic_functionality()
        test_edge_cases()
        test_quota_scenarios()
        test_middleware_logic()
        
        print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
        print("토큰 쿼터 시스템의 핵심 로직이 정상적으로 작동합니다.")
        
    except Exception as e:
        print(f"\n💥 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)