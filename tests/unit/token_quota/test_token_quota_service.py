"""
토큰 쿼터 서비스 단위 테스트
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.metrics.token_quota_service import (
    get_or_create_user_quota,
    check_token_availability,
    consume_tokens,
    purchase_tokens,
    get_user_quota_info,
    InsufficientTokensError
)
from app.core.models import UserTokenQuota, TokenPurchase


@pytest.fixture
def mock_session():
    """Mock AsyncSession"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_quota():
    """샘플 토큰 쿼터 데이터"""
    return UserTokenQuota(
        user_id=123,
        plan_month=date(2024, 1, 1),
        allocated_quota=10000,
        used_tokens=2000,
        remaining_tokens=8000,
        total_purchased=0
    )


class TestTokenQuotaService:
    """토큰 쿼터 서비스 테스트"""

    @pytest.mark.asyncio
    async def test_get_or_create_user_quota_existing(self, mock_session, sample_quota):
        """기존 쿼터 조회 테스트"""
        # Mock database query result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_quota
        mock_session.execute.return_value = mock_result
        
        quota = await get_or_create_user_quota(123, date(2024, 1, 1), mock_session)
        
        assert quota.user_id == 123
        assert quota.allocated_quota == 10000
        assert quota.remaining_tokens == 8000
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_user_quota_new(self, mock_session):
        """새 쿼터 생성 테스트"""
        # Mock no existing quota found
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Mock new quota creation
        new_quota = UserTokenQuota(
            user_id=456,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=0,
            remaining_tokens=10000,
            total_purchased=0
        )
        
        with patch('app.metrics.token_quota_service.UserTokenQuota') as mock_quota_class:
            mock_quota_class.return_value = new_quota
            
            quota = await get_or_create_user_quota(456, date(2024, 1, 1), mock_session)
            
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_token_availability_sufficient(self, mock_session):
        """충분한 토큰이 있는 경우 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=2000,
            remaining_tokens=8000,
            total_purchased=0
        )
        
        with patch('app.metrics.token_quota_service.get_or_create_user_quota') as mock_get_quota:
            mock_get_quota.return_value = quota
            
            available = await check_token_availability(123, 500, session=mock_session)
            assert available is True

    @pytest.mark.asyncio
    async def test_check_token_availability_insufficient(self, mock_session):
        """토큰이 부족한 경우 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=9900,
            remaining_tokens=100,
            total_purchased=0
        )
        
        with patch('app.metrics.token_quota_service.get_or_create_user_quota') as mock_get_quota:
            mock_get_quota.return_value = quota
            
            available = await check_token_availability(123, 500, session=mock_session)
            assert available is False

    @pytest.mark.asyncio
    async def test_consume_tokens_success(self, mock_session):
        """토큰 소비 성공 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=2000,
            remaining_tokens=8000,
            total_purchased=0
        )
        
        with patch('app.metrics.token_quota_service.get_or_create_user_quota') as mock_get_quota:
            mock_get_quota.return_value = quota
            
            updated_quota = await consume_tokens(123, 500, session=mock_session)
            
            # 토큰이 소비되었는지 확인
            assert quota.used_tokens == 2500
            assert quota.remaining_tokens == 7500
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_consume_tokens_insufficient(self, mock_session):
        """토큰 부족으로 소비 실패 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=9900,
            remaining_tokens=100,
            total_purchased=0
        )
        
        with patch('app.metrics.token_quota_service.get_or_create_user_quota') as mock_get_quota:
            mock_get_quota.return_value = quota
            
            with pytest.raises(InsufficientTokensError) as exc_info:
                await consume_tokens(123, 500, session=mock_session)
            
            assert exc_info.value.required == 500
            assert exc_info.value.available == 100
            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_purchase_tokens(self, mock_session):
        """토큰 구매 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=2000,
            remaining_tokens=8000,
            total_purchased=0
        )
        
        purchase = TokenPurchase(
            id=1,
            user_id=123,
            plan_month=date(2024, 1, 1),
            token_amount=5000,
            purchase_type="purchase",
            status="completed",
            created_at=datetime.now(),
            processed_at=datetime.now()
        )
        
        with patch('app.metrics.token_quota_service.get_or_create_user_quota') as mock_get_quota:
            with patch('app.metrics.token_quota_service.TokenPurchase') as mock_purchase_class:
                mock_get_quota.return_value = quota
                mock_purchase_class.return_value = purchase
                
                result = await purchase_tokens(
                    user_id=123,
                    token_amount=5000,
                    transaction_id="tx_123",
                    session=mock_session
                )
                
                # 쿼터가 업데이트되었는지 확인
                assert quota.allocated_quota == 15000
                assert quota.remaining_tokens == 13000
                assert quota.total_purchased == 5000
                
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_quota_info(self, mock_session, sample_quota):
        """사용자 쿼터 정보 조회 테스트"""
        with patch('app.metrics.token_quota_service.get_or_create_user_quota') as mock_get_quota:
            mock_get_quota.return_value = sample_quota
            
            info = await get_user_quota_info(123, session=mock_session)
            
            assert info["user_id"] == 123
            assert info["allocated_quota"] == 10000
            assert info["used_tokens"] == 2000
            assert info["remaining_tokens"] == 8000
            assert info["usage_percentage"] == 0.2
            assert info["is_quota_exceeded"] is False


class TestUserTokenQuotaModel:
    """UserTokenQuota 모델 테스트"""

    def test_quota_properties(self):
        """쿼터 속성 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=3000,
            remaining_tokens=7000,
            total_purchased=2000
        )
        
        assert quota.usage_percentage == 0.3
        assert quota.is_quota_exceeded is False
        assert quota.can_consume(5000) is True
        assert quota.can_consume(8000) is False

    def test_consume_tokens_success(self):
        """토큰 소비 성공 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=3000,
            remaining_tokens=7000,
            total_purchased=0
        )
        
        result = quota.consume_tokens(2000)
        
        assert result is True
        assert quota.used_tokens == 5000
        assert quota.remaining_tokens == 5000

    def test_consume_tokens_failure(self):
        """토큰 소비 실패 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=9500,
            remaining_tokens=500,
            total_purchased=0
        )
        
        result = quota.consume_tokens(1000)
        
        assert result is False
        assert quota.used_tokens == 9500  # 변경되지 않음
        assert quota.remaining_tokens == 500  # 변경되지 않음

    def test_add_quota(self):
        """쿼터 추가 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=3000,
            remaining_tokens=7000,
            total_purchased=1000
        )
        
        quota.add_quota(5000)
        
        assert quota.allocated_quota == 15000
        assert quota.remaining_tokens == 12000
        assert quota.total_purchased == 6000

    def test_quota_exceeded(self):
        """쿼터 초과 상황 테스트"""
        quota = UserTokenQuota(
            user_id=123,
            plan_month=date(2024, 1, 1),
            allocated_quota=10000,
            used_tokens=10000,
            remaining_tokens=0,
            total_purchased=0
        )
        
        assert quota.is_quota_exceeded is True
        assert quota.usage_percentage == 1.0
        assert quota.can_consume(1) is False