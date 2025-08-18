# LinkyBoard AI API 연동 가이드

이 문서는 Spring Boot 서버에서 LinkyBoard AI API와 연동하기 위한 가이드입니다.

## 🚀 개요

LinkyBoard AI API는 다음 핵심 기능을 제공합니다:
- **사용자 동기화**: Spring Boot 사용자 정보를 AI 서비스로 동기화
- **Board AI**: 보드 문맥 기반 AI 질의/초안 생성
- **Clipper**: 웹페이지 수집 및 AI 분석

## 📋 API 목록

### 1. User Sync API (사용자 동기화)
Spring Boot에서 사용자 관리 시 호출하는 API

#### 1.1 사용자 동기화
```http
POST /user-sync/sync
Content-Type: application/json

{
    "user_id": 123,
    "is_active": true
}
```

**응답 예시:**
```json
{
    "success": true,
    "message": "사용자 123가 성공적으로 생성되었습니다.",
    "user_id": 123,
    "created": true,
    "last_sync_at": "2025-08-18T07:06:48.222178"
}
```

**사용 시나리오:**
- 새 사용자 가입 시
- 사용자 정보 변경 시
- 정기적인 사용자 동기화

#### 1.2 사용자 상태 변경
```http
PUT /user-sync/status
Content-Type: application/json

{
    "user_id": 123,
    "is_active": false
}
```

**응답 예시:**
```json
{
    "success": true,
    "message": "사용자 123가 성공적으로 비활성화되었습니다.",
    "user_id": 123,
    "is_active": false
}
```

**사용 시나리오:**
- 사용자 탈퇴 시 (`is_active`: false)
- 사용자 계정 복구 시 (`is_active`: true)
- 관리자의 사용자 상태 변경

#### 1.3 사용자 상태 조회
```http
GET /user-sync/status/{user_id}
```

**응답 예시:**
```json
{
    "user_id": 123,
    "is_active": true,
    "ai_preferences": null,
    "embedding_model_version": null,
    "last_sync_at": "2025-08-18T07:06:48.222178+00:00",
    "created_at": "2025-08-18T07:06:48.215149+00:00",
    "updated_at": null
}
```

**참고사항:**
- `ai_preferences`와 `embedding_model_version`은 AI 서비스에서 자동 관리
- Spring Boot에서 이 값들을 설정할 필요 없음

### 2. Board AI API (보드 기반 AI)
보드 문맥을 활용한 AI 질의 및 초안 생성

#### 2.1 AI 질의
```http
POST /board-ai/ask
Content-Type: application/json

{
    "user_id": 123,
    "board_id": "uuid-board-id",
    "question": "이 보드의 내용을 요약해주세요",
    "model_name": "gpt-4o-mini",
    "max_tokens": 1000
}
```

#### 2.2 AI 초안 생성
```http
POST /board-ai/draft
Content-Type: application/json

{
    "user_id": 123,
    "board_id": "uuid-board-id",
    "content_type": "blog_post",
    "requirements": "전문적이고 친근한 톤으로 작성",
    "model_name": "gpt-4o-mini"
}
```

#### 2.3 선택된 아이템 기반 질의
```http
POST /board-ai/ask-with-items
Content-Type: application/json

{
    "user_id": 123,
    "board_id": "uuid-board-id",
    "item_ids": [1, 2, 3],
    "question": "선택된 아이템들의 공통점을 분석해주세요",
    "model_name": "gpt-4o-mini"
}
```

### 3. Clipper API (웹페이지 수집)
웹페이지 수집 및 AI 분석

#### 3.1 웹페이지 동기화
```http
POST /api/v1/clipper/webpage/sync
Content-Type: multipart/form-data

{
    "item_id": 456,
    "user_id": 123,
    "thumbnail": "https://example.com/thumb.jpg",
    "title": "페이지 제목",
    "url": "https://example.com",
    "category": "tech",
    "html_file": [HTML 파일]
}
```

## 🔧 Spring Boot 연동 예시

### 1. 사용자 가입 시 동기화
```java
@Service
public class UserService {
    
    @Value("${ai.api.base-url}")
    private String aiApiBaseUrl;
    
    public void registerUser(Long userId) {
        // Spring Boot에서 사용자 생성 후
        User user = userRepository.save(new User(...));
        
        // AI 서비스로 동기화
        syncUserToAI(user.getId(), true);
    }
    
    private void syncUserToAI(Long userId, boolean isActive) {
        RestTemplate restTemplate = new RestTemplate();
        
        Map<String, Object> request = Map.of(
            "user_id", userId,
            "is_active", isActive
        );
        
        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(
                aiApiBaseUrl + "/user-sync/sync", 
                request, 
                Map.class
            );
            
            log.info("User {} synced to AI service: {}", userId, response.getBody());
        } catch (Exception e) {
            log.error("Failed to sync user {} to AI service", userId, e);
            // 필요에 따라 재시도 로직 추가
        }
    }
}
```

### 2. 사용자 탈퇴 시 상태 변경
```java
public void deactivateUser(Long userId) {
    // Spring Boot에서 사용자 비활성화
    userRepository.updateUserStatus(userId, false);
    
    // AI 서비스 상태 동기화
    updateUserStatusInAI(userId, false);
}

private void updateUserStatusInAI(Long userId, boolean isActive) {
    RestTemplate restTemplate = new RestTemplate();
    
    Map<String, Object> request = Map.of(
        "user_id", userId,
        "is_active", isActive
    );
    
    try {
        ResponseEntity<Map> response = restTemplate.exchange(
            aiApiBaseUrl + "/user-sync/status",
            HttpMethod.PUT,
            new HttpEntity<>(request),
            Map.class
        );
        
        log.info("User {} status updated in AI service: {}", userId, response.getBody());
    } catch (Exception e) {
        log.error("Failed to update user {} status in AI service", userId, e);
    }
}
```

## 🛡️ 에러 처리

### HTTP 상태 코드
- `200`: 성공
- `400`: 잘못된 요청 (필수 필드 누락, 잘못된 데이터)
- `404`: 사용자를 찾을 수 없음
- `422`: 유효성 검증 실패
- `500`: 서버 내부 오류

### 에러 응답 예시
```json
{
    "detail": "사용자 동기화 중 오류가 발생했습니다."
}
```

### 재시도 정책 권장사항
1. **네트워크 오류 (5xx)**: 지수 백오프로 최대 3회 재시도
2. **클라이언트 오류 (4xx)**: 재시도하지 않고 로그 기록
3. **타임아웃**: 30초 설정 권장

## 🔄 동기화 시점

### 필수 동기화 시점
1. **사용자 가입**: 즉시 동기화
2. **사용자 탈퇴**: 즉시 상태 변경
3. **계정 복구**: 즉시 상태 변경

### 권장 동기화 시점
1. **정기 배치**: 일 1회 전체 사용자 동기화 (데이터 일관성 보장)
2. **서비스 재시작**: AI 서비스 재시작 후 활성 사용자 동기화

## 📞 문의사항

API 연동 관련 문의사항이 있으시면 AI 개발팀으로 연락주세요.

---

**참고**: AI 관련 개인화 설정(`ai_preferences`, `embedding_model_version`)은 AI 서비스에서 사용자 행동을 기반으로 자동 학습/관리되므로, Spring Boot에서 별도로 관리할 필요가 없습니다.