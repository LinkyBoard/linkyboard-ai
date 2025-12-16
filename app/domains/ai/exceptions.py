"""AI 도메인 예외 클래스

AI 기능 수행 중 발생할 수 있는 도메인 특화 예외들을 정의합니다.
"""
from enum import Enum

from app.core.exceptions import (
    BadRequestException,
    InternalServerException,
    NotFoundException,
)


class AIErrorCode(str, Enum):
    """AI 도메인 에러 코드"""

    # 서비스 레벨 에러
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    EMBEDDING_FAILED = "EMBEDDING_FAILED"
    SUMMARIZATION_FAILED = "SUMMARIZATION_FAILED"
    EVALUATION_FAILED = "EVALUATION_FAILED"

    # URL/입력 검증 에러
    INVALID_URL_FORMAT = "INVALID_URL_FORMAT"
    INVALID_YOUTUBE_URL = "INVALID_YOUTUBE_URL"

    # YouTube 관련 에러
    YOUTUBE_VIDEO_NOT_FOUND = "YOUTUBE_VIDEO_NOT_FOUND"
    TRANSCRIPT_NOT_AVAILABLE = "TRANSCRIPT_NOT_AVAILABLE"

    # 파싱 에러
    HTML_PARSE_ERROR = "HTML_PARSE_ERROR"
    PDF_PARSE_ERROR = "PDF_PARSE_ERROR"

    # 파일 관련 에러
    FILE_SIZE_EXCEEDED = "FILE_SIZE_EXCEEDED"

    # 캐시 에러
    CACHE_NOT_FOUND = "CACHE_NOT_FOUND"

    # 콘텐츠 에러
    CONTENT_NOT_FOUND = "CONTENT_NOT_FOUND"


# AI 서비스 관련 예외


class AIServiceUnavailableException(InternalServerException):
    """AI 서비스 일시 불가

    LLM API 호출 실패 등으로 AI 서비스를
    일시적으로 사용할 수 없을 때 발생합니다.
    """

    def __init__(self, detail_msg: str = "AI 서비스가 일시적으로 사용 불가능합니다"):
        super().__init__(
            message="AI 서비스가 일시적으로 사용 불가능합니다",
            error_code=AIErrorCode.AI_SERVICE_UNAVAILABLE,
            detail={"info": detail_msg},
        )


class EmbeddingFailedException(InternalServerException):
    """임베딩 생성 실패

    텍스트 임베딩 생성 중 오류가 발생했을 때 발생합니다.
    """

    def __init__(self, detail_msg: str):
        super().__init__(
            message="임베딩 생성에 실패했습니다",
            error_code=AIErrorCode.EMBEDDING_FAILED,
            detail={"info": detail_msg},
        )


class SummarizationFailedException(InternalServerException):
    """요약 생성 실패

    LLM을 사용한 요약 생성 중 오류가 발생했을 때 발생합니다.
    """

    def __init__(self, detail_msg: str):
        super().__init__(
            message="요약 생성에 실패했습니다",
            error_code=AIErrorCode.SUMMARIZATION_FAILED,
            detail={"info": detail_msg},
        )


class EvaluationFailedException(InternalServerException):
    """신뢰도 평가 실패 (Phase 2)

    RAG 결과의 신뢰도 평가 중 오류가 발생했을 때 발생합니다.
    """

    def __init__(self, detail_msg: str):
        super().__init__(
            message="신뢰도 평가에 실패했습니다",
            error_code=AIErrorCode.EVALUATION_FAILED,
            detail={"info": detail_msg},
        )


# URL/입력 검증 예외


class InvalidURLFormatException(BadRequestException):
    """잘못된 URL 형식

    제공된 URL이 유효하지 않은 형식일 때 발생합니다.
    """

    def __init__(self, url: str):
        super().__init__(
            message="잘못된 URL 형식입니다",
            error_code=AIErrorCode.INVALID_URL_FORMAT,
            detail={"url": url},
        )


