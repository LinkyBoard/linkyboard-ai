# LinkyBoard AI - 프로젝트 구조

## 개요

LinkyBoard AI는 FastAPI 기반의 현대적인 AI 콘텐츠 처리 시스템입니다. 멀티 에이전트 아키텍처와 토큰 쿼터 관리 시스템을 통해 확장 가능한 AI 서비스를 제공합니다.

## 프로젝트 메트릭스

- **총 Python 파일**: 171개
- **코드 라인 수**: ~37,801줄
- **테스트 파일**: 49개
- **주요 모듈**: 8개
- **지원 AI 제공자**: 3개 (OpenAI, Claude, Google)

---

## 디렉터리 구조

### 루트 디렉터리
```
linkyboard-ai/
├── app/                    # 메인 애플리케이션
├── tests/                  # 테스트 수트
├── docs/                   # 프로젝트 문서
├── migrations/             # 데이터베이스 마이그레이션
├── scripts/                # 유틸리티 스크립트
├── logs/                   # 로그 파일
├── data/                   # 데이터 및 참조 자료
├── htmlcov/                # 테스트 커버리지 리포트
├── docker-compose.yml      # Docker 설정
├── Dockerfile              # 컨테이너 설정
├── requirements.txt        # Python 의존성
├── Pipfile                 # Pipenv 설정
└── README.md              # 프로젝트 개요
```

---

## 메인 애플리케이션 구조 (`/app/`)

### 1. 핵심 시스템 (`/core/`)
```
core/
├── config.py              # 설정 관리
├── models.py              # 데이터베이스 모델 (877줄)
├── database.py            # 데이터베이스 연결
├── middleware.py          # 커스텀 미들웨어
├── logging.py             # 로깅 설정
├── utils/                 # 유틸리티 모듈
│   ├── dedup_detection.py # 중복 감지
│   └── observability.py   # 모니터링
└── repository/            # 데이터 저장소 패턴
    ├── base.py
    └── item_repository.py
```

**주요 데이터베이스 모델 (17개 테이블):**
- `Users` - 사용자 관리
- `Items` - 콘텐츠 저장 (벡터 임베딩 포함)
- `Categories/Tags` - 콘텐츠 분류
- `Boards` - 콘텐츠 조직화
- `BoardAnalytics` - AI 분석 결과
- `ModelCatalog` - AI 모델 관리
- `UsageMeter` - WTU 사용량 추적
- `UserTokenQuota` - 토큰 쿼터 관리
- `TokenPurchase` - 결제 이력

### 2. V2 에이전트 시스템 (`/agents/`) - **새로운 아키텍처**
```
agents/
├── core/                  # 에이전트 핵심
│   ├── base_agent.py     # 기본 에이전트 클래스
│   ├── coordinator.py    # 에이전트 조정
│   └── context_manager.py # 컨텍스트 관리
├── specialized/           # 전문 에이전트
│   ├── content_agent.py  # 콘텐츠 분석
│   ├── summary_agent.py  # 요약 생성
│   └── validator_agent.py # 품질 검증
├── routing/              # 라우팅 시스템
│   ├── smart_router.py   # V1/V2 스마트 라우팅
│   └── legacy_adapter.py # 레거시 호환성
├── reference/            # 참조 시스템
│   ├── reference_manager.py
│   └── quality_validator.py
├── router.py             # API 라우터
├── schemas.py            # 데이터 스키마
└── mode_selector.py      # 모드 선택기
```

**주요 기능:**
- 스마트 모드 선택 (Legacy/Agent/Auto)
- WTU 통합 기본 에이전트
- 컨텍스트 관리 및 조정
- 참조 기반 품질 검증

### 3. AI 처리 레이어 (`/ai/`)
```
ai/
├── providers/            # 멀티 AI 제공자
│   ├── openai_provider.py
│   ├── claude_provider.py
│   ├── google_provider.py
│   ├── interface.py      # 통합 인터페이스
│   └── router.py         # AI 라우터
├── classification/       # 분류 시스템
│   ├── category_classifier.py
│   ├── tag_extractor.py
│   └── smart_extractor.py
├── embedding/            # 임베딩 시스템
│   ├── service.py        # 임베딩 서비스
│   ├── repository.py     # 벡터 저장소
│   ├── chunking/         # 청킹 전략
│   ├── generators/       # 임베딩 생성기
│   └── processors/       # 콘텐츠 처리기
├── content_extraction/   # 콘텐츠 추출
│   ├── html_parser.py
│   ├── youtube_extractor.py
│   ├── keyword_extractor.py
│   └── recommendation_engine.py
└── recommendation/       # 추천 시스템
    ├── content_scoring.py
    ├── user_profiling.py
    └── vector_service.py
```

### 4. 토큰 쿼터 시스템 (`/metrics/`)
```
metrics/
├── token_quota_service.py  # 쿼터 관리 핵심 서비스
├── wtu_calculator.py       # WTU 계산기
├── usage_recorder.py       # 사용량 기록
├── usage_recorder_v2.py    # V2 사용량 기록
├── token_counter.py        # 토큰 카운터
├── pricing_service.py      # 가격 책정
├── model_catalog_service.py # 모델 카탈로그
└── model_policy_service.py # 모델 정책
```

**WTU (Weighted Token Unit) 시스템:**
- 모델별 가중치 적용
- 실시간 비용 추적
- 월별 쿼터 관리
- 사용량 분석

