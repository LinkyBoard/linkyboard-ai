"""S3Client 유닛 테스트"""

import hashlib

import pytest

from app.core.config import Settings
from app.core.exceptions import StorageException
from app.core.storage import S3Client


class TestS3ClientHashCalculation:
    """파일 해시 계산 테스트"""

    def test_calculate_file_hash(self):
        """SHA-256 해시 계산 테스트"""
        # Given
        settings = Settings(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test",
            s3_bucket_contents="test",
        )
        client = S3Client(settings)
        file_content = b"test content"

        # When
        file_hash = client.calculate_file_hash(file_content)

        # Then
        expected_hash = hashlib.sha256(file_content).hexdigest()
        assert file_hash == expected_hash
        assert len(file_hash) == 64

    def test_calculate_file_hash_empty_file(self):
        """빈 파일 해시 계산 테스트"""
        # Given
        settings = Settings(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test",
            s3_bucket_contents="test",
        )
        client = S3Client(settings)
        file_content = b""

        # When
        file_hash = client.calculate_file_hash(file_content)

        # Then
        expected_hash = hashlib.sha256(b"").hexdigest()
        assert file_hash == expected_hash


class TestS3ClientValidation:
    """파일 크기 검증 테스트"""

    def test_validate_file_size_success(self):
        """파일 크기 검증 성공 케이스"""
        # Given
        settings = Settings(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test",
            s3_bucket_contents="test",
            max_content_size=50 * 1024 * 1024,  # 50MB
        )
        client = S3Client(settings)
        file_size = 10 * 1024 * 1024  # 10MB

        # When / Then
        client.validate_file_size(file_size)  # 예외 발생하지 않음

    def test_validate_file_size_exceeds(self):
        """파일 크기 초과 시 예외 발생"""
        # Given
        settings = Settings(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test",
            s3_bucket_contents="test",
            max_content_size=50 * 1024 * 1024,  # 50MB
        )
        client = S3Client(settings)
        file_size = 60 * 1024 * 1024  # 60MB

        # When / Then
        with pytest.raises(StorageException) as exc_info:
            client.validate_file_size(file_size)
        assert "파일 크기가 제한을 초과" in exc_info.value.message

    def test_validate_file_size_exact_limit(self):
        """파일 크기가 정확히 제한값일 때"""
        # Given
        settings = Settings(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test",
            s3_bucket_contents="test",
            max_content_size=50 * 1024 * 1024,  # 50MB
        )
        client = S3Client(settings)
        file_size = 50 * 1024 * 1024  # Exactly 50MB

        # When / Then
        client.validate_file_size(file_size)  # 예외 발생하지 않음


class TestS3ClientUploadDownload:
    """S3 업로드/다운로드 테스트 (실제 MinIO 사용)"""

    def test_upload_pdf(self, test_s3_client):
        """PDF 업로드 테스트"""
        # Given
        file_content = b"test pdf content"
        file_hash = test_s3_client.calculate_file_hash(file_content)

        # When
        object_key = test_s3_client.upload_pdf(file_content, file_hash)

        # Then
        assert object_key == f"pdfs/{file_hash}.pdf"

        # MinIO에 파일이 실제로 업로드되었는지 확인
        response = test_s3_client.client.head_object(
            Bucket=test_s3_client.settings.s3_bucket_contents,
            Key=object_key,
        )
        assert response["ContentLength"] == len(file_content)

    def test_download_pdf(self, test_s3_client):
        """PDF 다운로드 테스트"""
        # Given
        file_content = b"test pdf content for download"
        file_hash = test_s3_client.calculate_file_hash(file_content)
        test_s3_client.upload_pdf(file_content, file_hash)

        # When
        downloaded_content = test_s3_client.download_pdf(file_hash)

        # Then
        assert downloaded_content == file_content

    def test_download_pdf_not_found(self, test_s3_client):
        """존재하지 않는 PDF 다운로드 시 예외 발생"""
        # Given
        non_existent_hash = "0" * 64

        # When / Then
        with pytest.raises(StorageException) as exc_info:
            test_s3_client.download_pdf(non_existent_hash)
        assert "파일을 찾을 수 없습니다" in exc_info.value.message

    def test_upload_pdf_duplicate(self, test_s3_client):
        """동일한 파일 중복 업로드 (덮어쓰기)"""
        # Given
        file_content = b"duplicate test content"
        file_hash = test_s3_client.calculate_file_hash(file_content)

        # When
        object_key_1 = test_s3_client.upload_pdf(file_content, file_hash)
        object_key_2 = test_s3_client.upload_pdf(file_content, file_hash)

        # Then
        assert object_key_1 == object_key_2
        downloaded = test_s3_client.download_pdf(file_hash)
        assert downloaded == file_content


class TestS3ClientURLGeneration:
    """S3 URL 생성 테스트"""

    def test_get_file_url_minio(self):
        """MinIO URL 생성 (path-style)"""
        # Given
        settings = Settings(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test",
            s3_bucket_contents="test-contents",
        )
        client = S3Client(settings)
        file_hash = "a" * 64

        # When
        url = client.get_file_url(file_hash)

        # Then
        assert (
            url == f"http://localhost:9000/test-contents/pdfs/{file_hash}.pdf"
        )

    def test_get_file_url_aws(self):
        """AWS S3 URL 생성 (virtual-hosted-style)"""
        # Given
        settings = Settings(
            s3_endpoint=None,  # AWS S3는 endpoint가 None
            s3_access_key="test",
            s3_secret_key="test",
            s3_bucket_contents="prod-contents",
            s3_region="ap-northeast-2",
            s3_use_ssl=True,  # AWS는 항상 HTTPS
        )
        client = S3Client(settings)
        file_hash = "b" * 64

        # When
        url = client.get_file_url(file_hash)

        # Then
        expected_url = (
            f"https://prod-contents.s3.ap-northeast-2.amazonaws.com/"
            f"pdfs/{file_hash}.pdf"
        )
        assert url == expected_url

    def test_get_file_url_aws_us_east_1(self):
        """AWS S3 URL 생성 (us-east-1 리전)"""
        # Given
        settings = Settings(
            s3_endpoint=None,
            s3_access_key="test",
            s3_secret_key="test",
            s3_bucket_contents="us-contents",
            s3_region="us-east-1",
            s3_use_ssl=True,  # AWS는 항상 HTTPS
        )
        client = S3Client(settings)
        file_hash = "c" * 64

        # When
        url = client.get_file_url(file_hash)

        # Then
        # us-east-1은 리전 표기 생략
        expected_url = (
            f"https://us-contents.s3.amazonaws.com/pdfs/{file_hash}.pdf"
        )
        assert url == expected_url
