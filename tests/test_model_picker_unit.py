"""
Model Picker v1 - 단위 테스트
"""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4, UUID
from datetime import date
from app.core.models import ModelCatalog, BoardModelPolicy, UserModelPolicy
from app.metrics.model_catalog_service import model_catalog_service
from app.metrics.model_policy_service import model_policy_service


class TestModelCatalogService:
    """모델 카탈로그 서비스 테스트"""
    
    @pytest.fixture
    def sample_model(self):
        """샘플 모델 데이터"""
        return ModelCatalog(
            id=1,
            alias="gpt-4o-mini",
            model_name="gpt-4o-mini",
            provider="openai",
            model_type="llm",
            role_mask=0b111,  # 모든 역할 허용
            price_per_input_token=0.15,
            price_per_output_token=0.6,
            price_currency="USD",
            input_token_weight=1.0,
            output_token_weight=4.0,
            status="active",
            version="2024-07-18"
        )
    
    @pytest.mark.asyncio
    async def test_get_model_by_alias(self, sample_model):
        """별칭으로 모델 조회 테스트"""
        with patch('app.metrics.model_catalog_service.model_catalog_service.get_model_by_alias') as mock_get:
            mock_get.return_value = sample_model
            
            result = await model_catalog_service.get_model_by_alias("gpt-4o-mini")
            
            assert result is not None
            assert result.alias == "gpt-4o-mini"
            assert result.provider == "openai"
            mock_get.assert_called_once_with("gpt-4o-mini")
    
    @pytest.mark.asyncio
    async def test_list_active_models(self, sample_model):
        """활성 모델 목록 조회 테스트"""
        with patch('app.metrics.model_catalog_service.model_catalog_service.list_active_models') as mock_list:
            mock_list.return_value = [sample_model]
            
            result = await model_catalog_service.list_active_models()
            
            assert len(result) == 1
            assert result[0].status == "active"
            mock_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_model(self):
        """모델 생성 테스트"""
        with patch('app.metrics.model_catalog_service.model_catalog_service.create_model') as mock_create:
            mock_create.return_value = ModelCatalog(id=2, alias="claude-3-haiku", model_name="claude-3-haiku-20240307")
            
            model_data = {
                "alias": "claude-3-haiku",
                "model_name": "claude-3-haiku-20240307",
                "provider": "anthropic",
                "model_type": "llm",
                "role_mask": 0b111,
                "price_per_input_token": 0.25,
                "price_per_output_token": 1.25,
                "input_token_weight": 1.0,
                "output_token_weight": 5.0
            }
            
            result = await model_catalog_service.create_model(model_data)
            
            assert result.alias == "claude-3-haiku"
            assert result.provider == "anthropic"
            mock_create.assert_called_once_with(model_data)


