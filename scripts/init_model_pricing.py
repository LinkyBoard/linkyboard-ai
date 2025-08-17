#!/usr/bin/env python3
"""
모델 가격 정보 초기화 스크립트

기본 모델들의 가격 정보와 WTU 가중치를 데이터베이스에 초기화합니다.
"""

import asyncio
import logging
from datetime import datetime

from app.core.database import get_db
from app.metrics.pricing_service import pricing_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """기본 모델 가격 정보 초기화"""
    try:
        logger.info("모델 가격 정보 초기화 시작...")
        
        # 기본 모델들 초기화
        async for session in get_db():
            await pricing_service.initialize_default_models(session)
            break  # 첫 번째 세션만 사용
        
        logger.info("모델 가격 정보 초기화 완료!")
        
        # 현재 등록된 모델들 출력
        async for session in get_db():
            from sqlalchemy import select
            from app.core.models import ModelPricing
            
            stmt = select(ModelPricing).where(ModelPricing.is_active == True)
            result = await session.execute(stmt)
            models = result.scalars().all()
            
            logger.info(f"등록된 모델 수: {len(models)}")
            for model in models:
                logger.info(
                    f"  - {model.model_name} ({model.model_type}): "
                    f"가중치 입력={model.weight_input}, 출력={model.weight_output}, "
                    f"임베딩={model.weight_embedding}"
                )
            break
        
    except Exception as e:
        logger.error(f"초기화 실패: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