class InvalidYoutubeURLException(BadRequestException):
    """잘못된 YouTube URL

    YouTube URL이 아니거나 비디오 ID를 추출할 수 없을 때 발생합니다.
    """

    def __init__(self, url: str):
        super().__init__(
            message="잘못된 YouTube URL입니다",
            error_code=AIErrorCode.INVALID_YOUTUBE_URL,
            detail={"url": url},
        )


# YouTube 관련 예외


class YoutubeVideoNotFoundException(NotFoundException):
    """YouTube 동영상을 찾을 수 없음

    제공된 YouTube 비디오 ID에 해당하는 동영상이 존재하지 않거나
    접근할 수 없을 때 발생합니다.
    """

    def __init__(self, video_id: str):
        super().__init__(
            message="YouTube 동영상을 찾을 수 없습니다",
            error_code=AIErrorCode.YOUTUBE_VIDEO_NOT_FOUND,
            detail={"video_id": video_id},
        )


class TranscriptNotAvailableException(BadRequestException):
    """자막을 가져올 수 없음

    YouTube 동영상에 자막이 없거나 자막 API 호출이 실패했을 때 발생합니다.
    사용자에게 수동으로 메모를 작성하도록 안내할 수 있습니다.
    """

    def __init__(self, video_id: str, reason: str = "자막을 사용할 수 없습니다"):
        super().__init__(
            message="자막을 가져올 수 없습니다",
            error_code=AIErrorCode.TRANSCRIPT_NOT_AVAILABLE,
            detail={"video_id": video_id, "reason": reason},
        )


# 파싱 예외


class HTMLParseException(BadRequestException):
    """HTML 파싱 실패

    HTML 파싱 중 오류가 발생했을 때 발생합니다.
    """

    def __init__(self, detail_msg: str):
        super().__init__(
            message="HTML 파싱에 실패했습니다",
            error_code=AIErrorCode.HTML_PARSE_ERROR,
            detail={"info": detail_msg},
        )


class PDFParseException(BadRequestException):
    """PDF 파싱 실패

    PDF 텍스트 추출 중 오류가 발생했을 때 발생합니다.
    손상된 PDF 파일이거나 텍스트가 없는 이미지 기반 PDF일 수 있습니다.
    """

    def __init__(self, detail_msg: str):
        super().__init__(
            message="PDF 파싱에 실패했습니다",
            error_code=AIErrorCode.PDF_PARSE_ERROR,
            detail={"info": detail_msg},
        )


# 파일 관련 예외


class FileSizeExceededException(BadRequestException):
    """파일 크기 제한 초과

    업로드된 파일이 허용된 최대 크기를 초과했을 때 발생합니다.
    """

    def __init__(self, file_size: int, max_size: int):
        super().__init__(
            message="파일 크기가 제한을 초과했습니다",
            error_code=AIErrorCode.FILE_SIZE_EXCEEDED,
            detail={"file_size": file_size, "max_size": max_size},
        )


# 캐시 예외


class CacheNotFoundException(NotFoundException):
    """캐시를 찾을 수 없음

    요청한 캐시 키에 해당하는 캐시 항목이
    존재하지 않거나 만료되었을 때 발생합니다.
    """

    def __init__(self, cache_key: str):
        super().__init__(
            message="캐시를 찾을 수 없습니다",
            error_code=AIErrorCode.CACHE_NOT_FOUND,
            detail={"cache_key": cache_key},
        )


# 콘텐츠 예외


class ContentNotFoundException(NotFoundException):
    """콘텐츠를 찾을 수 없음

    요청한 콘텐츠 ID에 해당하는 콘텐츠가 존재하지 않을 때 발생합니다.
    """

    def __init__(self, content_id: int):
        super().__init__(
            message="콘텐츠를 찾을 수 없습니다",
            error_code=AIErrorCode.CONTENT_NOT_FOUND,
            detail={"content_id": content_id},
        )
