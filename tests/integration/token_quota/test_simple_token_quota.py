#!/usr/bin/env python3
"""
토큰 쿼터 시스템 간단한 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from app.core.models import UserTokenQuota


def test_user_token_quota_model():
    """UserTokenQuota 모델 기본 기능 테스트"""
    print("=== UserTokenQuota 모델 테스트 ===")
    
    # 1. 기본 쿼터 생성
    quota = UserTokenQuota(
        user_id=123,
        plan_month=date(2024, 1, 1),
        allocated_quota=10000,
        used_tokens=3000,
        remaining_tokens=7000,
        total_purchased=0
    )
    
    # 2. 속성 테스트
    print(f"사용률: {quota.usage_percentage}")  # 0.3
    print(f"쿼터 초과: {quota.is_quota_exceeded}")  # False
    print(f"5000 토큰 사용 가능: {quota.can_consume(5000)}")  # True
    print(f"8000 토큰 사용 가능: {quota.can_consume(8000)}")  # False
    
    # 3. 토큰 소비 테스트
    print("\n--- 토큰 소비 테스트 ---")
    print(f"소비 전 - 사용됨: {quota.used_tokens}, 남음: {quota.remaining_tokens}")
    
    result = quota.consume_tokens(2000)
    print(f"2000 토큰 소비 결과: {result}")
    print(f"소비 후 - 사용됨: {quota.used_tokens}, 남음: {quota.remaining_tokens}")
    
    # 4. 실패 케이스 테스트
    result = quota.consume_tokens(8000)
    print(f"8000 토큰 소비 시도 결과: {result}")  # False
    print(f"실패 후 - 사용됨: {quota.used_tokens}, 남음: {quota.remaining_tokens}")  # 변경 없음
    
    # 5. 쿼터 추가 테스트
    print("\n--- 쿼터 추가 테스트 ---")
    print(f"추가 전 - 할당량: {quota.allocated_quota}, 구매량: {quota.total_purchased}")
    
    quota.add_quota(5000)
    print(f"5000 토큰 추가 후 - 할당량: {quota.allocated_quota}, 남음: {quota.remaining_tokens}, 구매량: {quota.total_purchased}")
    
    print("\n=== 테스트 완료 ===")


def test_quota_edge_cases():
    """경계 조건 테스트"""
    print("\n=== 경계 조건 테스트 ===")
    
    # 1. 쿼터 초과 상황
    quota = UserTokenQuota(
        user_id=456,
        plan_month=date(2024, 1, 1),
        allocated_quota=1000,
        used_tokens=1000,
        remaining_tokens=0,
        total_purchased=0
    )
    
    print(f"쿼터 초과 상황 - 사용률: {quota.usage_percentage}, 초과: {quota.is_quota_exceeded}")
    print(f"1 토큰도 사용 불가: {quota.can_consume(1)}")
    
    # 2. 빈 쿼터
    empty_quota = UserTokenQuota(
        user_id=789,
        plan_month=date(2024, 1, 1),
        allocated_quota=0,
        used_tokens=0,
        remaining_tokens=0,
        total_purchased=0
    )
    
    print(f"빈 쿼터 - 사용률: {empty_quota.usage_percentage}, 초과: {empty_quota.is_quota_exceeded}")
    
    print("=== 경계 조건 테스트 완료 ===")


if __name__ == "__main__":
    try:
        test_user_token_quota_model()
        test_quota_edge_cases()
        print("\n✅ 모든 테스트가 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)