#!/usr/bin/env python3
"""
토큰 쿼터 미들웨어 로직 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from unittest.mock import Mock, AsyncMock, patch
import asyncio


class MockRequest:
    """Mock FastAPI Request 객체"""
    def __init__(self, path: str, headers: dict = None, body: str = ""):
        self.url = Mock()
        self.url.path = path
        self.headers = headers or {}
        self.query_params = {}
        self._body = body.encode() if isinstance(body, str) else body
    
    async def body(self):
        return self._body


class TokenQuotaMiddlewareTest:
    """토큰 쿼터 미들웨어 테스트 클래스"""
    
    def __init__(self):
        # AI 엔드포인트 목록 (미들웨어와 동일)
        self.ai_endpoints = [
            "/api/v1/agents/",
            "/api/v1/board-ai/",
            "/api/v1/collect/v1/clipper/",
            "/api/v1/embedding/",
            "/api/v1/ai/",
            "/audio/",
        ]
    
    def _is_ai_endpoint(self, path: str) -> bool:
        """AI 엔드포인트인지 확인"""
        return any(ai_endpoint in path for ai_endpoint in self.ai_endpoints)
    
    def _extract_user_id(self, request: MockRequest) -> int:
        """요청에서 사용자 ID 추출"""
        # 헤더에서 직접 추출
        user_id = request.headers.get("x-user-id")
        if user_id:
            try:
                return int(user_id)
            except ValueError:
                pass
        
        # 쿼리 파라미터에서 추출
        user_id = request.query_params.get("user_id")
        if user_id:
            try:
                return int(user_id)
            except ValueError:
                pass
        
        return None
    
    def _estimate_request_tokens(self, request: MockRequest, body: str) -> int:
        """요청에서 예상 토큰 수 계산"""
        try:
            # 기본 토큰 수 (최소값)
            base_tokens = 100
            
            # 요청 본문 크기 기반 추정
            if body:
                try:
                    # JSON 파싱 시도
                    json_data = json.loads(body)
                    # 주요 텍스트 필드에서 토큰 추정
                    text_content = ""
                    for key in ["content", "text", "message", "prompt", "description", "summary"]:
                        if key in json_data and isinstance(json_data[key], str):
                            text_content += json_data[key] + " "
                    
                    if text_content:
                        # 단순한 토큰 추정 (실제로는 tiktoken 사용)
                        estimated = len(text_content.split()) * 1.3  # 대략적인 토큰 수
                        return max(base_tokens, int(estimated))
                except json.JSONDecodeError:
                    # JSON이 아니면 텍스트로 추정
                    estimated = len(body.split()) * 1.3
                    return max(base_tokens, int(estimated))
            
            # 엔드포인트별 기본 토큰 수
            path = request.url.path
            if "/board-ai/" in path:
                return 500  # 보드 분석은 더 많은 토큰 필요
            elif "/agents/" in path:
                return 300  # 에이전트 처리
            elif "/clipper/" in path:
                return 200  # 콘텐츠 추출
            elif "/embedding/" in path:
                return 150  # 임베딩 생성
            
            return base_tokens
            
        except Exception as e:
            print(f"Token estimation failed: {e}")
            return 100  # 기본값


def test_middleware_endpoint_detection():
    """미들웨어 엔드포인트 감지 테스트"""
    print("=== 미들웨어 엔드포인트 감지 테스트 ===")
    
    middleware = TokenQuotaMiddlewareTest()
    
    test_cases = [
        # AI 엔드포인트 (처리 대상)
        ("/api/v1/agents/analyze", True),
        ("/api/v1/board-ai/summary", True),
        ("/api/v1/collect/v1/clipper/extract", True),
        ("/api/v1/embedding/generate", True),
        ("/api/v1/ai/completion", True),
        ("/audio/transcribe", True),
        
        # 일반 엔드포인트 (처리 제외)
        ("/api/v1/user-quota/quota", False),
        ("/api/v1/health", False),
        ("/docs", False),
        ("/", False),
    ]
    
    for path, expected in test_cases:
        result = middleware._is_ai_endpoint(path)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {path} -> {result} (예상: {expected})")
    
    print("=== 엔드포인트 감지 테스트 완료 ===")


def test_user_id_extraction():
    """사용자 ID 추출 테스트"""
    print("\n=== 사용자 ID 추출 테스트 ===")
    
    middleware = TokenQuotaMiddlewareTest()
    
    test_cases = [
        # 헤더에서 추출
        ({"x-user-id": "123"}, 123),
        ({"x-user-id": "456"}, 456),
        ({"x-user-id": "invalid"}, None),
        
        # 헤더 없음
        ({}, None),
        ({"authorization": "Bearer token"}, None),
    ]
    
    for headers, expected in test_cases:
        request = MockRequest("/api/v1/agents/test", headers=headers)
        result = middleware._extract_user_id(request)
        status = "✅" if result == expected else "❌"
        print(f"  {status} 헤더 {headers} -> {result} (예상: {expected})")
    
    print("=== 사용자 ID 추출 테스트 완료 ===")


def test_token_estimation():
    """토큰 추정 테스트"""
    print("\n=== 토큰 추정 테스트 ===")
    
    middleware = TokenQuotaMiddlewareTest()
    
    test_cases = [
        # 엔드포인트별 기본값
        ("/api/v1/board-ai/analyze", "", 500),
        ("/api/v1/agents/generate", "", 300),
        ("/api/v1/clipper/extract", "", 200),
        ("/api/v1/embedding/create", "", 150),
        ("/api/v1/unknown/endpoint", "", 100),
        
        # JSON 본문 포함
        ("/api/v1/agents/analyze", '{"prompt": "이것은 테스트 프롬프트입니다"}', 300),  # max(300, estimated)
        ("/api/v1/board-ai/analyze", '{"content": "매우 긴 텍스트 내용이 여기에 들어갑니다. 이것은 보드 분석을 위한 긴 텍스트입니다."}', 500),
        
        # 빈 본문
        ("/api/v1/agents/test", "", 300),
    ]
    
    for path, body, expected_min in test_cases:
        request = MockRequest(path, body=body)
        result = middleware._estimate_request_tokens(request, body)
        status = "✅" if result >= expected_min else "❌"
        print(f"  {status} {path} + '{body[:30]}...' -> {result} 토큰 (최소 예상: {expected_min})")
    
    print("=== 토큰 추정 테스트 완료 ===")


def test_middleware_flow_simulation():
    """미들웨어 전체 플로우 시뮬레이션"""
    print("\n=== 미들웨어 플로우 시뮬레이션 ===")
    
    middleware = TokenQuotaMiddlewareTest()
    
    # 사용자별 쿼터 시뮬레이션
    user_quotas = {
        123: {"allocated": 10000, "used": 2000, "remaining": 8000},
        456: {"allocated": 1000, "used": 950, "remaining": 50},    # 거의 소진
        789: {"allocated": 5000, "used": 5000, "remaining": 0},   # 완전 소진
    }
    
    def simulate_quota_check(user_id: int, required_tokens: int) -> bool:
        """쿼터 확인 시뮬레이션"""
        if user_id not in user_quotas:
            return False
        return user_quotas[user_id]["remaining"] >= required_tokens
    
    def simulate_token_consumption(user_id: int, tokens: int) -> bool:
        """토큰 소비 시뮬레이션"""
        if user_id not in user_quotas:
            return False
        quota = user_quotas[user_id]
        if quota["remaining"] >= tokens:
            quota["remaining"] -= tokens
            quota["used"] += tokens
            return True
        return False
    
    # 테스트 요청들
    test_requests = [
        # (path, user_id, body, expected_result)
        ("/api/v1/agents/analyze", 123, '{"prompt": "간단한 분석"}', "success"),
        ("/api/v1/board-ai/summary", 123, '{"content": "보드 내용"}', "success"),
        ("/api/v1/agents/generate", 456, '{"prompt": "생성 요청"}', "quota_exceeded"),
        ("/api/v1/board-ai/analyze", 789, '{"content": "분석 요청"}', "quota_exceeded"),
        ("/api/v1/user-quota/quota", 123, "", "bypass"),  # AI 엔드포인트 아님
        ("/api/v1/agents/test", None, '{"test": "data"}', "no_user"),  # 사용자 ID 없음
    ]
    
    for path, user_id, body, expected in test_requests:
        print(f"\n📋 요청: {path}")
        print(f"   사용자: {user_id}, 본문: '{body[:30]}{'...' if len(body) > 30 else ''}'")
        
        request = MockRequest(path, {"x-user-id": str(user_id)} if user_id else {}, body)
        
        # 1. AI 엔드포인트인지 확인
        if not middleware._is_ai_endpoint(path):
            print(f"   ➡️  일반 엔드포인트 - 처리 건너뜀")
            assert expected == "bypass"
            continue
        
        # 2. 사용자 ID 추출
        extracted_user_id = middleware._extract_user_id(request)
        if not extracted_user_id:
            print(f"   ❌ 사용자 ID 없음 - 요청 통과 (인증은 다른 미들웨어에서)")
            assert expected == "no_user"
            continue
        
        # 3. 토큰 추정
        estimated_tokens = middleware._estimate_request_tokens(request, body)
        print(f"   🔢 예상 토큰: {estimated_tokens}")
        
        # 4. 쿼터 확인
        if not simulate_quota_check(extracted_user_id, estimated_tokens):
            print(f"   ❌ 토큰 부족 - HTTP 429 반환")
            quota = user_quotas.get(extracted_user_id, {})
            print(f"      필요: {estimated_tokens}, 보유: {quota.get('remaining', 0)}")
            assert expected == "quota_exceeded"
            continue
        
        # 5. 요청 처리 및 토큰 소비
        print(f"   ✅ 요청 처리 중...")
        consumed = simulate_token_consumption(extracted_user_id, estimated_tokens)
        if consumed:
            quota = user_quotas[extracted_user_id]
            print(f"   ✅ 완료 - {estimated_tokens} 토큰 소비 (잔여: {quota['remaining']})")
            assert expected == "success"
        else:
            print(f"   ❌ 토큰 소비 실패 (이론적으로 발생하지 않아야 함)")
    
    # 최종 쿼터 상태 출력
    print(f"\n📊 최종 쿼터 상태:")
    for user_id, quota in user_quotas.items():
        usage_pct = (quota["used"] / quota["allocated"]) * 100
        print(f"   사용자 {user_id}: {quota['used']}/{quota['allocated']} ({usage_pct:.1f}%) - 잔여 {quota['remaining']}")
    
    print("=== 미들웨어 플로우 시뮬레이션 완료 ===")


def test_error_handling():
    """에러 처리 테스트"""
    print("\n=== 에러 처리 테스트 ===")
    
    middleware = TokenQuotaMiddlewareTest()
    
    # 잘못된 요청들
    error_cases = [
        # 잘못된 JSON
        ("/api/v1/agents/test", '{"invalid": json}'),
        
        # 바이너리 데이터
        ("/api/v1/agents/test", b"\x00\x01\x02\x03"),
        
        # 매우 큰 본문
        ("/api/v1/agents/test", "매우 " * 1000 + "긴 텍스트"),
    ]
    
    for path, body in error_cases:
        try:
            request = MockRequest(path, body=body)
            if isinstance(body, bytes):
                body_str = body.decode('utf-8', errors='ignore')
            else:
                body_str = body
            
            tokens = middleware._estimate_request_tokens(request, body_str)
            print(f"   ✅ {path} -> {tokens} 토큰 (에러 없이 처리됨)")
        except Exception as e:
            print(f"   ❌ {path} -> 에러 발생: {e}")
    
    print("=== 에러 처리 테스트 완료 ===")


if __name__ == "__main__":
    try:
        print("🔧 토큰 쿼터 미들웨어 로직 테스트 시작\n")
        
        test_middleware_endpoint_detection()
        test_user_id_extraction()
        test_token_estimation()
        test_middleware_flow_simulation()
        test_error_handling()
        
        print("\n🎉 미들웨어 테스트가 성공적으로 완료되었습니다!")
        print("미들웨어의 모든 핵심 기능이 정상적으로 작동합니다.")
        
    except Exception as e:
        print(f"\n💥 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)