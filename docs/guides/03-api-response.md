# API 응답 규칙

## 응답 스키마 구조

### 성공 응답 - 단일 데이터

```python
from app.core.schemas import APIResponse, create_response

@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user(user_id: int):
    user = await service.get_user(user_id)
    return create_response(
        data=UserResponse.model_validate(user),
        message="사용자 정보를 조회했습니다.",
    )
```

**응답 예시:**

```json
{
    "success": true,
    "message": "사용자 정보를 조회했습니다.",
    "data": {
        "id": 1,
        "username": "testuser",
        "full_name": "Test User",
        "is_active": true,
        "is_superuser": false,
        "created_at": "2025-12-01T12:00:00Z",
        "updated_at": null
    }
}
```

### 성공 응답 - 목록 데이터 (페이지네이션)

```python
from app.core.schemas import ListAPIResponse, create_list_response
from app.core.utils.pagination import PageParams

@router.get("", response_model=ListAPIResponse[UserResponse])
async def get_users(page_params: PageParams = Depends()):
    users, total = await service.get_users(
        page=page_params.page,
        size=page_params.size,
    )
    return create_list_response(
        data=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page_params.page,
        size=page_params.size,
        message="사용자 목록을 조회했습니다.",
    )
```

**응답 예시:**

```json
{
    "success": true,
    "message": "사용자 목록을 조회했습니다.",
    "data": [
        {
            "id": 1,
            "username": "user1",
            ...
        }
    ],
    "meta": {
        "total": 100,
        "page": 1,
        "size": 20,
        "total_pages": 5,
        "has_next": true,
        "has_prev": false
    }
}
```

### 에러 응답

```json
{
    "success": false,
    "message": "사용자를 찾을 수 없습니다.",
    "error": {
        "code": "USER_NOT_FOUND",
        "message": "사용자를 찾을 수 없습니다.",
        "detail": {
            "user_id": 123
        }
    }
}
```

## 스키마 클래스

| 클래스 | 용도 |
|--------|------|
| `APIResponse[T]` | 단일 데이터 응답 |
| `ListAPIResponse[T]` | 목록 데이터 응답 (페이지네이션 포함) |
| `ErrorResponse` | 에러 응답 |
| `PageMeta` | 페이지네이션 메타 정보 |

## 팩토리 함수

직접 클래스 생성자 대신 **팩토리 함수** 사용 권장:

```python
# ✅ 권장
from app.core.schemas import create_response, create_list_response

return create_response(data=user, message="조회 성공")
return create_list_response(data=users, total=100, page=1, size=20)

# ⚠️ 가능하지만 권장하지 않음
return APIResponse(success=True, data=user, message="조회 성공")
```

## HTTP 상태 코드

| 상태 코드 | 용도 | 예시 |
|-----------|------|------|
| 200 | 조회/수정 성공 | GET, PATCH |
| 201 | 생성 성공 | POST |
| 204 | 삭제 성공 (본문 없음) | DELETE |
| 400 | 잘못된 요청 | 유효성 검사 실패 |
| 401 | 인증 필요 | 토큰 없음/만료 |
| 403 | 권한 없음 | 접근 거부 |
| 404 | 리소스 없음 | 존재하지 않는 ID |
| 409 | 충돌 | 중복 데이터 |
| 500 | 서버 오류 | 예상치 못한 오류 |

## 엔드포인트 응답 설정

```python
# 조회 (기본 200)
@router.get("/{user_id}", response_model=APIResponse[UserResponse])

# 생성 (201)
@router.post("", response_model=APIResponse[UserResponse], status_code=201)

# 수정 (기본 200)
@router.patch("/{user_id}", response_model=APIResponse[UserResponse])

# 삭제 (204, 본문 없음)
@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int):
    await service.delete_user(user_id)
    return None  # 204는 본문 없음
```

## 요청 ID 추적

모든 응답에 `X-Request-ID` 헤더가 포함됩니다.

```bash
$ curl -I http://localhost:8000/health

HTTP/1.1 200 OK
x-request-id: 550e8400-e29b-41d4-a716-446655440000
x-process-time: 0.0012
```

클라이언트가 `X-Request-ID`를 전송하면 해당 값을 사용합니다:

```bash
$ curl -H "X-Request-ID: my-custom-id" http://localhost:8000/health
```
