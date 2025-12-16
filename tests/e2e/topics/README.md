# Topics E2E Tests

Topics 오케스트레이션 End-to-End 테스트

## 테스트 구조

### Mock AI Tests (`test_topics_mock.py`)
- **목적**: 빠른 CI/CD 검증, 비용 없음
- **특징**: LLM 호출 모킹, 예측 가능한 출력
- **실행**: 기본 테스트 실행 시 자동 포함
- **테스트 수**: 6개

### Real AI Tests (`test_topics_real.py`)
- **목적**: 실제 LLM API 동작 검증
- **특징**: 실제 OpenAI/Anthropic API 호출, 비용 발생
- **실행**: 수동 실행, 환경 변수 게이트
- **테스트 수**: 5개

---

## 실행 방법

### 1. Mock AI 테스트 (기본)

```bash
# 전체 Topics 테스트 (Mock AI만)
pytest tests/unit/domains/topics/ tests/integration/topics/ tests/e2e/topics/ -v

# E2E Mock 테스트만
pytest tests/e2e/topics/test_topics_mock.py -v

# 또는 make 명령
make test-topics
```

**결과**: 91 passed, 5 skipped (Real AI 제외)

### 2. Real AI 테스트 (수동)

```bash
# 환경 변수 설정 후 Real AI 테스트 실행
ENABLE_REAL_AI_TESTS=true pytest tests/e2e/topics/test_topics_real.py -v -s

# 또는 특정 테스트만
ENABLE_REAL_AI_TESTS=true pytest tests/e2e/topics/test_topics_real.py::test_real_draft_creation_basic -v -s
```

**주의사항**:
- ⚠️ **비용 발생**: 실제 LLM API 호출로 토큰 비용 발생
- 📊 **WTU 로깅**: `-s` 옵션으로 사용량 출력 확인
- 🔑 **API Key 필요**: 환경 변수에 OpenAI/Anthropic API Key 설정

### 3. 모든 테스트 (Mock + Real AI)

```bash
# Mock AI와 Real AI 모두 실행
ENABLE_REAL_AI_TESTS=true pytest tests/unit/domains/topics/ tests/integration/topics/ tests/e2e/topics/ -v -s
```

**결과**: 96 passed

---

## Real AI 테스트 상세

### test_real_draft_creation_basic
- **검증**: 기본 Draft 생성 플로우
- **프롬프트**: "Write a brief introduction about quantum computing fundamentals"
- **예상 비용**: ~1-2 WTU (gpt-4o-mini 기준)

### test_real_draft_with_multiple_contents
- **검증**: 다수 콘텐츠 통합 처리
- **콘텐츠**: 3개 (Asyncio, Async/Await, Concurrency)
- **예상 비용**: ~2-3 WTU

### test_real_streaming_flow
- **검증**: SSE 스트리밍 동작
- **프롬프트**: "Write about REST API best practices"
- **예상 비용**: ~1-2 WTU

### test_real_draft_empty_contents
- **검증**: 콘텐츠 없이 Writer 단독 동작
- **프롬프트**: "Write a short essay about the importance of software testing"
- **예상 비용**: ~1 WTU

### test_real_draft_output_quality
- **검증**: 마크다운 형식, Title 추출
- **프롬프트**: "Create a structured document about database indexing strategies"
- **예상 비용**: ~1-2 WTU

**총 예상 비용**: ~6-10 WTU (전체 Real AI 테스트 실행 시)

---

## 환경 설정

### API Key 설정

```bash
# .env 파일에 추가
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### pytest.ini 설정 (이미 적용됨)

```ini
[pytest]
markers =
    real_ai: Tests that call real AI APIs (costs money)
    mock_ai: Tests that use mocked AI (default, free)

# 기본 실행 시 real_ai 제외
addopts = -m "not real_ai"
```

---

## CI/CD 통합

### Pre-commit Hook
- Mock AI 테스트만 자동 실행
- Real AI 테스트 제외 (비용, 속도)

### GitHub Actions
```yaml
# .github/workflows/test.yml
- name: Run Tests
  run: |
    make test  # Mock AI만, Real AI 제외
```

### 수동 검증 (로컬)
```bash
# 배포 전 Real AI 동작 확인
ENABLE_REAL_AI_TESTS=true pytest -m real_ai -v -s
```

---

## 트러블슈팅

### Real AI 테스트가 스킵되는 경우

```bash
# 환경 변수 확인
echo $ENABLE_REAL_AI_TESTS

# 명시적으로 설정
export ENABLE_REAL_AI_TESTS=true
pytest tests/e2e/topics/test_topics_real.py -v
```

### API Key 에러

```bash
# .env 파일 확인
cat .env | grep API_KEY

# 환경 변수 로드 확인
python -c "import os; print(os.getenv('OPENAI_API_KEY'))"
```

### WTU 사용량 확인

```bash
# -s 옵션으로 stdout 출력 확인
ENABLE_REAL_AI_TESTS=true pytest tests/e2e/topics/test_topics_real.py -v -s
```

---

## 테스트 커버리지

### Mock AI Tests
- ✅ 전체 플로우 검증 (Orchestrator → Executor → Agents)
- ✅ Context 누적 (Stage 1 → Stage 2)
- ✅ Usage/WTU 계산
- ✅ Title 추출
- ✅ SSE 스트리밍
- ✅ 에러 처리 (LLM 실패, Agent 스킵)

### Real AI Tests
- ✅ 실제 LLM 출력 품질
- ✅ 마크다운 구조
- ✅ 의미 있는 콘텐츠 생성
- ✅ 실제 토큰 사용량
- ✅ 스트리밍 동작

---

## 참고

- **테스트 플랜**: `~/.claude/plans/glistening-scribbling-turing.md`
- **구현 코드**: `app/domains/topics/`
- **Mock Fixtures**: `tests/conftest.py`
