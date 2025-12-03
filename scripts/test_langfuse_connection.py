"""LangFuse 연결 테스트 스크립트"""

import logging
import sys

from app.core.config import settings
from app.core.llm.observability import langfuse_client

# 로그 레벨을 INFO로 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def test_langfuse_connection():
    """LangFuse 연결 테스트"""
    print("=" * 60)
    print("LangFuse 연결 테스트")
    print("=" * 60)

    # 설정 확인
    print("\n[1] 환경 변수 설정:")
    print(
        f"  LANGFUSE_SECRET_KEY: ({len(settings.langfuse_secret_key)} chars)"
    )
    print(
        f"  LANGFUSE_PUBLIC_KEY: ({len(settings.langfuse_public_key)} chars)"
    )
    print(f"  LANGFUSE_HOST: {settings.langfuse_host}")

    # 클라이언트 확인
    print("\n[2] LangFuse 클라이언트 상태:")
    if langfuse_client is None:
        print("  ❌ LangFuse 클라이언트가 초기화되지 않았습니다.")
        print("  → observability.py의 initialize_langfuse() 실패")
        return False
    else:
        print("  ✅ LangFuse 클라이언트 초기화 성공")

    # 실제 연결 테스트
    print("\n[3] LangFuse 대시보드 연결 테스트:")
    try:
        # Trace 생성 테스트
        trace = langfuse_client.trace(name="test-connection")
        print(f"  ✅ Trace 생성 성공: {trace.id}")

        # Generation 생성 테스트
        generation = trace.generation(
            name="test-generation",
            model="test-model",
            input={"test": "input"},
            output={"test": "output"},
        )
        print(f"  ✅ Generation 생성 성공: {generation.id}")

        # 명시적으로 flush
        langfuse_client.flush()
        print("  ✅ LangFuse flush 완료")

        print("\n[결과] ✅ LangFuse 대시보드와 정상 연결되었습니다!")
        dashboard_url = (
            f"{settings.langfuse_host}/project/default/traces/{trace.id}"
        )
        print(f"\n대시보드 확인: {dashboard_url}")
        return True

    except Exception as e:
        print(f"  ❌ 연결 실패: {e}")
        print("\n[결과] ❌ LangFuse 대시보드 연결 실패")
        print("\n가능한 원인:")
        print("  1. API 키가 올바르지 않음")
        print("  2. LangFuse 프로젝트가 존재하지 않음")
        print("  3. HOST URL이 올바르지 않음")
        return False


if __name__ == "__main__":
    success = test_langfuse_connection()
    sys.exit(0 if success else 1)
