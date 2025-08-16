import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from app.main import app  # 실제 FastAPI 앱 인스턴스를 가져옵니다.
from app.collect.v1.clipper.router import get_clipper_service

# TestClient 인스턴스 생성
client = TestClient(app)


@pytest.fixture
def mock_clipper_service():
    """ClipperService를 모의(Mock) 객체로 만들고 FastAPI 의존성을 오버라이드합니다."""
    mock_service = AsyncMock()
    app.dependency_overrides[get_clipper_service] = lambda: mock_service
    yield mock_service
    # 테스트 종료 후 오버라이드된 의존성 정리
    del app.dependency_overrides[get_clipper_service]


def test_summarize_webpage_success(mock_clipper_service):
    """
    POST /webpage/summarize 엔드포인트가 성공적으로 동작하는지 테스트합니다.
    """
    # Given (준비)
    # 서비스가 반환할 예상 결과
    service_result = {
        "summary": "AI가 생성한 요약입니다.",
        "recommended_tags": ["AI", "FastAPI", "Test"],
        "recommended_category": "기술"
    }
    mock_clipper_service.generate_webpage_summary_with_recommendations.return_value = service_result

    # HTML 파일 모의 데이터
    mock_html_content = b"<html><body><h1>Test</h1></body></html>"

    # When (실행)
    # TestClient를 사용하여 API 요청
    response = client.post(
        "/api/v1/clipper/webpage/summarize",
        data={
            "url": "http://test.com",
            "user_id": 123,
            "tag_count": 3
        },
        files={"html_file": ("test.html", mock_html_content, "text/html")}
    )

    # Then (검증)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["summary"] == service_result["summary"]
    assert response_data["tags"] == service_result["recommended_tags"]
    assert response_data["category"] == service_result["recommended_category"]

    # 서비스 메서드가 올바른 인자와 함께 호출되었는지 확인
    mock_clipper_service.generate_webpage_summary_with_recommendations.assert_called_once()
    call_args = mock_clipper_service.generate_webpage_summary_with_recommendations.call_args
    assert call_args.kwargs['user_id'] == 123
    assert call_args.kwargs['tag_count'] == 3
    assert call_args.kwargs['request_data'].url == "http://test.com"
    assert call_args.kwargs['request_data'].html_content == mock_html_content.decode('utf-8')
