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

실제 LLM API를 호출하여 통합 테스트를 수행합니다.

```bash
make test-llm
```

**확인 사항:**
- Core LLM 공개 API import
- 기본 LLM 호출 (티어 기반 fallback)
- 임베딩 생성
- LangFuse 트레이싱

**필요한 환경 변수:**
```bash
# 최소 1개 이상 필요
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

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
