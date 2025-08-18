"""
모델 관리 API 라우터 - 관리자 전용 엔드포인트
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.metrics.model_catalog_service import model_catalog_service
from .schemas import (
    ModelCatalogResponse, 
    ModelCatalogCreateRequest,
    ModelCatalogUpdateRequest,
    ModelListResponse
)

router = APIRouter(prefix="/admin/models", tags=["admin", "models"])


@router.get("/", response_model=ModelListResponse)
async def list_models(
    model_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """활성 모델 목록 조회"""
    try:
        models = await model_catalog_service.get_active_models(model_type, db)
        
        # 상태 필터링
        if status:
            models = [m for m in models if m.status == status]
        
        model_list = []
        for model in models:
            model_dict = {
                "id": model.id,
                "model_name": model.model_name,
                "alias": model.alias,
                "provider": model.provider,
                "model_type": model.model_type,
                "role_mask": model.role_mask,
                "status": model.status,
                "version": model.version,
                "price_input": model.price_input,
                "price_output": model.price_output,
                "price_embedding": model.price_embedding,
                "weight_input": model.weight_input,
                "weight_output": model.weight_output,
                "weight_embedding": model.weight_embedding,
                "is_active": model.is_active,
                "created_at": model.created_at,
                "updated_at": model.updated_at
            }
            model_list.append(model_dict)
        
        return ModelListResponse(
            models=model_list,
            total=len(model_list)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}"
        )


@router.post("/", response_model=ModelCatalogResponse)
async def create_model(
    request: ModelCatalogCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """새 모델 카탈로그 항목 생성"""
    try:
        model = await model_catalog_service.add_or_update_model_catalog(
            model_name=request.model_name,
            alias=request.alias,
            provider=request.provider,
            model_type=request.model_type,
            role_mask=request.role_mask,
            status=request.status,
            version=request.version,
            price_input=request.price_input,
            price_output=request.price_output,
            price_embedding=request.price_embedding,
            session=db
        )
        
        return ModelCatalogResponse(
            id=model.id,
            model_name=model.model_name,
            alias=model.alias,
            provider=model.provider,
            model_type=model.model_type,
            role_mask=model.role_mask,
            status=model.status,
            version=model.version,
            price_input=model.price_input,
            price_output=model.price_output,
            price_embedding=model.price_embedding,
            weight_input=model.weight_input,
            weight_output=model.weight_output,
            weight_embedding=model.weight_embedding,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create model: {str(e)}"
        )


@router.put("/{model_id}", response_model=ModelCatalogResponse)
async def update_model(
    model_id: int,
    request: ModelCatalogUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """모델 카탈로그 항목 업데이트"""
    try:
        # 먼저 모델 존재 확인
        from sqlalchemy import select
        from app.core.models import ModelCatalog
        
        stmt = select(ModelCatalog).where(ModelCatalog.id == model_id)
        result = await db.execute(stmt)
        existing_model = result.scalar_one_or_none()
        
        if not existing_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model with id {model_id} not found"
            )
        
        # 업데이트 수행
        model = await model_catalog_service.add_or_update_model_catalog(
            model_name=existing_model.model_name,  # 모델명은 변경 불가
            alias=request.alias or existing_model.alias,
            provider=request.provider or existing_model.provider,
            model_type=request.model_type or existing_model.model_type,
            role_mask=request.role_mask or existing_model.role_mask,
            status=request.status or existing_model.status,
            version=request.version or existing_model.version,
            price_input=request.price_input if request.price_input is not None else existing_model.price_input,
            price_output=request.price_output if request.price_output is not None else existing_model.price_output,
            price_embedding=request.price_embedding if request.price_embedding is not None else existing_model.price_embedding,
            session=db
        )
        
        return ModelCatalogResponse(
            id=model.id,
            model_name=model.model_name,
            alias=model.alias,
            provider=model.provider,
            model_type=model.model_type,
            role_mask=model.role_mask,
            status=model.status,
            version=model.version,
            price_input=model.price_input,
            price_output=model.price_output,
            price_embedding=model.price_embedding,
            weight_input=model.weight_input,
            weight_output=model.weight_output,
            weight_embedding=model.weight_embedding,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update model: {str(e)}"
        )


@router.post("/seed-defaults")
async def seed_default_models(
    db: AsyncSession = Depends(get_db)
):
    """기본 모델들을 카탈로그에 시드"""
    try:
        await model_catalog_service.initialize_default_models(db)
        return {"message": "Default models seeded successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed default models: {str(e)}"
        )


