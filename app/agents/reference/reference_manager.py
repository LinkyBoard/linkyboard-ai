"""
Reference Manager - 레퍼런스 자료 관리자

사용자가 업로드한 레퍼런스 자료를 저장, 검색, 관리합니다.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import uuid4
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, and_

from app.core.logging import get_logger
from app.core.database import AsyncSessionLocal
from ..schemas import ReferenceValidation

logger = get_logger(__name__)


class ReferenceMaterial:
    """레퍼런스 자료 모델"""
    
    def __init__(
        self,
        material_id: str,
        user_id: int,
        title: str,
        content: str,
        source_type: str,
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None
    ):
        self.material_id = material_id
        self.user_id = user_id
        self.title = title
        self.content = content
        self.source_type = source_type  # 'document', 'web', 'manual', 'note'
        self.source_url = source_url
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now()
        self.content_hash = self._calculate_content_hash()
        
    def _calculate_content_hash(self) -> str:
        """콘텐츠 해시 계산"""
        content_str = f"{self.title}{self.content}"
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
        
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'material_id': self.material_id,
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'source_type': self.source_type,
            'source_url': self.source_url,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'content_hash': self.content_hash
        }


class ReferenceManager:
    """레퍼런스 자료 관리자"""
    
    def __init__(self):
        self.storage_path = Path("data/references")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 인메모리 캐시 (실제 운영에서는 Redis 등 사용)
        self.material_cache: Dict[str, ReferenceMaterial] = {}
        self.user_materials_cache: Dict[int, List[str]] = {}
        
    async def add_reference_material(
        self,
        user_id: int,
        title: str,
        content: str,
        source_type: str = "manual",
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None
    ) -> str:
        """
        레퍼런스 자료 추가
        
        Args:
            user_id: 사용자 ID
            title: 자료 제목
            content: 자료 내용
            source_type: 자료 타입 ('document', 'web', 'manual', 'note')
            source_url: 소스 URL (선택사항)
            metadata: 추가 메타데이터
            session: DB 세션
            
        Returns:
            생성된 자료 ID
        """
        try:
            material_id = str(uuid4())
            
            material = ReferenceMaterial(
                material_id=material_id,
                user_id=user_id,
                title=title,
                content=content,
                source_type=source_type,
                source_url=source_url,
                metadata=metadata
            )
            
            # 캐시에 저장
            self.material_cache[material_id] = material
            
            # 사용자별 자료 목록 업데이트
            if user_id not in self.user_materials_cache:
                self.user_materials_cache[user_id] = []
            self.user_materials_cache[user_id].append(material_id)
            
            # 파일 시스템에 저장
            await self._save_material_to_file(material)
            
            # 데이터베이스에 저장 (실제 구현시)
            # await self._save_material_to_db(material, session)
            
            logger.info(f"Added reference material {material_id} for user {user_id}")
            return material_id
            
        except Exception as e:
            logger.error(f"Failed to add reference material: {e}")
            raise
    
    async def get_reference_material(
        self,
        material_id: str,
        user_id: Optional[int] = None
    ) -> Optional[ReferenceMaterial]:
        """
        레퍼런스 자료 조회
        
        Args:
            material_id: 자료 ID
            user_id: 사용자 ID (권한 확인용)
            
        Returns:
            레퍼런스 자료 또는 None
        """
        try:
            # 캐시에서 조회
            if material_id in self.material_cache:
                material = self.material_cache[material_id]
                
                # 권한 확인
                if user_id and material.user_id != user_id:
                    logger.warning(f"User {user_id} denied access to material {material_id}")
                    return None
                    
                return material
            
            # 파일에서 로드 시도
            material = await self._load_material_from_file(material_id)
            if material:
                if user_id and material.user_id != user_id:
                    return None
                    
                # 캐시에 추가
                self.material_cache[material_id] = material
                return material
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get reference material {material_id}: {e}")
            return None
    
    async def get_user_materials(
        self,
        user_id: int,
        limit: int = 100,
        source_type_filter: Optional[str] = None
    ) -> List[ReferenceMaterial]:
        """
        사용자의 레퍼런스 자료 목록 조회
        
        Args:
            user_id: 사용자 ID
            limit: 조회 제한
            source_type_filter: 소스 타입 필터
            
        Returns:
            레퍼런스 자료 목록
        """
        try:
            materials = []
            
            # 캐시에서 사용자 자료 ID 목록 가져오기
            material_ids = self.user_materials_cache.get(user_id, [])
            
            # 캐시에 없으면 파일 시스템에서 로드
            if not material_ids:
                material_ids = await self._load_user_materials_from_files(user_id)
                self.user_materials_cache[user_id] = material_ids
            
            # 각 자료 로드
            for material_id in material_ids[:limit]:
                material = await self.get_reference_material(material_id, user_id)
                if material:
                    # 소스 타입 필터 적용
                    if not source_type_filter or material.source_type == source_type_filter:
                        materials.append(material)
            
            return materials
            
        except Exception as e:
            logger.error(f"Failed to get user materials for user {user_id}: {e}")
            return []
    
    async def search_materials(
        self,
        user_id: int,
        query: str,
        limit: int = 10
    ) -> List[Tuple[ReferenceMaterial, float]]:
        """
        레퍼런스 자료 검색
        
        Args:
            user_id: 사용자 ID
            query: 검색 쿼리
            limit: 결과 제한
            
        Returns:
            (자료, 유사도 점수) 튜플 리스트
        """
        try:
            user_materials = await self.get_user_materials(user_id)
            results = []
            
            query_lower = query.lower()
            
            for material in user_materials:
                # 간단한 키워드 기반 검색
                score = 0.0
                
                # 제목에서 검색
                if query_lower in material.title.lower():
                    score += 0.5
                
                # 내용에서 검색
                content_lower = material.content.lower()
                if query_lower in content_lower:
                    # 단어 빈도에 따라 점수 조정
                    word_count = content_lower.count(query_lower)
                    score += min(0.5, word_count * 0.1)
                
                # 메타데이터에서 검색
                metadata_str = json.dumps(material.metadata, default=str).lower()
                if query_lower in metadata_str:
                    score += 0.2
                
                if score > 0:
                    results.append((material, score))
            
            # 점수순으로 정렬
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search materials: {e}")
            return []
    
    async def update_reference_material(
        self,
        material_id: str,
        user_id: int,
        **updates
    ) -> bool:
        """
        레퍼런스 자료 업데이트
        
        Args:
            material_id: 자료 ID
            user_id: 사용자 ID
            **updates: 업데이트할 필드들
            
        Returns:
            업데이트 성공 여부
        """
        try:
            material = await self.get_reference_material(material_id, user_id)
            if not material:
                return False
            
            # 업데이트 가능한 필드들
            updatable_fields = {'title', 'content', 'source_url', 'metadata'}
            
            updated = False
            for field, value in updates.items():
                if field in updatable_fields and hasattr(material, field):
                    setattr(material, field, value)
                    updated = True
            
            if updated:
                # 콘텐츠 해시 재계산
                material.content_hash = material._calculate_content_hash()
                
                # 파일에 저장
                await self._save_material_to_file(material)
                
                logger.info(f"Updated reference material {material_id}")
                
            return updated
            
        except Exception as e:
            logger.error(f"Failed to update reference material {material_id}: {e}")
            return False
    
    async def delete_reference_material(
        self,
        material_id: str,
        user_id: int
    ) -> bool:
        """
        레퍼런스 자료 삭제
        
        Args:
            material_id: 자료 ID
            user_id: 사용자 ID
            
        Returns:
            삭제 성공 여부
        """
        try:
            material = await self.get_reference_material(material_id, user_id)
            if not material:
                return False
            
            # 캐시에서 제거
            self.material_cache.pop(material_id, None)
            
            # 사용자 자료 목록에서 제거
            if user_id in self.user_materials_cache:
                if material_id in self.user_materials_cache[user_id]:
                    self.user_materials_cache[user_id].remove(material_id)
            
            # 파일 삭제
            await self._delete_material_file(material_id)
            
            logger.info(f"Deleted reference material {material_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete reference material {material_id}: {e}")
            return False
    
    async def _save_material_to_file(self, material: ReferenceMaterial):
        """자료를 파일에 저장"""
        try:
            user_dir = self.storage_path / f"user_{material.user_id}"
            user_dir.mkdir(exist_ok=True)
            
            file_path = user_dir / f"{material.material_id}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(material.to_dict(), f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save material to file: {e}")
            raise
    
    async def _load_material_from_file(self, material_id: str) -> Optional[ReferenceMaterial]:
        """파일에서 자료 로드"""
        try:
            # 모든 사용자 디렉토리에서 찾기
            for user_dir in self.storage_path.glob("user_*"):
                file_path = user_dir / f"{material_id}.json"
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    return ReferenceMaterial(
                        material_id=data['material_id'],
                        user_id=data['user_id'],
                        title=data['title'],
                        content=data['content'],
                        source_type=data['source_type'],
                        source_url=data.get('source_url'),
                        metadata=data.get('metadata', {}),
                        created_at=datetime.fromisoformat(data['created_at'])
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to load material from file: {e}")
            return None
    
    async def _load_user_materials_from_files(self, user_id: int) -> List[str]:
        """사용자 자료 ID 목록을 파일에서 로드"""
        try:
            user_dir = self.storage_path / f"user_{user_id}"
            if not user_dir.exists():
                return []
            
            material_ids = []
            for file_path in user_dir.glob("*.json"):
                material_id = file_path.stem
                material_ids.append(material_id)
            
            return material_ids
            
        except Exception as e:
            logger.error(f"Failed to load user materials from files: {e}")
            return []
    
    async def _delete_material_file(self, material_id: str):
        """자료 파일 삭제"""
        try:
            # 모든 사용자 디렉토리에서 찾아 삭제
            for user_dir in self.storage_path.glob("user_*"):
                file_path = user_dir / f"{material_id}.json"
                if file_path.exists():
                    file_path.unlink()
                    break
                    
        except Exception as e:
            logger.error(f"Failed to delete material file: {e}")
    
    async def get_materials_stats(self, user_id: int) -> Dict[str, Any]:
        """사용자 자료 통계 조회"""
        try:
            materials = await self.get_user_materials(user_id)
            
            stats = {
                'total_materials': len(materials),
                'by_source_type': {},
                'total_content_length': 0,
                'oldest_material': None,
                'newest_material': None
            }
            
            if not materials:
                return stats
            
            # 소스 타입별 통계
            for material in materials:
                source_type = material.source_type
                stats['by_source_type'][source_type] = \
                    stats['by_source_type'].get(source_type, 0) + 1
                
                stats['total_content_length'] += len(material.content)
            
            # 날짜 범위
            dates = [m.created_at for m in materials]
            stats['oldest_material'] = min(dates).isoformat()
            stats['newest_material'] = max(dates).isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get materials stats: {e}")
            return {'error': str(e)}


# 글로벌 레퍼런스 매니저 인스턴스
reference_manager = ReferenceManager()