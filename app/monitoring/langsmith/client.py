"""
LangSmith 클라이언트 설정 및 초기화

AI 호출 추적, 성능 모니터링, 디버깅을 위한 LangSmith 클라이언트를 설정합니다.
"""

import os
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import asyncio
from datetime import datetime
import logging

from langsmith import Client, traceable
from langsmith.wrappers import wrap_openai
from langsmith.run_helpers import tracing_context

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LangSmithManager:
    """LangSmith 관리자 클래스"""
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._is_enabled = False
        self._project_name = settings.LANGCHAIN_PROJECT
        
    def initialize(self) -> bool:
        """LangSmith 클라이언트 초기화"""
        try:
            # 환경 변수 설정
            if settings.LANGCHAIN_API_KEY:
                os.environ["LANGCHAIN_TRACING_V2"] = str(settings.LANGCHAIN_TRACING_V2).lower()
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
                os.environ["LANGCHAIN_PROJECT"] = self._project_name
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
                
                # 클라이언트 생성
                self._client = Client(
                    api_key=settings.LANGCHAIN_API_KEY,
                    api_url=settings.LANGCHAIN_ENDPOINT
                )
                
                # 프로젝트 생성 (존재하지 않는 경우)
                self._ensure_project_exists()
                
                self._is_enabled = True
                logger.info(f"LangSmith initialized successfully for project: {self._project_name}")
                return True
            else:
                logger.warning("LANGCHAIN_API_KEY not provided, LangSmith monitoring disabled")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith: {e}")
            self._is_enabled = False
            return False
    
    def _ensure_project_exists(self):
        """프로젝트 존재 확인 및 생성"""
        try:
            if self._client:
                # 프로젝트가 존재하는지 확인
                projects = list(self._client.list_projects())
                project_names = [p.name for p in projects]
                
                if self._project_name not in project_names:
                    # 프로젝트 생성
                    self._client.create_project(
                        project_name=self._project_name,
                        description=f"LinkyBoard AI 모니터링 프로젝트 - {datetime.now().isoformat()}"
                    )
                    logger.info(f"Created new LangSmith project: {self._project_name}")
                else:
                    logger.info(f"Using existing LangSmith project: {self._project_name}")
        except Exception as e:
            logger.warning(f"Could not verify/create project: {e}")
    
    @property
    def is_enabled(self) -> bool:
        """LangSmith 활성화 여부"""
        return self._is_enabled
    
    @property
    def client(self) -> Optional[Client]:
        """LangSmith 클라이언트 반환"""
        return self._client
    
    def get_project_url(self) -> Optional[str]:
        """프로젝트 URL 반환"""
        if self._is_enabled:
            return f"{settings.LANGCHAIN_ENDPOINT}/projects/{self._project_name}"
        return None
    
    @contextmanager
    def trace_context(self, 
                     run_name: str,
                     run_type: str = "chain",
                     inputs: Dict[str, Any] = None,
                     extra: Dict[str, Any] = None):
        """
        추적 컨텍스트 매니저
        
        Args:
            run_name: 실행 이름
            run_type: 실행 타입 (chain, llm, tool, retriever 등)
            inputs: 입력 데이터
            extra: 추가 메타데이터
        """
        if not self._is_enabled:
            yield None
            return
        
        extra_data = extra or {}
        extra_data.update({
            "timestamp": datetime.now().isoformat(),
            "project": self._project_name,
            "user_agent": "LinkyBoard-AI"
        })
        
        try:
            with tracing_context(
                name=run_name,
                run_type=run_type,
                inputs=inputs or {},
                extra=extra_data,
                project_name=self._project_name
            ) as run_context:
                yield run_context
        except Exception as e:
            logger.error(f"Error in trace context: {e}")
            yield None
    
    def log_feedback(self, 
                    run_id: str,
                    score: float,
                    feedback_type: str = "user_score",
                    comment: Optional[str] = None):
        """
        사용자 피드백 로깅
        
        Args:
            run_id: 실행 ID
            score: 점수 (0.0-1.0)
            feedback_type: 피드백 타입
            comment: 추가 코멘트
        """
        if not self._is_enabled or not self._client:
            return
        
        try:
            self._client.create_feedback(
                run_id=run_id,
                key=feedback_type,
                score=score,
                comment=comment
            )
            logger.info(f"Logged feedback for run {run_id}: {score}")
        except Exception as e:
            logger.error(f"Failed to log feedback: {e}")
    
    def create_dataset(self, 
                      dataset_name: str,
                      description: Optional[str] = None,
                      examples: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
        """
        데이터셋 생성
        
        Args:
            dataset_name: 데이터셋 이름
            description: 설명
            examples: 예제 데이터
            
        Returns:
            생성된 데이터셋 ID
        """
        if not self._is_enabled or not self._client:
            return None
        
        try:
            dataset = self._client.create_dataset(
                dataset_name=dataset_name,
                description=description or f"LinkyBoard AI 데이터셋 - {datetime.now().isoformat()}"
            )
            
            # 예제 데이터 추가
            if examples:
                for example in examples:
                    self._client.create_example(
                        dataset_id=dataset.id,
                        inputs=example.get("inputs", {}),
                        outputs=example.get("outputs", {}),
                        metadata=example.get("metadata", {})
                    )
            
            logger.info(f"Created dataset: {dataset_name} (ID: {dataset.id})")
            return str(dataset.id)
            
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            return None
    
    def get_run_stats(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        실행 통계 조회
        
        Args:
            project_name: 프로젝트 이름 (기본값: 현재 프로젝트)
            
        Returns:
            실행 통계 딕셔너리
        """
        if not self._is_enabled or not self._client:
            return {}
        
        try:
            project_name = project_name or self._project_name
            runs = list(self._client.list_runs(
                project_name=project_name,
                limit=100
            ))
            
            stats = {
                "total_runs": len(runs),
                "successful_runs": sum(1 for run in runs if not run.error),
                "failed_runs": sum(1 for run in runs if run.error),
                "avg_latency_ms": 0,
                "total_tokens": 0
            }
            
            if runs:
                total_latency = sum((run.end_time - run.start_time).total_seconds() * 1000 
                                 for run in runs if run.end_time and run.start_time)
                stats["avg_latency_ms"] = total_latency / len(runs)
                
                # 토큰 사용량 집계
                for run in runs:
                    if run.outputs and isinstance(run.outputs, dict):
                        usage = run.outputs.get("usage", {})
                        if isinstance(usage, dict):
                            stats["total_tokens"] += usage.get("total_tokens", 0)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get run stats: {e}")
            return {}


# 전역 LangSmith 관리자 인스턴스
langsmith_manager = LangSmithManager()


def get_langsmith_client() -> Optional[Client]:
    """LangSmith 클라이언트 반환"""
    return langsmith_manager.client


def is_langsmith_enabled() -> bool:
    """LangSmith 활성화 여부 확인"""
    return langsmith_manager.is_enabled


def trace_ai_operation(operation_name: str, **kwargs):
    """AI 작업 추적 데코레이터"""
    if not langsmith_manager.is_enabled:
        def decorator(func):
            return func
        return decorator
    
    return traceable(
        name=operation_name,
        run_type="chain",
        **kwargs
    )


# 초기화
def initialize_langsmith():
    """LangSmith 초기화 함수"""
    return langsmith_manager.initialize()