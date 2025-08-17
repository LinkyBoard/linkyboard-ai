"""
관측성(Observability) 시스템

이 모듈은 다음 기능을 제공합니다:
1. OpenTelemetry 기반 분산 추적
2. Prometheus 메트릭스 수집
3. 구조화된 로깅

주요 지표:
- ingest.request: 요청 수신 시점
- ingest.embed: 임베딩 생성 시점  
- ingest.process: 전체 처리 과정
- ai.usage: AI 모델 사용량 (WTU 포함)
"""

import time
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from opentelemetry import trace, metrics
from opentelemetry.trace import Status, StatusCode
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest

logger = logging.getLogger(__name__)

# OpenTelemetry tracer 및 meter 초기화
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Prometheus 메트릭스 정의
REGISTRY = CollectorRegistry()

# 요청 관련 메트릭스
REQUEST_COUNTER = Counter(
    'linkyboard_requests_total',
    'Total number of requests',
    ['endpoint', 'method', 'status'],
    registry=REGISTRY
)

REQUEST_DURATION = Histogram(
    'linkyboard_request_duration_seconds',
    'Request duration in seconds',
    ['endpoint', 'method'],
    registry=REGISTRY
)

# AI 관련 메트릭스  
AI_REQUESTS = Counter(
    'linkyboard_ai_requests_total',
    'Total AI API requests',
    ['model', 'operation', 'status'],
    registry=REGISTRY
)

AI_TOKENS = Counter(
    'linkyboard_ai_tokens_total',
    'Total AI tokens consumed',
    ['model', 'token_type'],  # input, output, embed
    registry=REGISTRY
)

WTU_CONSUMED = Counter(
    'linkyboard_wtu_consumed_total',
    'Total WTU consumed',
    ['user_id', 'model'],
    registry=REGISTRY
)

# 임베딩 관련 메트릭스
EMBEDDING_REQUESTS = Counter(
    'linkyboard_embedding_requests_total',
    'Total embedding requests',
    ['status'],
    registry=REGISTRY
)

EMBEDDING_CHUNKS = Histogram(
    'linkyboard_embedding_chunks',
    'Number of chunks per embedding request',
    registry=REGISTRY
)

# 데이터베이스 관련 메트릭스
DB_QUERIES = Counter(
    'linkyboard_db_queries_total',
    'Total database queries',
    ['operation', 'table'],
    registry=REGISTRY
)

DB_QUERY_DURATION = Histogram(
    'linkyboard_db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    registry=REGISTRY
)


class ObservabilityManager:
    """관측성 데이터 수집 및 관리"""
    
    def __init__(self):
        self.active_spans: Dict[str, Any] = {}
        
    @asynccontextmanager
    async def trace_request(self, operation: str, **attributes):
        """HTTP 요청 추적"""
        span_name = f"request.{operation}"
        
        with tracer.start_as_current_span(span_name) as span:
            # 기본 속성 설정
            span.set_attribute("operation", operation)
            span.set_attribute("timestamp", datetime.utcnow().isoformat())
            
            # 추가 속성 설정
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
            
            start_time = time.time()
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                span.set_attribute("duration_seconds", duration)
                
                # Prometheus 메트릭 업데이트
                REQUEST_DURATION.labels(
                    endpoint=operation,
                    method=attributes.get('method', 'unknown')
                ).observe(duration)

    @asynccontextmanager  
    async def trace_ai_operation(self, model: str, operation: str, **attributes):
        """AI 작업 추적"""
        span_name = f"ai.{operation}"
        
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("ai.model", model)
            span.set_attribute("ai.operation", operation)
            span.set_attribute("timestamp", datetime.utcnow().isoformat())
            
            for key, value in attributes.items():
                span.set_attribute(f"ai.{key}", str(value))
            
            start_time = time.time()
            status = "success"
            
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                status = "error"
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                span.set_attribute("ai.duration_seconds", duration)
                
                # Prometheus 메트릭 업데이트
                AI_REQUESTS.labels(
                    model=model,
                    operation=operation,
                    status=status
                ).inc()

    @asynccontextmanager
    async def trace_embedding_generation(self, **attributes):
        """임베딩 생성 추적"""
        span_name = "embedding.generate"
        
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("embedding.timestamp", datetime.utcnow().isoformat())
            
            for key, value in attributes.items():
                span.set_attribute(f"embedding.{key}", str(value))
            
            start_time = time.time()
            status = "success"
            
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                status = "error"
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                span.set_attribute("embedding.duration_seconds", duration)
                
                # Prometheus 메트릭 업데이트
                EMBEDDING_REQUESTS.labels(status=status).inc()
                
                # 청크 수 기록
                chunk_count = attributes.get('chunk_count', 1)
                EMBEDDING_CHUNKS.observe(chunk_count)

    def record_ai_tokens(self, model: str, input_tokens: int = 0, output_tokens: int = 0, embed_tokens: int = 0):
        """AI 토큰 사용량 기록"""
        if input_tokens > 0:
            AI_TOKENS.labels(model=model, token_type="input").inc(input_tokens)
        if output_tokens > 0:
            AI_TOKENS.labels(model=model, token_type="output").inc(output_tokens)
        if embed_tokens > 0:
            AI_TOKENS.labels(model=model, token_type="embed").inc(embed_tokens)

    def record_wtu_usage(self, user_id: int, model: str, wtu_amount: int):
        """WTU 사용량 기록"""
        WTU_CONSUMED.labels(user_id=str(user_id), model=model).inc(wtu_amount)

    def record_db_operation(self, operation: str, table: str, duration: float = None):
        """데이터베이스 작업 기록"""
        DB_QUERIES.labels(operation=operation, table=table).inc()
        
        if duration is not None:
            DB_QUERY_DURATION.labels(operation=operation, table=table).observe(duration)

    def get_metrics(self) -> bytes:
        """Prometheus 형식으로 메트릭 반환"""
        return generate_latest(REGISTRY)


# 전역 관측성 매니저 인스턴스
observability = ObservabilityManager()


# 편의 함수들
def trace_request(operation: str, **attributes):
    """요청 추적 컨텍스트 매니저"""
    return observability.trace_request(operation, **attributes)

def trace_ai_operation(model: str, operation: str, **attributes):
    """AI 작업 추적 컨텍스트 매니저"""
    return observability.trace_ai_operation(model, operation, **attributes)

def trace_embedding_generation(**attributes):
    """임베딩 생성 추적 컨텍스트 매니저"""
    return observability.trace_embedding_generation(**attributes)

def record_ai_tokens(model: str, input_tokens: int = 0, output_tokens: int = 0, embed_tokens: int = 0):
    """AI 토큰 사용량 기록"""
    observability.record_ai_tokens(model, input_tokens, output_tokens, embed_tokens)

def record_wtu_usage(user_id: int, model: str, wtu_amount: int):
    """WTU 사용량 기록"""
    observability.record_wtu_usage(user_id, model, wtu_amount)

def record_db_operation(operation: str, table: str, duration: float = None):
    """데이터베이스 작업 기록"""
    observability.record_db_operation(operation, table, duration)

def get_metrics() -> bytes:
    """Prometheus 메트릭 가져오기"""
    return observability.get_metrics()
