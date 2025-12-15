# Scripts

개발 및 테스트를 위한 유틸리티 스크립트 모음입니다.

## LLM & Observability 테스트

### LangFuse 연결 테스트

LangFuse 대시보드 연결 상태를 확인합니다.

```bash
make test-langfuse
```

**확인 사항:**
- LangFuse 클라이언트 초기화
- Trace 생성 가능 여부
- 대시보드 URL 제공

**필요한 환경 변수:**
```bash
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

### LLM 통합 테스트

실제 LLM API를 호출하여 Core LLM 인프라가 정상 작동하는지 검증합니다.

```bash
make test-llm
```

**테스트 항목:**
1. 기본 LLM 호출 (LIGHT 티어)
2. 스트리밍 LLM 호출 (STANDARD 티어)
3. 임베딩 생성 (EMBEDDING 티어)
4. Fallback 메커니즘 검증
5. LangFuse 트레이싱 확인

**필요한 환경 변수:**
```bash
# 최소 1개 이상 필요
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...

# 선택사항 (트레이싱)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

**주의사항:**
- 실제 API를 호출하므로 비용이 발생할 수 있습니다
- 최소한의 토큰만 사용하도록 설계되었습니다

## 사용법

### 직접 실행
```bash
# PYTHONPATH 설정 필요
PYTHONPATH=. poetry run python scripts/test_langfuse_connection.py
```

### Makefile 사용 (권장)
```bash
# Makefile이 자동으로 PYTHONPATH 설정
make test-langfuse
make test-llm
```

## 추가 예정

- `test_model_catalog.py`: 모델 카탈로그 검증
- `benchmark_llm.py`: LLM 호출 성능 측정
- `check_api_keys.py`: API 키 유효성 검증
