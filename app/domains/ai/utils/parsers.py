"""콘텐츠 파싱 유틸리티

HTML, PDF, YouTube 자막 등 다양한 포맷의 텍스트를 추출합니다.
"""

import hashlib
import re
from typing import Union, cast

from bs4 import BeautifulSoup
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from app.core.logging import get_logger
from app.domains.ai.exceptions import (
    HTMLParseException,
    InvalidYoutubeURLException,
    PDFParseException,
    TranscriptNotAvailableException,
    YoutubeVideoNotFoundException,
)

logger = get_logger(__name__)


def extract_text_from_html(html_content: str) -> str:
    """HTML에서 텍스트 추출

    Args:
        html_content: HTML 콘텐츠 문자열

    Returns:
        str: 추출된 텍스트

    Raises:
        HTMLParseException: HTML 파싱 실패 시
    """
    try:
        soup = BeautifulSoup(html_content, "lxml")

        # 스크립트, 스타일 태그 제거
        for script in soup(["script", "style", "noscript"]):
            script.decompose()

        # 본문 텍스트 추출
        text = cast(str, soup.get_text(separator="\n", strip=True))

        # 연속된 공백/줄바꿈 정리
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        if not text.strip():
            raise HTMLParseException(detail_msg="HTML에서 텍스트를 추출할 수 없습니다")

        logger.info(f"Extracted {len(text)} characters from HTML")
        return text.strip()

    except Exception as e:
        logger.error(f"HTML parsing failed: {e}")
        raise HTMLParseException(detail_msg=f"HTML 파싱 실패: {str(e)}")


def extract_text_from_pdf(pdf_content: bytes) -> str:
    """PDF에서 텍스트 추출

    Args:
        pdf_content: PDF 바이너리 콘텐츠

    Returns:
        str: 추출된 텍스트

    Raises:
        PDFParseException: PDF 파싱 실패 시
    """
    try:
        from io import BytesIO

        pdf_file = BytesIO(pdf_content)
        reader = PdfReader(pdf_file)

        if len(reader.pages) == 0:
            raise PDFParseException(detail_msg="PDF에 페이지가 없습니다")

        # 페이지별 텍스트 추출
        text_parts = []
        for page_num, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(page_text)
            except Exception as e:
                logger.warning(f"Page {page_num + 1} extraction failed: {e}")
                continue

        if not text_parts:
            raise PDFParseException(
                detail_msg="PDF에서 텍스트를 추출할 수 없습니다. "
                "이미지 기반 PDF이거나 보호된 문서일 수 있습니다."
            )

        text = "\n\n".join(text_parts)

        # 공백 정리
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        logger.info(
            f"Extracted {len(text)} characters from PDF "
            f"({len(reader.pages)} pages)"
        )
        return text.strip()

    except PDFParseException:
        raise
    except Exception as e:
        logger.error(f"PDF parsing failed: {e}")
        raise PDFParseException(detail_msg=f"PDF 파싱 실패: {str(e)}")


def extract_youtube_video_id(url: str) -> str:
    """YouTube URL에서 비디오 ID 추출

    Args:
        url: YouTube URL

    Returns:
        str: 비디오 ID

    Raises:
        InvalidYoutubeURLException: 유효하지 않은 YouTube URL
    """
    # youtu.be 형식
    match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)

    # youtube.com/watch?v= 형식
    match = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)

    # youtube.com/embed/ 형식
    match = re.search(r"youtube\.com/embed/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)

    raise InvalidYoutubeURLException(url=url)


def get_youtube_transcript(
    video_id: str, languages: list[str] | None = None
) -> str:
    """YouTube 자막 추출

    Args:
        video_id: YouTube 비디오 ID
        languages: 선호 언어 목록 (기본: ['ko', 'en'])

    Returns:
        str: 자막 텍스트

    Raises:
        YoutubeVideoNotFoundException: 동영상을 찾을 수 없음
        TranscriptNotAvailableException: 자막을 사용할 수 없음
    """
    if languages is None:
        languages = ["ko", "en"]

    try:
        # 자막 가져오기
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # 선호 언어 순서대로 시도
        transcript = None
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except NoTranscriptFound:
                continue

        # 선호 언어가 없으면 사용 가능한 첫 번째 자막
        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(
                    languages
                )
            except NoTranscriptFound:
                # 자동 생성 자막도 없으면 수동 자막 중 첫 번째
                # TODO : mp3 -> transcript 변환
                available = list(transcript_list)
                if available:
                    transcript = available[0]
                else:
                    raise TranscriptNotAvailableException(
                        video_id=video_id,
                        reason="사용 가능한 자막이 없습니다",
                    )

        # 자막 텍스트 추출
        transcript_data = transcript.fetch()
        text_parts = [item["text"] for item in transcript_data]
        text = " ".join(text_parts)

        # 공백 정리
        text = re.sub(r"\s+", " ", text)

        logger.info(
            f"Extracted {len(text)} characters from YouTube "
            f"transcript (video_id={video_id})"
        )
        return text.strip()

    except VideoUnavailable:
        logger.error(f"YouTube video not found: {video_id}")
        raise YoutubeVideoNotFoundException(video_id=video_id)
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        logger.warning(f"Transcript not available: {video_id} - {e}")
        raise TranscriptNotAvailableException(video_id=video_id, reason=str(e))
    except Exception as e:
        logger.error(f"YouTube transcript extraction failed: {e}")
        raise TranscriptNotAvailableException(
            video_id=video_id, reason=f"자막 추출 실패: {str(e)}"
        )


def calculate_content_hash(content: Union[str, bytes]) -> str:
    """콘텐츠 해시 계산 (캐시 키 생성용)

    Args:
        content: 텍스트 또는 바이너리 콘텐츠

    Returns:
        str: SHA-256 해시 (16진수 문자열)
    """
    if isinstance(content, str):
        content = content.encode("utf-8")

    hash_obj = hashlib.sha256(content)
    return hash_obj.hexdigest()
