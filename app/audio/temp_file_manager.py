"""
Temporary File Management System

오디오 처리 과정에서 생성되는 임시 파일들을 안전하게 관리하는 모듈입니다.
자동 정리, 용량 제한, 오래된 파일 삭제 등의 기능을 제공합니다.
"""

import os
import time
import tempfile
import shutil
import threading
from typing import Dict, List, Optional, Set
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager

from app.core.logging import get_logger

logger = get_logger(__name__)


class TempFileManagerError(Exception):
    """임시 파일 관리 관련 오류"""
    pass


class TempFileInfo:
    """임시 파일 정보 클래스"""
    
    def __init__(self, path: str, created_at: float, purpose: str = "unknown"):
        self.path = path
        self.created_at = created_at
        self.purpose = purpose
        self.size_bytes = 0
        self._update_size()
    
    def _update_size(self):
        """파일 크기 업데이트"""
        try:
            if os.path.exists(self.path):
                self.size_bytes = os.path.getsize(self.path)
        except (OSError, IOError):
            self.size_bytes = 0
    
    @property
    def age_seconds(self) -> float:
        """파일 생성 후 경과 시간 (초)"""
        return time.time() - self.created_at
    
    @property
    def size_mb(self) -> float:
        """파일 크기 (MB)"""
        return self.size_bytes / (1024 * 1024)
    
    def exists(self) -> bool:
        """파일 존재 여부"""
        return os.path.exists(self.path)
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            'path': self.path,
            'created_at': self.created_at,
            'purpose': self.purpose,
            'size_bytes': self.size_bytes,
            'size_mb': self.size_mb,
            'age_seconds': self.age_seconds,
            'exists': self.exists()
        }


