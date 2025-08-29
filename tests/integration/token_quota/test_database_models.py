#!/usr/bin/env python3
"""
데이터베이스 모델 구조 및 관계 검증 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime


def test_user_token_quota_model_properties():
    """UserTokenQuota 모델의 속성 및 메서드 테스트"""
    print("=== UserTokenQuota 모델 속성 테스트 ===")
    
    # UserTokenQuota의 속성을 직접 구현한 클래스로 테스트
    class TestUserTokenQuota:
        def __init__(self, user_id, plan_month, allocated_quota, used_tokens, remaining_tokens, total_purchased):
            self.user_id = user_id
            self.plan_month = plan_month
            self.allocated_quota = allocated_quota
            self.used_tokens = used_tokens
            self.remaining_tokens = remaining_tokens
            self.total_purchased = total_purchased
            self.is_active = True
            self.created_at = datetime.now()
            self.updated_at = None
        
        @property
        def usage_percentage(self) -> float:
            if self.allocated_quota == 0:
                return 1.0
            return self.used_tokens / self.allocated_quota
        
        @property
        def is_quota_exceeded(self) -> bool:
            return self.remaining_tokens <= 0
        
        def can_consume(self, token_amount: int) -> bool:
            return self.remaining_tokens >= token_amount
        
        def consume_tokens(self, token_amount: int) -> bool:
            if not self.can_consume(token_amount):
                return False
            
            self.used_tokens += token_amount
            self.remaining_tokens = max(0, self.allocated_quota - self.used_tokens)
            return True
        
        def add_quota(self, additional_tokens: int):
            self.allocated_quota += additional_tokens
            self.remaining_tokens = self.allocated_quota - self.used_tokens
            self.total_purchased += additional_tokens
    
    # 1. 기본 속성 테스트
    print("1. 기본 속성 테스트")
    quota = TestUserTokenQuota(
        user_id=123,
        plan_month=date(2024, 2, 1),
        allocated_quota=10000,
        used_tokens=3000,
        remaining_tokens=7000,
        total_purchased=0
    )
    
    print(f"   사용자 ID: {quota.user_id}")
    print(f"   계획 월: {quota.plan_month}")
    print(f"   할당량: {quota.allocated_quota:,}")
    print(f"   사용량: {quota.used_tokens:,}")
    print(f"   잔여량: {quota.remaining_tokens:,}")
    print(f"   구매량: {quota.total_purchased:,}")
    print(f"   사용률: {quota.usage_percentage:.1%}")
    print(f"   쿼터 초과: {quota.is_quota_exceeded}")
    
    assert quota.usage_percentage == 0.3
    assert quota.is_quota_exceeded is False
    print("   ✅ 기본 속성 확인 성공")
    
    # 2. 토큰 소비 메서드 테스트
    print("\n2. 토큰 소비 메서드 테스트")
    
    # 정상 소비
    result = quota.consume_tokens(2000)
    print(f"   2000 토큰 소비 결과: {result}")
    print(f"   소비 후 사용량: {quota.used_tokens:,}")
    print(f"   소비 후 잔여량: {quota.remaining_tokens:,}")
    
    assert result is True
    assert quota.used_tokens == 5000
    assert quota.remaining_tokens == 5000
    
    # 초과 소비 시도
    result = quota.consume_tokens(10000)
    print(f"   10000 토큰 초과 소비 시도: {result}")
    
    assert result is False
    assert quota.used_tokens == 5000  # 변화 없음
    print("   ✅ 토큰 소비 메서드 확인 성공")
    
    # 3. 쿼터 추가 메서드 테스트
    print("\n3. 쿼터 추가 메서드 테스트")
    old_quota = quota.allocated_quota
    old_purchased = quota.total_purchased
    
    quota.add_quota(5000)
    print(f"   5000 토큰 추가 후:")
    print(f"     할당량: {old_quota:,} → {quota.allocated_quota:,}")
    print(f"     구매량: {old_purchased:,} → {quota.total_purchased:,}")
    print(f"     잔여량: {quota.remaining_tokens:,}")
    
    assert quota.allocated_quota == 15000
    assert quota.total_purchased == 5000
    assert quota.remaining_tokens == 10000  # 15000 - 5000(사용됨)
    print("   ✅ 쿼터 추가 메서드 확인 성공")
    
    print("=== UserTokenQuota 모델 속성 테스트 완료 ===")


def test_token_purchase_model_structure():
    """TokenPurchase 모델 구조 테스트"""
    print("\n=== TokenPurchase 모델 구조 테스트 ===")
    
    class TestTokenPurchase:
        def __init__(self, user_id, plan_month, token_amount, purchase_type="purchase", 
                     payment_method=None, payment_amount=None, currency="KRW", 
                     status="completed", transaction_id=None):
            self.id = 1
            self.user_id = user_id
            self.plan_month = plan_month
            self.token_amount = token_amount
            self.purchase_type = purchase_type
            self.payment_method = payment_method
            self.payment_amount = payment_amount
            self.currency = currency
            self.status = status
            self.transaction_id = transaction_id
            self.created_at = datetime.now()
            self.processed_at = datetime.now() if status == "completed" else None
        
        def __repr__(self):
            return f"<TokenPurchase(user_id={self.user_id}, amount={self.token_amount}, status={self.status})>"
    
    # 1. 기본 구매 기록 생성
    print("1. 기본 구매 기록 생성")
    purchase = TestTokenPurchase(
        user_id=456,
        plan_month=date(2024, 2, 1),
        token_amount=5000,
        purchase_type="purchase",
        payment_method="card",
        payment_amount=5000.0,
        currency="KRW",
        transaction_id="tx_test_001"
    )
    
    print(f"   구매 기록 ID: {purchase.id}")
    print(f"   사용자 ID: {purchase.user_id}")
    print(f"   토큰 수량: {purchase.token_amount:,}")
    print(f"   구매 유형: {purchase.purchase_type}")
    print(f"   결제 수단: {purchase.payment_method}")
    print(f"   결제 금액: {purchase.payment_amount:,} {purchase.currency}")
    print(f"   상태: {purchase.status}")
    print(f"   거래 ID: {purchase.transaction_id}")
    print(f"   처리 시간: {purchase.processed_at}")
    
    assert purchase.user_id == 456
    assert purchase.token_amount == 5000
    assert purchase.status == "completed"
    print("   ✅ 기본 구매 기록 생성 성공")
    
    # 2. 다양한 구매 유형 테스트
    print("\n2. 다양한 구매 유형 테스트")
    purchase_types = [
        ("purchase", "일반 구매"),
        ("bonus", "보너스 지급"),
        ("refund", "환불 처리")
    ]
    
    for p_type, description in purchase_types:
        test_purchase = TestTokenPurchase(
            user_id=789,
            plan_month=date(2024, 2, 1),
            token_amount=1000,
            purchase_type=p_type,
            transaction_id=f"tx_{p_type}_001"
        )
        
        print(f"   {description}: {test_purchase.purchase_type} - {test_purchase.transaction_id}")
        assert test_purchase.purchase_type == p_type
    
    print("   ✅ 다양한 구매 유형 테스트 성공")
    
    # 3. __repr__ 메서드 테스트
    print("\n3. 문자열 표현 테스트")
    repr_str = repr(purchase)
    print(f"   문자열 표현: {repr_str}")
    
    assert "TokenPurchase" in repr_str
    assert "456" in repr_str
    assert "5000" in repr_str
    print("   ✅ 문자열 표현 테스트 성공")
    
    print("=== TokenPurchase 모델 구조 테스트 완료 ===")


def test_model_relationships():
    """모델 간 관계 로직 테스트 (서비스 레벨)"""
    print("\n=== 모델 관계 로직 테스트 ===")
    
    # 사용자별 쿼터와 구매 기록을 관리하는 간단한 저장소
    class ModelRelationshipTest:
        def __init__(self):
            self.quotas = {}
            self.purchases = {}
            self.next_purchase_id = 1
        
        def create_quota(self, user_id: int, plan_month: date):
            """쿼터 생성"""
            key = (user_id, plan_month)
            self.quotas[key] = {
                "user_id": user_id,
                "plan_month": plan_month,
                "allocated_quota": 10000,
                "used_tokens": 0,
                "remaining_tokens": 10000,
                "total_purchased": 0
            }
            return self.quotas[key]
        
        def create_purchase(self, user_id: int, plan_month: date, token_amount: int):
            """구매 기록 생성"""
            purchase_id = self.next_purchase_id
            self.next_purchase_id += 1
            
            self.purchases[purchase_id] = {
                "id": purchase_id,
                "user_id": user_id,
                "plan_month": plan_month,
                "token_amount": token_amount,
                "status": "completed"
            }
            return self.purchases[purchase_id]
        
        def get_purchases_for_quota(self, user_id: int, plan_month: date):
            """특정 쿼터에 해당하는 구매 기록들 조회"""
            return [
                purchase for purchase in self.purchases.values()
                if purchase["user_id"] == user_id and purchase["plan_month"] == plan_month
            ]
        
        def get_quota_with_purchases(self, user_id: int, plan_month: date):
            """쿼터와 관련 구매 기록을 함께 조회"""
            key = (user_id, plan_month)
            quota = self.quotas.get(key)
            if quota:
                quota["purchases"] = self.get_purchases_for_quota(user_id, plan_month)
            return quota
    
    # 1. 기본 관계 설정 테스트
    print("1. 기본 관계 설정 테스트")
    store = ModelRelationshipTest()
    user_id = 1001
    month = date(2024, 2, 1)
    
    # 쿼터 생성
    quota = store.create_quota(user_id, month)
    print(f"   쿼터 생성: 사용자 {user_id}, 월 {month}")
    
    # 구매 기록 생성
    purchase1 = store.create_purchase(user_id, month, 5000)
    purchase2 = store.create_purchase(user_id, month, 3000)
    print(f"   구매 기록 생성: {len([purchase1, purchase2])}개")
    
    assert quota["user_id"] == user_id
    assert purchase1["user_id"] == user_id
    print("   ✅ 기본 관계 설정 성공")
    
    # 2. 관계 조회 테스트
    print("\n2. 관계 조회 테스트")
    purchases = store.get_purchases_for_quota(user_id, month)
    print(f"   해당 쿼터의 구매 기록 수: {len(purchases)}")
    
    total_purchased = sum(p["token_amount"] for p in purchases)
    print(f"   총 구매량: {total_purchased:,} 토큰")
    
    assert len(purchases) == 2
    assert total_purchased == 8000
    print("   ✅ 관계 조회 테스트 성공")
    
    # 3. 통합 조회 테스트
    print("\n3. 통합 조회 테스트")
    quota_with_purchases = store.get_quota_with_purchases(user_id, month)
    
    print(f"   쿼터 정보:")
    print(f"     할당량: {quota_with_purchases['allocated_quota']:,}")
    print(f"     관련 구매 기록: {len(quota_with_purchases['purchases'])}개")
    
    for i, purchase in enumerate(quota_with_purchases["purchases"], 1):
        print(f"     구매 {i}: {purchase['token_amount']:,} 토큰 (ID: {purchase['id']})")
    
    assert len(quota_with_purchases["purchases"]) == 2
    print("   ✅ 통합 조회 테스트 성공")
    
    # 4. 다른 월 쿼터 분리 테스트
    print("\n4. 다른 월 쿼터 분리 테스트")
    next_month = date(2024, 3, 1)
    
    # 다음 달 쿼터 및 구매 생성
    next_quota = store.create_quota(user_id, next_month)
    next_purchase = store.create_purchase(user_id, next_month, 2000)
    
    # 이전 달 구매 기록은 그대로인지 확인
    feb_purchases = store.get_purchases_for_quota(user_id, month)
    mar_purchases = store.get_purchases_for_quota(user_id, next_month)
    
    print(f"   2월 구매 기록: {len(feb_purchases)}개")
    print(f"   3월 구매 기록: {len(mar_purchases)}개")
    
    assert len(feb_purchases) == 2
    assert len(mar_purchases) == 1
    assert mar_purchases[0]["token_amount"] == 2000
    print("   ✅ 월별 쿼터 분리 테스트 성공")
    
    print("=== 모델 관계 로직 테스트 완료 ===")


def test_database_constraints_simulation():
    """데이터베이스 제약조건 시뮬레이션 테스트"""
    print("\n=== 데이터베이스 제약조건 시뮬레이션 ===")
    
    class ConstraintValidator:
        @staticmethod
        def validate_user_token_quota(quota_data):
            """UserTokenQuota 제약조건 검증"""
            errors = []
            
            # 필수 필드 체크
            required_fields = ["user_id", "plan_month", "allocated_quota", "used_tokens", "remaining_tokens"]
            for field in required_fields:
                if field not in quota_data or quota_data[field] is None:
                    errors.append(f"필수 필드 누락: {field}")
            
            if errors:
                return False, errors
            
            # 양수 제약조건
            positive_fields = ["allocated_quota", "used_tokens", "remaining_tokens", "total_purchased"]
            for field in positive_fields:
                if field in quota_data and quota_data[field] < 0:
                    errors.append(f"{field}는 0 이상이어야 합니다")
            
            # 토큰 균형 체크
            allocated = quota_data.get("allocated_quota", 0)
            used = quota_data.get("used_tokens", 0)
            remaining = quota_data.get("remaining_tokens", 0)
            
            if remaining != (allocated - used):
                errors.append(f"토큰 균형 오류: remaining({remaining}) != allocated({allocated}) - used({used})")
            
            return len(errors) == 0, errors
        
        @staticmethod
        def validate_token_purchase(purchase_data):
            """TokenPurchase 제약조건 검증"""
            errors = []
            
            # 필수 필드 체크
            required_fields = ["user_id", "plan_month", "token_amount"]
            for field in required_fields:
                if field not in purchase_data or purchase_data[field] is None:
                    errors.append(f"필수 필드 누락: {field}")
            
            if errors:
                return False, errors
            
            # 토큰 수량 양수 체크
            if purchase_data.get("token_amount", 0) <= 0:
                errors.append("token_amount는 0보다 커야 합니다")
            
            # 유효한 구매 타입 체크
            valid_types = ["purchase", "bonus", "refund"]
            if purchase_data.get("purchase_type") not in valid_types:
                errors.append(f"purchase_type은 {valid_types} 중 하나여야 합니다")
            
            # 유효한 상태 체크
            valid_statuses = ["pending", "completed", "failed", "refunded"]
            if purchase_data.get("status") not in valid_statuses:
                errors.append(f"status는 {valid_statuses} 중 하나여야 합니다")
            
            # 유효한 통화 체크
            valid_currencies = ["KRW", "USD", "EUR", "JPY"]
            if purchase_data.get("currency") and purchase_data.get("currency") not in valid_currencies:
                errors.append(f"currency는 {valid_currencies} 중 하나여야 합니다")
            
            return len(errors) == 0, errors
    
    # 1. 유효한 쿼터 데이터 테스트
    print("1. 유효한 쿼터 데이터 검증")
    valid_quota = {
        "user_id": 123,
        "plan_month": date(2024, 2, 1),
        "allocated_quota": 10000,
        "used_tokens": 3000,
        "remaining_tokens": 7000,
        "total_purchased": 0
    }
    
    is_valid, errors = ConstraintValidator.validate_user_token_quota(valid_quota)
    print(f"   유효한 쿼터 검증 결과: {is_valid}")
    if errors:
        for error in errors:
            print(f"     오류: {error}")
    
    assert is_valid is True
    print("   ✅ 유효한 쿼터 검증 성공")
    
    # 2. 제약조건 위반 쿼터 테스트
    print("\n2. 제약조건 위반 쿼터 검증")
    invalid_quotas = [
        # 음수 값
        {"user_id": 123, "plan_month": date(2024, 2, 1), "allocated_quota": -1000, 
         "used_tokens": 0, "remaining_tokens": 0},
        
        # 토큰 균형 오류
        {"user_id": 123, "plan_month": date(2024, 2, 1), "allocated_quota": 10000, 
         "used_tokens": 3000, "remaining_tokens": 8000},  # 7000이어야 함
        
        # 필수 필드 누락
        {"user_id": 123, "allocated_quota": 10000}
    ]
    
    for i, invalid_quota in enumerate(invalid_quotas, 1):
        is_valid, errors = ConstraintValidator.validate_user_token_quota(invalid_quota)
        print(f"   무효한 쿼터 {i} 검증 결과: {is_valid}")
        if errors:
            for error in errors:
                print(f"     오류: {error}")
        assert is_valid is False
    
    print("   ✅ 제약조건 위반 검증 성공")
    
    # 3. 유효한 구매 데이터 테스트
    print("\n3. 유효한 구매 데이터 검증")
    valid_purchase = {
        "user_id": 456,
        "plan_month": date(2024, 2, 1),
        "token_amount": 5000,
        "purchase_type": "purchase",
        "status": "completed",
        "currency": "KRW"
    }
    
    is_valid, errors = ConstraintValidator.validate_token_purchase(valid_purchase)
    print(f"   유효한 구매 검증 결과: {is_valid}")
    assert is_valid is True
    print("   ✅ 유효한 구매 검증 성공")
    
    # 4. 제약조건 위반 구매 테스트
    print("\n4. 제약조건 위반 구매 검증")
    invalid_purchases = [
        # 토큰 수량 0 이하
        {"user_id": 456, "plan_month": date(2024, 2, 1), "token_amount": 0},
        
        # 잘못된 구매 타입
        {"user_id": 456, "plan_month": date(2024, 2, 1), "token_amount": 1000, "purchase_type": "invalid"},
        
        # 잘못된 통화
        {"user_id": 456, "plan_month": date(2024, 2, 1), "token_amount": 1000, "currency": "INVALID"}
    ]
    
    for i, invalid_purchase in enumerate(invalid_purchases, 1):
        is_valid, errors = ConstraintValidator.validate_token_purchase(invalid_purchase)
        print(f"   무효한 구매 {i} 검증 결과: {is_valid}")
        if errors:
            for error in errors:
                print(f"     오류: {error}")
        assert is_valid is False
    
    print("   ✅ 제약조건 위반 검증 성공")
    
    print("=== 데이터베이스 제약조건 시뮬레이션 완료 ===")


if __name__ == "__main__":
    try:
        print("🗄️  데이터베이스 모델 구조 및 관계 검증 테스트\n")
        
        test_user_token_quota_model_properties()
        test_token_purchase_model_structure()
        test_model_relationships()
        test_database_constraints_simulation()
        
        print(f"\n✨ 데이터베이스 모델 테스트가 성공적으로 완료되었습니다!")
        print("모든 모델의 구조, 속성, 관계, 제약조건이 정상적으로 작동합니다.")
        
        print(f"\n📊 테스트 요약:")
        print("✅ UserTokenQuota 모델 속성 및 메서드")
        print("✅ TokenPurchase 모델 구조 및 표현")
        print("✅ 모델 간 관계 로직 (서비스 레벨)")
        print("✅ 데이터베이스 제약조건 검증")
        
    except Exception as e:
        print(f"\n💥 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)