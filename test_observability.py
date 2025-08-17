#!/usr/bin/env python3
"""
관측성 시스템 테스트
"""
import asyncio
from app.observability import trace_request, trace_ai_operation, get_metrics

async def test_observability():
    print("=== 관측성 시스템 테스트 ===")
    
    # 1. 요청 추적 테스트
    async with trace_request("test_operation", method="POST", user_id=123) as span:
        print("요청 추적 중...")
        await asyncio.sleep(0.1)  # 시뮬레이션
        span.set_attribute("test_attribute", "test_value")
        print("요청 추적 완료")
    
    # 2. AI 작업 추적 테스트  
    async with trace_ai_operation("gpt-3.5-turbo", "test_generation", user_id=123) as span:
        print("AI 작업 추적 중...")
        await asyncio.sleep(0.05)  # 시뮬레이션
        span.set_attribute("ai.tokens", 100)
        print("AI 작업 추적 완료")
    
    # 3. 메트릭 확인
    print("\n=== Prometheus 메트릭 ===")
    metrics_data = get_metrics()
    print(f"메트릭 데이터 크기: {len(metrics_data)} bytes")
    
    # 메트릭 내용 일부 출력
    metrics_str = metrics_data.decode('utf-8')
    lines = metrics_str.split('\n')
    for line in lines[:20]:  # 처음 20줄만 출력
        if line.strip() and not line.startswith('#'):
            print(f"  {line}")
    
    print("\n관측성 시스템 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_observability())
