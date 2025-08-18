# LinkyBoard AI

링키보드 AI 서비스의 백엔드 API

## 주요 기능

- 웹 콘텐츠 클리핑 및 처리
- AI 기반 콘텐츠 분석 및 요약
- 벡터 임베딩을 통한 의미적 검색
- 사용자별 개인화 AI 서비스
- WTU(Weighted Token Unit) 기반 사용량 계측

## AI 모델 카탈로그 관리

### 개요

LinkyBoard AI는 다양한 AI 모델을 지원하며, 각 모델의 가격 정보와 WTU 가중치를 관리합니다.

### 지원 모델 타입

- **LLM**: 텍스트 생성 모델 (GPT-4, Claude 등)
- **Embedding**: 벡터 임베딩 모델 (text-embedding-3-small 등)

### 모델 관리 명령어

#### 1. 현재 모델 정보 확인

```bash
make models-check
```

#### 2. 새 데이터베이스에 초기 모델 설정

```bash
make models-init
```

#### 3. Dev에서 Prod로 모델 동기화

```bash
make models-sync-to-prod
```

#### 4. JSON 파일에서 모델 데이터 로드

```bash
make models-from-file file=model_catalog_data.json
```

### 초기 설정 모델

#### 1. GPT-4o Mini

- **Provider**: OpenAI
- **Type**: LLM
- **가격**: 입력 $0.15/1M tokens, 출력 $0.6/1M tokens
- **WTU 가중치**: 입력 0.6, 출력 2.4

#### 2. Text Embedding 3 Small

- **Provider**: OpenAI
- **Type**: Embedding
- **가격**: $0.02/1M tokens
- **WTU 가중치**: 0.064

### 자동 초기화

앱이 시작될 때 자동으로 모델 카탈로그를 확인하고, 활성 모델이 없는 경우 초기 데이터를 삽입합니다.

### 수동 모델 관리

더 세밀한 모델 관리가 필요한 경우 다음 스크립트를 직접 사용할 수 있습니다:

```bash
# 초기 설정
python scripts/manage_model_catalog.py --action init --database-url "postgresql://..."

# Dev에서 동기화
python scripts/manage_model_catalog.py --action sync \
  --database-url "postgresql://...prod" \
  --dev-database-url "postgresql://...dev"

# 파일에서 로드
python scripts/manage_model_catalog.py --action from-file \
  --database-url "postgresql://..." \
  --file model_data.json
```

## 개발 환경 설정

### 필수 요구사항

- Python 3.12+
- PostgreSQL 15+
- pgvector 확장

### 설치 및 실행

```bash
# 의존성 설치
pipenv install

# 데이터베이스 마이그레이션
make upgrade

# 개발 서버 실행
make run
```

## 프로덕션 배포

### 데이터베이스 마이그레이션

```bash
# 프로덕션 마이그레이션
make upgrade-prod

# 모델 카탈로그 동기화
make models-sync-to-prod
```

## 테스트

```bash
# 전체 테스트 실행
make test

# 단위 테스트만
make test-unit

# 커버리지 리포트 생성
make test-cov
```
