"""
AI 모델 카탈로그 초기화 유틸리티
"""
import asyncio
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.core.models import ModelCatalog
from app.core.logging import logger
from datetime import datetime

# 초기 모델 데이터
INITIAL_MODEL_DATA = [
    {
        'model_name': 'text-embedding-3-small',
        'alias': 'Text Embedding 3 Small',
        'provider': 'openai',
        'model_type': 'embedding',
        'role_mask': 2,
        'status': 'active',
        'version': None,
        'price_input': None,
        'price_output': None,
        'price_embedding': 0.02,
        'weight_input': None,
        'weight_output': None,
        'weight_embedding': 0.064,
        'reference_model': 'gpt-5-mini',
        'reference_price_input': 0.25,
        'reference_price_output': 2.0,
        'cached_factor': 0.1,
        'embedding_alpha': 0.8,
        'is_active': True
    },
    {
        'model_name': 'gpt-4o-mini',
        'alias': 'GPT-4o Mini',
        'provider': 'openai',
        'model_type': 'llm',
        'role_mask': 1,
        'status': 'active',
        'version': '2024-07-18',
        'price_input': 0.15,
        'price_output': 0.6,
        'price_embedding': None,
        'weight_input': 0.6,
        'weight_output': 2.4,
        'weight_embedding': None,
        'reference_model': 'gpt-5-mini',
        'reference_price_input': 0.25,
        'reference_price_output': 2.0,
        'cached_factor': 0.1,
        'embedding_alpha': 0.8,
        'is_active': True
    }
]

def init_model_catalog(db: Session) -> bool:
    """
    데이터베이스에 초기 모델 카탈로그 데이터가 없으면 삽입
    
    Args:
        db: 데이터베이스 세션
        
    Returns:
        bool: 초기화 작업이 수행되었는지 여부
    """
    try:
        # 기존 모델 수 확인
        existing_count = db.query(ModelCatalog).count()
        
        if existing_count > 0:
            logger.info(f"모델 카탈로그에 이미 {existing_count}개의 모델이 있습니다. 초기화를 건너뜁니다.")
            return False
        
        logger.info("모델 카탈로그가 비어있습니다. 초기 데이터를 삽입합니다...")
        
        # 초기 데이터 삽입
        inserted_count = 0
        for model_data in INITIAL_MODEL_DATA:
            try:
                # 가중치 자동 계산
                model = ModelCatalog(**model_data)
                model.calculate_weights()
                
                db.add(model)
                inserted_count += 1
                logger.info(f"모델 추가: {model.alias} ({model.model_name})")
                
            except Exception as e:
                logger.error(f"모델 데이터 삽입 실패 ({model_data['model_name']}): {e}")
                continue
        
        db.commit()
        logger.info(f"총 {inserted_count}개의 초기 모델 데이터를 삽입했습니다.")
        return True
        
    except Exception as e:
        logger.error(f"모델 카탈로그 초기화 중 오류 발생: {e}")
        db.rollback()
        return False

def ensure_model_catalog_initialized(db: Session) -> None:
    """
    앱 시작 시 모델 카탈로그가 초기화되어 있는지 확인하고 필요시 초기화
    
    Args:
        db: 데이터베이스 세션
    """
    try:
        logger.info("모델 카탈로그 초기화 상태를 확인합니다...")
        
        # 활성 모델 수 확인
        active_models_count = db.query(ModelCatalog).filter(
            ModelCatalog.is_active == True
        ).count()
        
        if active_models_count == 0:
            logger.warning("활성 모델이 없습니다. 초기 데이터를 설정합니다.")
            init_model_catalog(db)
        else:
            logger.info(f"현재 {active_models_count}개의 활성 모델이 설정되어 있습니다.")
            
            # 모델 목록 로깅
            models = db.query(ModelCatalog).filter(
                ModelCatalog.is_active == True
            ).all()
            
            for model in models:
                logger.info(f"  - {model.alias} ({model.model_name}) - {model.provider}")
    
    except Exception as e:
        logger.error(f"모델 카탈로그 확인 중 오류 발생: {e}")

def update_model_weights(db: Session, model_name: str, **weights) -> bool:
    """
    특정 모델의 가중치 업데이트
    
    Args:
        db: 데이터베이스 세션
        model_name: 모델명
        **weights: 업데이트할 가중치 (weight_input, weight_output, weight_embedding)
        
    Returns:
        bool: 업데이트 성공 여부
    """
    try:
        model = db.query(ModelCatalog).filter(
            ModelCatalog.model_name == model_name
        ).first()
        
        if not model:
            logger.error(f"모델을 찾을 수 없습니다: {model_name}")
            return False
        
        # 가중치 업데이트
        updated_fields = []
        for key, value in weights.items():
            if hasattr(model, key) and value is not None:
                setattr(model, key, value)
                updated_fields.append(f"{key}={value}")
        
        if updated_fields:
            model.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"모델 가중치 업데이트: {model_name} - {', '.join(updated_fields)}")
            return True
        else:
            logger.warning(f"업데이트할 가중치가 없습니다: {model_name}")
            return False
            
    except Exception as e:
        logger.error(f"모델 가중치 업데이트 중 오류 발생: {e}")
        db.rollback()
        return False