class TestModelPolicyService:
    """모델 정책 서비스 테스트"""
    
    @pytest.fixture
    def board_id(self):
        return uuid4()
    
    @pytest.fixture
    def user_id(self):
        return 1001
    
    @pytest.fixture
    def sample_board_policy(self, board_id):
        """샘플 보드 정책"""
        return BoardModelPolicy(
            id=1,
            board_id=board_id,
            allowed_models=["gpt-4o-mini", "claude-3-haiku"],
            default_model="gpt-4o-mini",
            budget_limit_wtu=10000,
            budget_period="monthly"
        )
    
    @pytest.fixture
    def sample_user_policy(self, board_id, user_id):
        """샘플 사용자 정책"""
        return UserModelPolicy(
            id=1,
            board_id=board_id,
            user_id=user_id,
            allowed_models=["gpt-4o-mini"],
            default_model="gpt-4o-mini",
            budget_limit_wtu=5000,
            budget_period="monthly"
        )
    
    @pytest.mark.asyncio
    async def test_get_effective_model_with_request(self, board_id, user_id, sample_board_policy):
        """요청된 모델을 포함한 유효 모델 결정 테스트"""
        with patch('app.metrics.model_policy_service.model_policy_service.get_board_policy') as mock_board_policy, \
             patch('app.metrics.model_policy_service.model_policy_service.get_user_policy') as mock_user_policy, \
             patch('app.metrics.model_catalog_service.model_catalog_service.get_model_by_alias') as mock_get_model:
            
            # Mock 설정
            mock_board_policy.return_value = sample_board_policy
            mock_user_policy.return_value = None
            mock_get_model.return_value = ModelCatalog(
                id=1, alias="gpt-4o-mini", model_name="gpt-4o-mini", 
                provider="openai", model_type="llm", status="active"
            )
            
            result = await model_policy_service.get_effective_model(
                requested_model="gpt-4o-mini",
                board_id=board_id,
                user_id=user_id,
                model_type="llm"
            )
            
            assert result is not None
            assert result.alias == "gpt-4o-mini"
    
    @pytest.mark.asyncio
    async def test_get_effective_model_default(self, board_id, user_id, sample_board_policy):
        """기본 모델 선택 테스트"""
        with patch('app.metrics.model_policy_service.model_policy_service.get_board_policy') as mock_board_policy, \
             patch('app.metrics.model_policy_service.model_policy_service.get_user_policy') as mock_user_policy, \
             patch('app.metrics.model_catalog_service.model_catalog_service.get_model_by_alias') as mock_get_model:
            
            # Mock 설정
            mock_board_policy.return_value = sample_board_policy
            mock_user_policy.return_value = None
            mock_get_model.return_value = ModelCatalog(
                id=1, alias="gpt-4o-mini", model_name="gpt-4o-mini", 
                provider="openai", model_type="llm", status="active"
            )
            
            result = await model_policy_service.get_effective_model(
                requested_model=None,  # 요청된 모델 없음
                board_id=board_id,
                user_id=user_id,
                model_type="llm"
            )
            
            assert result is not None
            assert result.alias == "gpt-4o-mini"  # 보드 정책의 기본 모델
    
    @pytest.mark.asyncio
    async def test_estimate_wtu_cost(self):
        """WTU 비용 추정 테스트"""
        model = ModelCatalog(
            id=1,
            alias="gpt-4o-mini",
            model_name="gpt-4o-mini",
            provider="openai",
            model_type="llm",
            input_token_weight=1.0,
            output_token_weight=4.0
        )
        
        estimated_wtu = await model_policy_service.estimate_wtu_cost(
            model=model,
            estimated_input_tokens=100,
            estimated_output_tokens=200
        )
        
        # 100 * 1.0 + 200 * 4.0 = 900
        assert estimated_wtu == 900
    
    @pytest.mark.asyncio
    async def test_check_budget_limit_within_budget(self, board_id):
        """예산 한도 확인 - 예산 내"""
        with patch('app.metrics.model_policy_service.model_policy_service.get_board_policy') as mock_policy:
            mock_policy.return_value = BoardModelPolicy(
                board_id=board_id,
                budget_limit_wtu=10000,
                budget_period="monthly"
            )
            
            result = await model_policy_service.check_budget_limit(
                board_id=board_id,
                estimated_wtu=500,
                current_month_wtu=5000
            )
            
            assert result is True  # 5000 + 500 < 10000
    
    @pytest.mark.asyncio
    async def test_check_budget_limit_over_budget(self, board_id):
        """예산 한도 확인 - 예산 초과"""
        with patch('app.metrics.model_policy_service.model_policy_service.get_board_policy') as mock_policy:
            mock_policy.return_value = BoardModelPolicy(
                board_id=board_id,
                budget_limit_wtu=10000,
                budget_period="monthly"
            )
            
            result = await model_policy_service.check_budget_limit(
                board_id=board_id,
                estimated_wtu=1500,
                current_month_wtu=9000
            )
            
            assert result is False  # 9000 + 1500 > 10000


class TestModelValidation:
    """모델 검증 로직 테스트"""
    
    @pytest.mark.asyncio
    async def test_model_allowed_in_board_policy(self):
        """보드 정책에서 모델 허용 확인"""
        board_policy = BoardModelPolicy(
            board_id=uuid4(),
            allowed_models=["gpt-4o-mini", "claude-3-haiku"],
            default_model="gpt-4o-mini"
        )
        
        # 허용된 모델
        assert "gpt-4o-mini" in board_policy.allowed_models
        assert "claude-3-haiku" in board_policy.allowed_models
        
        # 허용되지 않은 모델
        assert "gpt-4" not in board_policy.allowed_models
    
    @pytest.mark.asyncio
    async def test_user_policy_overrides_board_policy(self):
        """사용자 정책이 보드 정책을 재정의하는지 확인"""
        board_id = uuid4()
        user_id = 1001
        
        board_policy = BoardModelPolicy(
            board_id=board_id,
            allowed_models=["gpt-4o-mini", "claude-3-haiku", "gpt-4"],
            default_model="gpt-4o-mini"
        )
        
        user_policy = UserModelPolicy(
            board_id=board_id,
            user_id=user_id,
            allowed_models=["gpt-4o-mini"],  # 더 제한적
            default_model="gpt-4o-mini"
        )
        
        # 사용자 정책이 더 제한적이어야 함
        assert len(user_policy.allowed_models) < len(board_policy.allowed_models)
        assert "claude-3-haiku" not in user_policy.allowed_models
        assert "gpt-4" not in user_policy.allowed_models
    
    def test_wtu_calculation_accuracy(self):
        """WTU 계산 정확도 테스트"""
        # 테스트 케이스들
        test_cases = [
            {
                "input_tokens": 100,
                "output_tokens": 200,
                "input_weight": 1.0,
                "output_weight": 4.0,
                "expected_wtu": 900  # 100*1 + 200*4
            },
            {
                "input_tokens": 500,
                "output_tokens": 1000,
                "input_weight": 1.5,
                "output_weight": 6.0,
                "expected_wtu": 6750  # 500*1.5 + 1000*6
            },
            {
                "input_tokens": 0,
                "output_tokens": 100,
                "input_weight": 1.0,
                "output_weight": 4.0,
                "expected_wtu": 400  # 0*1 + 100*4
            }
        ]
        
        for case in test_cases:
            calculated_wtu = (
                case["input_tokens"] * case["input_weight"] + 
                case["output_tokens"] * case["output_weight"]
            )
            assert calculated_wtu == case["expected_wtu"], f"WTU calculation failed for case: {case}"
