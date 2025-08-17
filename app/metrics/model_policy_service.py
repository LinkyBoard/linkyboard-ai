"""
보드/사용자 모델 정책 관리 서비스

보드별 기본 모델, 허용 모델, 예산 관리 기능을 제공합니다.
"""

import logging
from typing import Optional, List, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.models import BoardModelPolicy, UserModelPolicy, ModelCatalog
from app.metrics.model_catalog_service import model_catalog_service

logger = logging.getLogger(__name__)


class ModelPolicyService:
    """모델 정책 관리 서비스"""

    async def get_board_policy(self, board_id: UUID, session: Optional[AsyncSession] = None) -> Optional[BoardModelPolicy]:
        """보드 모델 정책 조회"""
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
        
        try:
            stmt = select(BoardModelPolicy).where(BoardModelPolicy.board_id == board_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
            
        finally:
            if close_session:
                await session.aclose()

    async def create_or_update_board_policy(
        self,
        board_id: UUID,
        default_model_id: Optional[int] = None,
        allowed_model_ids: Optional[List[int]] = None,
        budget_wtu: Optional[int] = None,
        confidence_target: Optional[float] = None,
        session: Optional[AsyncSession] = None
    ) -> BoardModelPolicy:
        """보드 모델 정책 생성 또는 업데이트"""
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
        
        try:
            # 기존 정책 확인
            stmt = select(BoardModelPolicy).where(BoardModelPolicy.board_id == board_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # 업데이트
                if default_model_id is not None:
                    existing.default_model_id = default_model_id
                if allowed_model_ids is not None:
                    existing.allowed_model_ids = allowed_model_ids
                if budget_wtu is not None:
                    existing.budget_wtu = budget_wtu
                if confidence_target is not None:
                    existing.confidence_target = confidence_target
                
                policy = existing
                logger.info(f"Updated board policy for {board_id}")
            else:
                # 생성
                policy = BoardModelPolicy(
                    board_id=board_id,
                    default_model_id=default_model_id,
                    allowed_model_ids=allowed_model_ids,
                    budget_wtu=budget_wtu,
                    confidence_target=confidence_target
                )
                session.add(policy)
                logger.info(f"Created board policy for {board_id}")
            
            await session.commit()
            await session.refresh(policy)
            return policy
            
        finally:
            if close_session:
                await session.aclose()

    async def validate_model_selection(
        self,
        model_id: int,
        board_id: Optional[UUID] = None,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """모델 선택 유효성 검사 (보드/사용자 정책 기준)"""
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
        
        try:
            # 모델이 활성화되어 있는지 확인
            model = await model_catalog_service.get_model_catalog(None, session)
            stmt = select(ModelCatalog).where(
                ModelCatalog.id == model_id,
                ModelCatalog.status == "active",
                ModelCatalog.is_active == True
            )
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                logger.warning(f"Model {model_id} is not active")
                return False
            
            # 보드 정책 확인
            if board_id:
                board_policy = await self.get_board_policy(board_id, session)
                if board_policy and board_policy.allowed_model_ids:
                    if model_id not in board_policy.allowed_model_ids:
                        logger.warning(f"Model {model_id} not allowed for board {board_id}")
                        return False
            
            # 사용자 정책 확인 (선택사항)
            if user_id:
                user_policy = await self.get_user_policy(user_id, session)
                if user_policy and user_policy.allowed_model_ids:
                    if model_id not in user_policy.allowed_model_ids:
                        logger.warning(f"Model {model_id} not allowed for user {user_id}")
                        return False
            
            return True
            
        finally:
            if close_session:
                await session.aclose()

    async def get_effective_model(
        self,
        requested_model: Optional[str] = None,
        board_id: Optional[UUID] = None,
        user_id: Optional[int] = None,
        model_type: str = "llm",
        session: Optional[AsyncSession] = None
    ) -> Optional[ModelCatalog]:
        """유효한 모델 결정 (우선순위: 요청 > 보드 기본값 > 시스템 기본값)"""
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
        
        try:
            # 1. 요청된 모델 확인
            if requested_model:
                model = await model_catalog_service.get_model_by_alias(requested_model, session)
                if model and await self.validate_model_selection(model.id, board_id, user_id, session):
                    logger.info(f"Using requested model: {requested_model}")
                    return model
                else:
                    logger.warning(f"Requested model {requested_model} is not valid or allowed")
            
            # 2. 보드 기본값 확인
            if board_id:
                board_policy = await self.get_board_policy(board_id, session)
                if board_policy and board_policy.default_model_id:
                    stmt = select(ModelCatalog).where(ModelCatalog.id == board_policy.default_model_id)
                    result = await session.execute(stmt)
                    model = result.scalar_one_or_none()
                    if model and model.model_type == model_type:
                        logger.info(f"Using board default model: {model.alias}")
                        return model
            
            # 3. 시스템 기본값 사용
            active_models = await model_catalog_service.get_active_models(model_type, session)
            if active_models:
                # 첫 번째 활성 모델을 기본값으로 사용
                default_model = active_models[0]
                logger.info(f"Using system default model: {default_model.alias}")
                return default_model
            
            logger.error(f"No valid model found for type {model_type}")
            return None
            
        finally:
            if close_session:
                await session.aclose()

    async def get_user_policy(self, user_id: int, session: Optional[AsyncSession] = None) -> Optional[UserModelPolicy]:
        """사용자 모델 정책 조회"""
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
        
        try:
            stmt = select(UserModelPolicy).where(UserModelPolicy.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
            
        finally:
            if close_session:
                await session.aclose()

    async def estimate_wtu_cost(
        self,
        model: ModelCatalog,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        estimated_embed_tokens: int = 0,
        session: Optional[AsyncSession] = None
    ) -> int:
        """모델 기반 WTU 비용 추정"""
        # 가중치 조회
        llm_model = model.model_name if model.model_type == "llm" else None
        embed_model = model.model_name if model.model_type == "embedding" else None
        
        weights = await model_catalog_service.get_wtu_weights(llm_model, embed_model, session)
        
        # WTU 계산
        estimated_wtu = (
            estimated_input_tokens * weights['w_in'] +
            estimated_output_tokens * weights['w_out'] +
            estimated_embed_tokens * weights['w_embed']
        )
        
        return int(estimated_wtu)

    async def check_budget_limit(
        self,
        board_id: UUID,
        estimated_wtu: int,
        current_month_wtu: int,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """예산 한도 확인"""
        board_policy = await self.get_board_policy(board_id, session)
        if not board_policy or not board_policy.budget_wtu:
            return True  # 예산 제한 없음
        
        total_wtu = current_month_wtu + estimated_wtu
        if total_wtu > board_policy.budget_wtu:
            logger.warning(f"Budget limit exceeded for board {board_id}: {total_wtu} > {board_policy.budget_wtu}")
            return False
        
        return True


# 전역 서비스 인스턴스
model_policy_service = ModelPolicyService()