### 5. 콘텐츠 수집 (`/collect/`)
```
collect/
└── v1/
    ├── clipper/          # 웹 클리핑
    │   ├── router.py
    │   ├── service.py
    │   ├── schemas.py
    │   └── schemas_youtube.py
    └── content/          # 콘텐츠 관리
        ├── router.py
        ├── service.py
        └── schemas.py
```

### 6. 오디오 처리 (`/audio/`)
```
audio/
├── youtube_downloader.py   # YouTube 다운로드
├── youtube_stt_service.py  # STT 서비스
├── whisper_stt.py         # Whisper 통합
└── temp_file_manager.py   # 임시 파일 관리
```

### 7. 보드 관리 (`/board_ai/`, `/board_analytics/`)
```
board_ai/
├── router.py             # API 라우터
├── service.py            # 보드 AI 서비스
└── schemas.py            # 데이터 스키마

board_analytics/
└── service.py            # 보드 분석 서비스
```

### 8. 사용자 관리 (`/user_sync/`, `/user_quota/`)
```
user_sync/
├── router.py             # 사용자 동기화
├── service.py
└── schemas.py

user_quota/
├── router.py             # 쿼터 관리 API
└── schemas.py
```

---

## 테스트 구조 (`/tests/`)

### 테스트 조직화
```
tests/
├── unit/                 # 단위 테스트
│   ├── ai/              # AI 컴포넌트 테스트
│   ├── agents/          # 에이전트 테스트
│   ├── core/            # 핵심 시스템 테스트
│   ├── token_quota/     # 토큰 쿼터 테스트
│   └── ...
├── integration/          # 통합 테스트
│   ├── token_quota/     # 토큰 쿼터 통합 테스트
│   └── ...
├── functional/           # 기능 테스트
│   ├── test_board_ai_service.py
│   ├── test_clipper_service.py
│   └── ...
└── conftest.py          # 테스트 설정
```

### 테스트 전략
- **Given-When-Then** 패턴 사용
- 49개 테스트 파일
- HTML 및 XML 커버리지 리포트
- 프로바이더별 통합 테스트

---

## 문서화 (`/docs/`)

### 시스템 문서
- `SYSTEM_ARCHITECTURE.md` - 시스템 아키텍처
- `TOKEN_QUOTA_SYSTEM.md` - 토큰 쿼터 시스템
- `AGENT_SYSTEM_SUMMARY.md` - V2 에이전트 시스템
- `YOUTUBE_STT_IMPLEMENTATION.md` - YouTube STT 구현
- `BOARD_MANAGEMENT.md` - 보드 관리 시스템
- `API_INTEGRATION.md` - API 통합 가이드
- `PROJECT_STRUCTURE.md` - 프로젝트 구조 (이 문서)

---

## 데이터베이스 스키마 (`/migrations/`)

### 마이그레이션 관리
```
migrations/
├── add_token_quota_tables.sql    # 토큰 쿼터 테이블
├── add_board_management_tables.sql # 보드 관리 테이블
├── versions/                     # Alembic 버전
└── env.py                       # 마이그레이션 환경
```

### 주요 스키마 특징
- PostgreSQL 15+ with pgvector
- 1536차원 벡터 임베딩
- 복합 인덱스 최적화
- 감사 추적 (audit trail)
- Spring Boot ID 호환성

---

## 배포 및 개발

### Docker 설정
- `Dockerfile` - 애플리케이션 컨테이너
- `docker-compose.yml` - 개발 환경
- PostgreSQL with pgvector 확장

### 개발 도구
- `Makefile` - 빌드 자동화
- `pytest.ini` - 테스트 설정
- `Pipfile` - 패키지 관리
- `alembic.ini` - 데이터베이스 마이그레이션

---

## 아키텍처 강점

### 1. **모던 Python 패턴**
- async/await 전반 사용
- FastAPI 의존성 주입
- Pydantic 데이터 검증
- 구조화된 로깅

### 2. **확장 가능한 설계**
- 멀티 AI 제공자 지원
- 마이크로서비스 준비
- 모듈러 아키텍처
- 플러그인 가능한 컴포넌트

### 3. **고급 기능**
- 벡터 검색 (pgvector)
- 실시간 비용 추적 (WTU)
- 멀티 에이전트 시스템
- 참조 기반 품질 검증

### 4. **운영 준비성**
- 종합적인 로깅
- 메트릭 수집
- 헬스 체크
- 도커화 배포

---

## 혁신적 특징

### 1. **V2 에이전트 시스템**
혁신적인 멀티 에이전트 아키텍처로 AI 요청을 지능적으로 처리

### 2. **WTU 비용 모델**
정교한 AI 사용량 측정 및 비용 관리

### 3. **스마트 라우팅**
V1(레거시)와 V2(에이전트) 시스템 간 지능적 선택

### 4. **참조 검증**
참조 자료를 통한 AI 결과 품질 보증

---

## 품질 보증

### 코드 품질
- **우수한 아키텍처**: 명확한 모듈 경계
- **현대적 기술**: 최신 Python 및 FastAPI 패턴
- **포괄적 테스트**: 49개 테스트 파일
- **상세한 문서**: 아키텍처 가이드 및 API 문서

### 혁신성
- 멀티 에이전트 AI 시스템
- 정교한 비용 추적 (WTU)
- 벡터 검색 통합
- 실시간 품질 검증

이 프로젝트는 현대적이고 확장 가능한 AI 시스템으로, 프로덕션 환경에서 사용할 준비가 완료된 고품질 코드베이스입니다.