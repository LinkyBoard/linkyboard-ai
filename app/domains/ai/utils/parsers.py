"""콘텐츠 파싱 유틸리티

HTML, PDF, YouTube 자막 등 다양한 포맷의 텍스트를 추출합니다.
"""

import hashlib
import re
from typing import Union, cast

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.core.logging import get_logger
from app.domains.ai.exceptions import HTMLParseException, PDFParseException

logger = get_logger(__name__)


async def fetch_html_from_url(url: str, timeout: float = 30.0) -> str:
    """URL에서 HTML 콘텐츠 가져오기

    Args:
        url: 가져올 웹페이지 URL
        timeout: 요청 타임아웃 (초, 기본: 30.0)

    Returns:
        str: HTML 콘텐츠

    Raises:
        HTMLParseException: HTML 가져오기 실패 시
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            # 인코딩 감지 및 디코딩
            html_content: str
            if response.encoding:
                html_content = str(response.text)
            else:
                # 인코딩이 감지되지 않으면 UTF-8로 시도
                html_content = response.content.decode(
                    "utf-8", errors="replace"
                )

            logger.info(
                f"Fetched HTML from {url} ({len(html_content)} characters)"
            )
            return html_content

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching {url}: {e.response.status_code}")
        raise HTMLParseException(
            detail_msg=f"URL에서 HTML을 가져올 수 없습니다: HTTP {e.response.status_code}"
        )
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching {url}")
        raise HTMLParseException(detail_msg=f"URL 요청 시간 초과: {url}")
    except Exception as e:
        logger.error(f"Failed to fetch HTML from {url}: {e}")
        raise HTMLParseException(detail_msg=f"URL에서 HTML 가져오기 실패: {str(e)}")


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


def parse_subtitle_file(subtitle_content: str) -> str:
    """자막 파일 또는 일반 텍스트에서 텍스트 추출

    Args:
        subtitle_content: 자막 파일 내용 (SRT, VTT 등) 또는 일반 텍스트

    Returns:
        str: 추출된 텍스트

    Raises:
        HTMLParseException: 자막 파싱 실패 시
    """
    try:
        lines = subtitle_content.strip().split("\n")
        text_parts = []

        # VTT 헤더 체크
        is_vtt = lines[0].strip().upper() == "WEBVTT"

        for line in lines:
            line = line.strip()

            # 빈 줄 무시
            if not line:
                continue

            # VTT 헤더 무시
            if is_vtt and line.upper().startswith("WEBVTT"):
                continue

            # 숫자만 있는 줄 무시 (자막 번호)
            if line.isdigit():
                continue

            # 타임스탬프 줄 무시
            if "-->" in line:
                continue

            # 타임스탬프 패턴 무시 (00:00:00,000 형식)
            if re.match(r"^\d{2}:\d{2}:\d{2}[,\.]\d{3}$", line):
                continue

            # 나머지는 모두 텍스트로 처리
            text_parts.append(line)

        text = " ".join(text_parts)
        # 공백 정리
        text = re.sub(r"\s+", " ", text)

        if not text.strip():
            raise HTMLParseException(detail_msg="자막 파일에서 텍스트를 추출할 수 없습니다")

        logger.info(
            f"Extracted {len(text)} characters from subtitle/text file"
        )
        return text.strip()

    except HTMLParseException:
        raise
    except Exception as e:
        logger.error(f"Subtitle parsing failed: {e}")
        raise HTMLParseException(detail_msg=f"자막 파싱 실패: {str(e)}")


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
