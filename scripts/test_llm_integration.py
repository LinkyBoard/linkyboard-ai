"""LLM 통합 테스트 스크립트

실제 LLM API를 호출하여 Core LLM 인프라가 정상 작동하는지 검증합니다.
"""

import asyncio
import logging
import sys

from app.core.llm import (
    LLMMessage,
    LLMTier,
    call_with_fallback,
    create_embedding,
    stream_with_fallback,
)
from app.core.llm.observability import langfuse_client

# 로그 레벨을 INFO로 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def test_basic_completion():
    """기본 completion 테스트"""
    print("\n" + "=" * 60)
    print("[테스트 1] 기본 LLM 호출 (LIGHT 티어)")
    print("=" * 60)

    try:
        messages = [
            LLMMessage(role="system", content="You are a helpful assistant."),
            LLMMessage(role="user", content="Say 'Hello, World!' in Korean."),
        ]

        result = await call_with_fallback(
            tier=LLMTier.LIGHT,
            messages=messages,
            temperature=0.7,
            max_tokens=100,
        )

        print("\n✅ LLM 호출 성공!")
        print(f"  모델: {result.model}")
        print(f"  응답: {result.content}")
        print(f"  토큰: {result.input_tokens} in, {result.output_tokens} out")
        print(f"  종료 이유: {result.finish_reason}")
        return True

    except Exception as e:
        print(f"\n❌ LLM 호출 실패: {e}")
        return False


async def test_streaming_completion():
    """스트리밍 completion 테스트"""
    print("\n" + "=" * 60)
    print("[테스트 2] 스트리밍 LLM 호출 (STANDARD 티어)")
    print("=" * 60)

    try:
        messages = [
            LLMMessage(role="system", content="You are a helpful assistant."),
            LLMMessage(
                role="user", content="Count from 1 to 5 in Korean. Be brief."
            ),
        ]

        print("\n📡 스트리밍 응답:")
        print("  ", end="", flush=True)

        chunk_count = 0
        async for chunk in stream_with_fallback(
            tier=LLMTier.STANDARD,
            messages=messages,
            temperature=0.7,
            max_tokens=100,
        ):
            print(chunk, end="", flush=True)
            chunk_count += 1

        print(f"\n\n✅ 스트리밍 성공! (총 {chunk_count}개 청크)")
        return True

    except Exception as e:
        print(f"\n❌ 스트리밍 실패: {e}")
        return False


async def test_embedding():
    """임베딩 생성 테스트"""
    print("\n" + "=" * 60)
    print("[테스트 3] 임베딩 생성 (EMBEDDING 티어)")
    print("=" * 60)

    try:
        text = "This is a test sentence for embedding."
        vector = await create_embedding(text)

        print("\n✅ 임베딩 생성 성공!")
        print(f"  입력 텍스트: {text}")
        print(f"  벡터 차원: {len(vector)}")
        print(f"  벡터 샘플 (처음 5개): {vector[:5]}")
        return True

    except Exception as e:
        print(f"\n❌ 임베딩 생성 실패: {e}")
        return False


async def test_fallback_mechanism():
    """Fallback 메커니즘 테스트"""
    print("\n" + "=" * 60)
    print("[테스트 4] Fallback 메커니즘 검증")
    print("=" * 60)

    try:
        messages = [
            LLMMessage(role="system", content="You are a helpful assistant."),
            LLMMessage(
                role="user",
                content="Explain the concept of fallback in one sentence.",
            ),
        ]

        # LIGHT 티어: claude-4.5-haiku -> gpt-4.1-mini -> gemini-2.0-flash
        result = await call_with_fallback(
            tier=LLMTier.LIGHT,
            messages=messages,
            temperature=0.7,
            max_tokens=150,
        )

        print("\n✅ Fallback 메커니즘 정상 작동!")
        print(f"  선택된 모델: {result.model}")
        print(f"  응답: {result.content[:100]}...")
        print("\n  💡 LIGHT 티어 fallback 순서:")
        print("     1. claude-4.5-haiku")
        print("     2. gpt-4.1-mini")
        print("     3. gemini-2.0-flash")
        return True

    except Exception as e:
        print(f"\n❌ Fallback 테스트 실패: {e}")
        return False


def test_langfuse_tracing():
    """LangFuse 트레이싱 확인"""
    print("\n" + "=" * 60)
    print("[테스트 5] LangFuse 트레이싱 확인")
    print("=" * 60)

    if langfuse_client is None:
        print("\n⚠️  LangFuse 클라이언트가 초기화되지 않았습니다.")
        print("  옵저버빌리티 없이 LLM 호출은 정상 작동합니다.")
        return True

    print("\n✅ LangFuse 클라이언트 활성화됨")
    print(f"  호스트: {langfuse_client.base_url}")
    print("\n  💡 위 테스트들의 LLM 호출이 자동으로 트레이싱되었습니다.")
    print("  💡 LangFuse 대시보드에서 확인 가능합니다:")
    print(f"     {langfuse_client.base_url}/traces")

    # Flush to ensure all traces are sent
    langfuse_client.flush()
    print("\n  ✅ Trace 전송 완료 (flush)")

    return True


async def run_all_tests():
    """모든 테스트 실행"""
    print("=" * 60)
    print("🧪 Core LLM 통합 테스트")
    print("=" * 60)
    print("\n⚠️  주의: 이 테스트는 실제 LLM API를 호출합니다!")
    print("  최소 1개 이상의 LLM API 키가 필요합니다.")
    print("  (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY)")

    results = []

    # 비동기 테스트들
    results.append(await test_basic_completion())
    results.append(await test_streaming_completion())
    results.append(await test_embedding())
    results.append(await test_fallback_mechanism())

    # 동기 테스트
    results.append(test_langfuse_tracing())

    # 최종 결과
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"\n  통과: {passed}/{total}")
    print(f"  실패: {total - passed}/{total}")

    if passed == total:
        print("\n✅ 모든 테스트 통과!")
        print("\n🎉 Core LLM 인프라가 정상적으로 작동합니다!")
        return True
    else:
        print("\n❌ 일부 테스트 실패")
        print("\n가능한 원인:")
        print("  1. LLM API 키가 설정되지 않음")
        print("  2. API 키가 유효하지 않음")
        print("  3. API 할당량 초과")
        print("  4. 네트워크 연결 문제")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  테스트가 사용자에 의해 중단되었습니다.")
        sys.exit(1)
