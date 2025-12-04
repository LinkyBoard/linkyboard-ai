"""S3/MinIO Storage 서비스

PDF 파일 업로드/다운로드를 위한 S3 클라이언트
"""

import hashlib
from functools import lru_cache
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import Settings, settings
from app.core.exceptions import ErrorCode, StorageException
from app.core.logging import get_logger

logger = get_logger(__name__)


class S3Client:
    """S3/MinIO 클라이언트

    PDF 파일을 S3 또는 MinIO에 업로드/다운로드합니다.
    """

    def __init__(self, settings: Settings):
        """S3 클라이언트 초기화

        Args:
            settings: 애플리케이션 설정
        """
        self.settings = settings
        self.bucket = settings.s3_bucket_contents

        # boto3 클라이언트 초기화
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},  # MinIO 호환
            ),
            use_ssl=settings.s3_use_ssl,
        )

        logger.info(
            "S3 Client initialized",
            extra={
                "endpoint": settings.s3_endpoint,
                "bucket": self.bucket,
                "region": settings.s3_region,
            },
        )

    def calculate_file_hash(self, file_content: bytes) -> str:
        """파일 해시 계산 (SHA-256)

        Args:
            file_content: 파일 내용 (bytes)

        Returns:
            SHA-256 해시 문자열 (hex)
        """
        return hashlib.sha256(file_content).hexdigest()

    def ensure_valid_file_size(
        self, file_size: int, max_size: Optional[int] = None
    ) -> None:
        """파일 크기 검증 및 보장

        Args:
            file_size: 파일 크기 (bytes)
            max_size: 최대 크기 (bytes, None이면 설정값 사용)

        Raises:
            StorageException: 파일 크기가 제한을 초과하는 경우
        """
        max_allowed = max_size or self.settings.max_content_size

        if file_size > max_allowed:
            max_mb = max_allowed / 1024 / 1024
            raise StorageException(
                message=f"파일 크기가 제한을 초과했습니다. (최대: {max_mb:.2f}MB)",
                error_code=ErrorCode.FILE_TOO_LARGE,
                detail={
                    "file_size": file_size,
                    "max_size": max_allowed,
                },
            )

    def upload_pdf(self, file_content: bytes, file_hash: str) -> str:
        """PDF 파일을 S3에 업로드

        Args:
            file_content: PDF 파일 내용 (bytes)
            file_hash: 파일 해시 (SHA-256)

        Returns:
            S3 객체 키 (pdfs/{file_hash}.pdf)

        Raises:
            StorageException: S3 업로드 실패 시
        """
        # S3 객체 키 생성
        object_key = f"pdfs/{file_hash}.pdf"

        try:
            # S3에 업로드
            self.client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=file_content,
                ContentType="application/pdf",
                Metadata={
                    "file_hash": file_hash,
                    "content_length": str(len(file_content)),
                },
            )

            logger.info(
                "PDF uploaded to S3",
                extra={
                    "bucket": self.bucket,
                    "key": object_key,
                    "file_hash": file_hash,
                    "size": len(file_content),
                },
            )

            return object_key

        except ClientError as e:
            logger.exception(
                "S3 upload failed",
                extra={
                    "bucket": self.bucket,
                    "key": object_key,
                    "file_hash": file_hash,
                    "error": str(e),
                },
            )
            raise StorageException(
                message="PDF 파일 업로드에 실패했습니다.",
                error_code=ErrorCode.S3_UPLOAD_FAILED,
                detail={
                    "file_hash": file_hash,
                    "error": str(e),
                },
            )

    def download_pdf(self, file_hash: str) -> bytes:
        """S3에서 PDF 파일 다운로드

        Args:
            file_hash: 파일 해시 (SHA-256)

        Returns:
            PDF 파일 내용 (bytes)

        Raises:
            StorageException: S3 다운로드 실패 시
        """
        object_key = f"pdfs/{file_hash}.pdf"

        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=object_key,
            )

            file_content: bytes = response["Body"].read()

            logger.info(
                "PDF downloaded from S3",
                extra={
                    "bucket": self.bucket,
                    "key": object_key,
                    "file_hash": file_hash,
                    "size": len(file_content),
                },
            )

            return file_content

        except ClientError as e:
            error_code_str = e.response.get("Error", {}).get("Code", "")

            # NoSuchKey 에러는 파일 없음으로 처리
            if error_code_str == "NoSuchKey":
                logger.warning(
                    "PDF file not found in S3",
                    extra={
                        "bucket": self.bucket,
                        "key": object_key,
                        "file_hash": file_hash,
                    },
                )
                raise StorageException(
                    message="파일을 찾을 수 없습니다.",
                    error_code=ErrorCode.S3_DOWNLOAD_FAILED,
                    detail={
                        "file_hash": file_hash,
                        "error": "File not found",
                    },
                )

            # 기타 에러
            logger.exception(
                "S3 download failed",
                extra={
                    "bucket": self.bucket,
                    "key": object_key,
                    "file_hash": file_hash,
                    "error": str(e),
                },
            )
            raise StorageException(
                message="PDF 파일 다운로드에 실패했습니다.",
                error_code=ErrorCode.S3_DOWNLOAD_FAILED,
                detail={
                    "file_hash": file_hash,
                    "error": str(e),
                },
            )

    def get_file_url(self, file_hash: str) -> str:
        """S3 객체 URL 생성

        Args:
            file_hash: 파일 해시 (SHA-256)

        Returns:
            S3 객체 URL
        """
        object_key = f"pdfs/{file_hash}.pdf"

        # S3 URL 생성
        if self.settings.s3_use_ssl:
            protocol = "https"
        else:
            protocol = "http"

        # MinIO는 path-style, AWS S3는 virtual-hosted-style
        endpoint = self.settings.s3_endpoint
        if endpoint:
            # MinIO or custom S3-compatible storage (path-style)
            clean_endpoint = endpoint.replace("http://", "").replace(
                "https://", ""
            )
            url = f"{protocol}://{clean_endpoint}/{self.bucket}/{object_key}"
        else:
            # AWS S3 (virtual-hosted-style)
            region = self.settings.s3_region
            if region == "us-east-1":
                # us-east-1은 리전 표기 생략
                host = f"{self.bucket}.s3.amazonaws.com"
            else:
                host = f"{self.bucket}.s3.{region}.amazonaws.com"
            url = f"{protocol}://{host}/{object_key}"

        return url

    def file_exists(self, file_hash: str) -> bool:
        """파일이 S3에 존재하는지 확인

        Args:
            file_hash: 파일 해시 (SHA-256)

        Returns:
            파일이 존재하면 True, 아니면 False
        """
        object_key = f"pdfs/{file_hash}.pdf"

        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=object_key,
            )
            return True
        except ClientError:
            return False


@lru_cache
def _create_s3_client() -> S3Client:
    """S3 클라이언트 싱글톤 생성 (캐시됨)

    Returns:
        S3Client 인스턴스
    """
    return S3Client(settings)


def get_s3_client() -> S3Client:
    """FastAPI DI용 S3 클라이언트 의존성

    Returns:
        S3Client 인스턴스
    """
    return _create_s3_client()