class TempFileManager:
    """임시 파일 관리자"""
    
    def __init__(
        self,
        base_temp_dir: Optional[str] = None,
        max_total_size_mb: float = 500.0,  # 최대 500MB
        max_file_age_hours: float = 2.0,   # 최대 2시간
        cleanup_interval_minutes: float = 10.0,  # 10분마다 정리
        auto_cleanup: bool = True
    ):
        """
        임시 파일 관리자 초기화
        
        Args:
            base_temp_dir: 기본 임시 디렉토리 (None이면 시스템 기본값)
            max_total_size_mb: 최대 총 용량 (MB)
            max_file_age_hours: 최대 파일 보관 시간 (시간)
            cleanup_interval_minutes: 자동 정리 주기 (분)
            auto_cleanup: 자동 정리 활성화 여부
        """
        self.base_temp_dir = base_temp_dir or tempfile.gettempdir()
        self.max_total_size_mb = max_total_size_mb
        self.max_file_age_hours = max_file_age_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self.auto_cleanup = auto_cleanup
        
        # 관리되는 파일들 추적
        self.managed_files: Dict[str, TempFileInfo] = {}
        self._lock = threading.Lock()
        
        # 자동 정리 스레드
        self._cleanup_thread = None
        self._stop_cleanup = False
        
        # 전용 임시 디렉토리 생성
        self.work_dir = os.path.join(self.base_temp_dir, "linkyboard_audio")
        self._ensure_work_directory()
        
        if self.auto_cleanup:
            self._start_auto_cleanup()
        
        logger.info(
            f"TempFileManager 초기화: work_dir={self.work_dir}, "
            f"max_size={max_total_size_mb}MB, max_age={max_file_age_hours}h"
        )
    
    def _ensure_work_directory(self):
        """작업 디렉토리 생성 보장"""
        try:
            os.makedirs(self.work_dir, exist_ok=True)
            logger.debug(f"작업 디렉토리 확인/생성: {self.work_dir}")
        except Exception as e:
            error_msg = f"작업 디렉토리 생성 실패: {self.work_dir}, {str(e)}"
            logger.error(error_msg)
            raise TempFileManagerError(error_msg)
    
    def create_temp_file(
        self,
        prefix: str = "temp_",
        suffix: str = "",
        purpose: str = "unknown"
    ) -> str:
        """
        새 임시 파일 경로 생성 및 추적 시작
        
        Args:
            prefix: 파일명 접두사
            suffix: 파일명 접미사 (확장자 포함)
            purpose: 파일 용도 설명
            
        Returns:
            str: 생성된 임시 파일 경로
        """
        try:
            # 고유한 파일명 생성
            timestamp = int(time.time() * 1000)
            thread_id = threading.get_ident() % 10000
            filename = f"{prefix}{timestamp}_{thread_id}{suffix}"
            file_path = os.path.join(self.work_dir, filename)
            
            # 파일 정보 등록
            with self._lock:
                file_info = TempFileInfo(file_path, time.time(), purpose)
                self.managed_files[file_path] = file_info
            
            logger.debug(f"임시 파일 생성: {file_path} (용도: {purpose})")
            return file_path
            
        except Exception as e:
            error_msg = f"임시 파일 생성 실패: {str(e)}"
            logger.error(error_msg)
            raise TempFileManagerError(error_msg)
    
    def register_file(self, file_path: str, purpose: str = "external") -> bool:
        """
        외부에서 생성된 파일을 관리 대상으로 등록
        
        Args:
            file_path: 등록할 파일 경로
            purpose: 파일 용도
            
        Returns:
            bool: 등록 성공 여부
        """
        try:
            with self._lock:
                if file_path not in self.managed_files:
                    file_info = TempFileInfo(file_path, time.time(), purpose)
                    self.managed_files[file_path] = file_info
                    logger.debug(f"외부 파일 등록: {file_path} (용도: {purpose})")
                    return True
            return False
        except Exception as e:
            logger.error(f"파일 등록 실패 {file_path}: {e}")
            return False
    
    def unregister_file(self, file_path: str, delete_file: bool = True) -> bool:
        """
        파일을 관리 대상에서 제거
        
        Args:
            file_path: 제거할 파일 경로
            delete_file: 실제 파일도 삭제할지 여부
            
        Returns:
            bool: 제거 성공 여부
        """
        try:
            with self._lock:
                if file_path in self.managed_files:
                    if delete_file and os.path.exists(file_path):
                        os.remove(file_path)
                        logger.debug(f"임시 파일 삭제: {file_path}")
                    
                    del self.managed_files[file_path]
                    return True
            return False
        except Exception as e:
            logger.error(f"파일 제거 실패 {file_path}: {e}")
            return False
    
    def cleanup_file(self, file_path: str) -> bool:
        """특정 파일 정리"""
        return self.unregister_file(file_path, delete_file=True)
    
    def cleanup_expired_files(self) -> Dict[str, int]:
        """만료된 파일들 정리"""
        max_age_seconds = self.max_file_age_hours * 3600
        current_time = time.time()
        
        expired_files = []
        
        with self._lock:
            for file_path, file_info in list(self.managed_files.items()):
                if current_time - file_info.created_at > max_age_seconds:
                    expired_files.append(file_path)
        
        # 락 밖에서 파일 삭제 (I/O 작업 최소화)
        cleanup_results = {
            'deleted_count': 0,
            'failed_count': 0,
            'freed_bytes': 0
        }
        
        for file_path in expired_files:
            try:
                file_size = 0
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    
                if self.unregister_file(file_path, delete_file=True):
                    cleanup_results['deleted_count'] += 1
                    cleanup_results['freed_bytes'] += file_size
                else:
                    cleanup_results['failed_count'] += 1
                    
            except Exception as e:
                logger.warning(f"만료 파일 삭제 실패 {file_path}: {e}")
                cleanup_results['failed_count'] += 1
        
        if cleanup_results['deleted_count'] > 0:
            logger.info(
                f"만료 파일 정리 완료: {cleanup_results['deleted_count']}개 삭제, "
                f"{cleanup_results['freed_bytes'] / 1024 / 1024:.1f}MB 확보"
            )
        
        return cleanup_results
    
    def cleanup_oversized_files(self) -> Dict[str, int]:
        """용량 초과 시 오래된 파일부터 정리"""
        current_total_mb = self.get_total_size_mb()
        
        if current_total_mb <= self.max_total_size_mb:
            return {'deleted_count': 0, 'failed_count': 0, 'freed_bytes': 0}
        
        # 파일들을 생성 시간 순으로 정렬 (오래된 것부터)
        with self._lock:
            sorted_files = sorted(
                self.managed_files.items(),
                key=lambda x: x[1].created_at
            )
        
        cleanup_results = {
            'deleted_count': 0,
            'failed_count': 0,
            'freed_bytes': 0
        }
        
        target_delete_mb = current_total_mb - self.max_total_size_mb
        deleted_mb = 0.0
        
        for file_path, file_info in sorted_files:
            if deleted_mb >= target_delete_mb:
                break
            
            try:
                file_size = file_info.size_bytes
                if self.unregister_file(file_path, delete_file=True):
                    cleanup_results['deleted_count'] += 1
                    cleanup_results['freed_bytes'] += file_size
                    deleted_mb += file_size / 1024 / 1024
                else:
                    cleanup_results['failed_count'] += 1
                    
            except Exception as e:
                logger.warning(f"용량 정리 중 파일 삭제 실패 {file_path}: {e}")
                cleanup_results['failed_count'] += 1
        
        if cleanup_results['deleted_count'] > 0:
            logger.info(
                f"용량 정리 완료: {cleanup_results['deleted_count']}개 삭제, "
                f"{cleanup_results['freed_bytes'] / 1024 / 1024:.1f}MB 확보"
            )
        
        return cleanup_results
    
    def cleanup_all(self) -> Dict[str, int]:
        """모든 관리 파일 정리"""
        with self._lock:
            all_files = list(self.managed_files.keys())
        
        cleanup_results = {
            'deleted_count': 0,
            'failed_count': 0,
            'freed_bytes': 0
        }
        
        for file_path in all_files:
            try:
                file_size = 0
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                
                if self.unregister_file(file_path, delete_file=True):
                    cleanup_results['deleted_count'] += 1
                    cleanup_results['freed_bytes'] += file_size
                else:
                    cleanup_results['failed_count'] += 1
                    
            except Exception as e:
                logger.warning(f"전체 정리 중 파일 삭제 실패 {file_path}: {e}")
                cleanup_results['failed_count'] += 1
        
        logger.info(
            f"전체 파일 정리 완료: {cleanup_results['deleted_count']}개 삭제, "
            f"{cleanup_results['freed_bytes'] / 1024 / 1024:.1f}MB 확보"
        )
        
        return cleanup_results
    
    def get_managed_files(self) -> List[Dict]:
        """관리 중인 파일 목록 반환"""
        with self._lock:
            return [info.to_dict() for info in self.managed_files.values()]
    
    def get_total_size_mb(self) -> float:
        """총 관리 파일 크기 (MB)"""
        total_bytes = 0
        with self._lock:
            for file_info in self.managed_files.values():
                file_info._update_size()  # 최신 크기로 업데이트
                total_bytes += file_info.size_bytes
        
        return total_bytes / 1024 / 1024
    
    def get_stats(self) -> Dict:
        """관리 통계 반환"""
        with self._lock:
            file_count = len(self.managed_files)
            purposes = {}
            
            for file_info in self.managed_files.values():
                file_info._update_size()
                purpose = file_info.purpose
                purposes[purpose] = purposes.get(purpose, 0) + 1
        
        return {
            'total_files': file_count,
            'total_size_mb': self.get_total_size_mb(),
            'max_size_mb': self.max_total_size_mb,
            'max_age_hours': self.max_file_age_hours,
            'work_directory': self.work_dir,
            'files_by_purpose': purposes,
            'auto_cleanup_enabled': self.auto_cleanup
        }
    
    def _start_auto_cleanup(self):
        """자동 정리 스레드 시작"""
        if self._cleanup_thread is not None:
            return
        
        def cleanup_worker():
            while not self._stop_cleanup:
                try:
                    # 만료된 파일 정리
                    self.cleanup_expired_files()
                    
                    # 용량 초과 시 정리
                    self.cleanup_oversized_files()
                    
                    # 정리 주기만큼 대기
                    wait_seconds = self.cleanup_interval_minutes * 60
                    for _ in range(int(wait_seconds)):
                        if self._stop_cleanup:
                            break
                        time.sleep(1)
                        
                except Exception as e:
                    logger.error(f"자동 정리 중 오류: {e}")
                    time.sleep(30)  # 오류 시 30초 대기 후 재시도
        
        self._stop_cleanup = False
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("자동 임시 파일 정리 스레드 시작")
    
    def _stop_auto_cleanup(self):
        """자동 정리 스레드 중지"""
        if self._cleanup_thread is not None:
            self._stop_cleanup = True
            self._cleanup_thread.join(timeout=5.0)
            self._cleanup_thread = None
            logger.info("자동 임시 파일 정리 스레드 종료")
    
    @contextmanager
    def managed_temp_file(self, prefix: str = "temp_", suffix: str = "", purpose: str = "context"):
        """
        컨텍스트 매니저로 임시 파일 관리
        
        Usage:
            with temp_manager.managed_temp_file(".mp3", "audio_download") as file_path:
                # 파일 사용
                pass
            # 자동으로 파일 정리됨
        """
        file_path = self.create_temp_file(prefix, suffix, purpose)
        try:
            yield file_path
        finally:
            self.cleanup_file(file_path)
    
    def __del__(self):
        """소멸자: 정리 작업"""
        try:
            self._stop_auto_cleanup()
            # 전체 정리는 하지 않음 (다른 인스턴스가 사용 중일 수 있음)
        except:
            pass  # 소멸자에서는 오류를 무시


# 글로벌 인스턴스 (싱글턴 패턴)
_global_temp_manager: Optional[TempFileManager] = None
_manager_lock = threading.Lock()


def get_temp_manager() -> TempFileManager:
    """글로벌 임시 파일 관리자 인스턴스 반환"""
    global _global_temp_manager
    
    if _global_temp_manager is None:
        with _manager_lock:
            if _global_temp_manager is None:
                _global_temp_manager = TempFileManager()
    
    return _global_temp_manager