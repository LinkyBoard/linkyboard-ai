"""
Repository 패키지 - 데이터 액세스 계층

이 패키지는 데이터베이스와의 상호작용을 담당하는 Repository 클래스들을 포함합니다.
각 Repository는 특정 모델에 대한 CRUD 작업과 특화된 쿼리 기능을 제공합니다.

Usage:
    from app.core.repository import item_repository
    
    # 또는
    from app.core.repository.item_repository import ItemRepository
"""

from .base import BaseRepository
from .item_repository import ItemRepository, item_repository

__all__ = [
    "BaseRepository",
    "ItemRepository", "item_repository"
]
