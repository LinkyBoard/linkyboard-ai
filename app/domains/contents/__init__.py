"""Contents 도메인 모듈

웹페이지, YouTube, PDF 콘텐츠를 관리하는 도메인입니다.

구조:
    - models.py: SQLAlchemy 모델 정의
      (Content, ContentType, SummaryStatus, EmbeddingStatus)
    - schemas.py: Pydantic 스키마 (Request/Response)
    - repository.py: 데이터 접근 계층
    - service.py: 비즈니스 로직 (Sync, CRUD)
    - router.py: API 엔드포인트 (API Key 인증 포함)
    - exceptions.py: 도메인 예외
"""

from app.domains.contents.exceptions import (
    CacheNotFoundException,
    ContentAlreadyDeletedException,
    ContentErrorCode,
    ContentNotFoundException,
    FileSizeExceededException,
    InvalidContentTypeException,
)
from app.domains.contents.models import (
    Content,
    ContentType,
    EmbeddingStatus,
    SummaryStatus,
)

__all__ = [
    "Content",
    "ContentType",
    "SummaryStatus",
    "EmbeddingStatus",
    "ContentErrorCode",
    "ContentNotFoundException",
    "ContentAlreadyDeletedException",
    "InvalidContentTypeException",
    "FileSizeExceededException",
    "CacheNotFoundException",
]
