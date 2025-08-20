import pytest
from unittest.mock import AsyncMock
from fastapi import BackgroundTasks

from app.collect.v1.clipper.service import ClipperService
from app.collect.v1.clipper.schemas import WebpageSyncRequest, SummarizeRequest
from app.core.models import Item, User


@pytest.fixture
def mock_session():
    """데이터베이스 세션을 위한 모의(Mock) 객체를 생성하는 픽스처"""
    return AsyncMock()


@pytest.fixture
def clipper_service(mocker):
    """
    ClipperService를 인스턴스화하고 내부 의존성을 Mocking합니다.
    __init__에서 자체적으로 의존성을 초기화하는 클래스를 테스트하는 표준적인 방법입니다.
    """
    # 1. 실제 서비스 인스턴스를 생성합니다.
    service = ClipperService()

    # 2. mocker.patch.object를 사용해 인스턴스 내부의 의존성을 모의 객체로 교체합니다.
    mocker.patch.object(service, 'user_repository', new_callable=AsyncMock)
    mocker.patch.object(service, 'item_repository', new_callable=AsyncMock)
    mocker.patch.object(service, 'ai_router', new_callable=AsyncMock)  # 올바른 속성명
    mocker.patch.object(service, 'embedding_service', new_callable=AsyncMock)
    mocker.patch.object(service, 'tag_extractor', new_callable=AsyncMock)
    mocker.patch.object(service, 'category_classifier', new_callable=AsyncMock)
    # 3. DB 작업을 수행하는 내부 헬퍼 메서드도 모의 처리합니다.
    mocker.patch.object(service, '_get_or_create_category_id', new_callable=AsyncMock, return_value=1)
    mocker.patch.object(service, '_create_item_tags', new_callable=AsyncMock)
    mocker.patch.object(service, '_process_embedding_with_monitoring', new_callable=AsyncMock)
    # YouTube 관련 의존성 모의 처리
    mocker.patch.object(service, 'youtube_url_extractor', new_callable=AsyncMock)
    mocker.patch.object(service, 'smart_extractor', new_callable=AsyncMock)

    return service


# --- 1. 의존성 없는 헬퍼 함수 테스트 ---
def test_rank_tags_by_user_preference(clipper_service):
    """_rank_tags_by_user_preference 헬퍼 함수의 태그 순위화 로직을 테스트합니다."""
    # Given (준비)
    service = clipper_service
    ai_tags = ["python", "fastapi", "docker", "react", "javascript"]
    user_tags = ["fastapi", "javascript", "sql"]  # 사용자는 fastapi와 javascript를 선호
    tag_count = 3

    # When (실행)
    ranked_tags = service._rank_tags_by_user_preference(ai_tags, user_tags, tag_count)

    # Then (검증)
    # - 최종 태그 개수는 3개여야 합니다.
    # - 사용자 선호 태그인 'fastapi'와 'javascript'가 포함되어야 합니다.
    # - 'fastapi'와 'javascript'가 다른 태그들보다 우선순위가 높아야 합니다.
    assert len(ranked_tags) == 3
    assert "fastapi" in ranked_tags
    assert "javascript" in ranked_tags
    assert ranked_tags[0] in ["fastapi", "javascript"]
    assert ranked_tags[1] in ["fastapi", "javascript"]
    assert ranked_tags[2] in ["python", "docker", "react"]


# --- 2. 의존성 있는 서비스 메서드 테스트 (Mocking 활용) ---
@pytest.mark.asyncio
async def test_sync_webpage_creates_new_item(clipper_service, mock_session, mocker):
    """
    sync_webpage 호출 시, 기존 아이템이 없으면 새로운 아이템을 생성하는지 테스트합니다.
    """
    # Given (준비)
    item_repo = clipper_service.item_repository
    user_repo = clipper_service.user_repository

    # 실제 서비스 메서드가 받는 요청 스키마 객체를 생성합니다.
    request_data = WebpageSyncRequest(
        item_id=101,
        user_id=1,
        thumbnail="http://example.com/thumb.jpg",
        title="New Example",
        url="http://new-example.com",
        tags=["new", "test"],
        category="Tech",
        html_content="<html>...</html>"
    )

    # 의존성 모의 객체들의 반환 값을 설정합니다.
    user_repo.get_or_create.return_value = User(id=1)
    item_repo.get_by_id.return_value = None  # 아이템이 존재하지 않는 상황을 시뮬레이션
    created_item = Item(id=request_data.item_id, user_id=request_data.user_id, title=request_data.title)
    item_repo.create.return_value = created_item

    mock_background_tasks = mocker.MagicMock(spec=BackgroundTasks)

    # When (실행)
    response = await clipper_service.sync_webpage(
        session=mock_session,
        background_tasks=mock_background_tasks,
        request_data=request_data
    )

    # Then (검증)
    user_repo.get_or_create.assert_called_once_with(mock_session, user_id=request_data.user_id)
    item_repo.get_by_id.assert_called_once_with(mock_session, request_data.item_id)
    item_repo.create.assert_called_once()  # create 메서드가 호출되었는지 확인
    item_repo.update.assert_not_called()   # update 메서드는 호출되지 않았는지 확인

    # 백그라운드 작업이 올바른 인자와 함께 예약되었는지 확인
    mock_background_tasks.add_task.assert_called_once_with(
        clipper_service._process_embedding_with_monitoring,
        request_data.item_id,
        request_data.html_content
    )

    assert response.success is True
    assert response.message == "콘텐츠가 성공적으로 저장되었습니다."


@pytest.mark.asyncio
async def test_sync_webpage_updates_existing_item(clipper_service, mock_session, mocker):
    """
    sync_webpage 호출 시, 기존 아이템이 있으면 정보를 업데이트하는지 테스트합니다.
    """
    # Given (준비)
    item_repo = clipper_service.item_repository
    user_repo = clipper_service.user_repository

    request_data = WebpageSyncRequest(
        item_id=202,
        user_id=1,
        thumbnail="http://example.com/thumb_new.jpg",
        title="Updated Title",
        url="http://existing-example.com",
        tags=["updated"],
        category="Programming",
        html_content="<html>...</html>"
    )

    # 아이템이 존재하는 상황을 시뮬레이션
    existing_item = Item(id=request_data.item_id, user_id=request_data.user_id, title="Old Title")
    item_repo.get_by_id.return_value = existing_item
    
    updated_item = Item(id=request_data.item_id, user_id=request_data.user_id, title=request_data.title)
    item_repo.update.return_value = updated_item
    
    user_repo.get_or_create.return_value = User(id=1)
    mock_background_tasks = mocker.MagicMock(spec=BackgroundTasks)

    # When (실행)
    await clipper_service.sync_webpage(
        session=mock_session,
        background_tasks=mock_background_tasks,
        request_data=request_data
    )

    # Then (검증)
    item_repo.get_by_id.assert_called_once_with(mock_session, request_data.item_id)
    item_repo.update.assert_called_once()  # update 메서드가 호출되었는지 확인
    item_repo.create.assert_not_called()   # create 메서드는 호출되지 않았는지 확인

    # update 메서드에 전달된 인자들을 상세히 검증 (특히 상태 초기화)
    update_args, update_kwargs = item_repo.update.call_args
    assert update_kwargs['title'] == request_data.title
    assert update_kwargs['processing_status'] == 'raw'  # 상태가 'raw'로 초기화되었는지 검증


@pytest.mark.asyncio
async def test_generate_summary_with_recommendations_fallback(clipper_service, mock_session, mocker):
    """
    추천 생성 중 예외 발생 시, generate_webpage_summary_with_recommendations가
    기본 요약/태그/카테고리로 Fallback하는지 테스트합니다.
    """
    # Given (준비)
    service = clipper_service
    request_data = SummarizeRequest(
        url="http://fallback-test.com",
        html_content="<html>...</html>",
        user_id=1
    )
    
    # 의존성 모의 객체 설정
    # 1. 기본 요약은 성공적으로 생성
    service.openai_service.generate_webpage_summary.return_value = "기본 요약입니다."
    
    # 2. UserProfilingService 클래스를 Mocking하여, 메서드 내에서 인스턴스화될 때 mock 객체를 사용하도록 설정
    mock_user_profiling_class = mocker.patch(
        'app.collect.v1.clipper.service.UserProfilingService'
    )
    mock_user_profiling_instance = AsyncMock()
    mock_user_profiling_instance.get_user_top_keywords.side_effect = Exception("Profiling DB Error")
    mock_user_profiling_class.return_value = mock_user_profiling_instance

    # 3. Fallback 로직에서 호출될 AI 서비스의 반환값 설정
    service.openai_service.generate_webpage_tags.return_value = ["fallback_tag"]
    service.openai_service.recommend_webpage_category.return_value = "fallback_category"

    # When (실행)
    result = await service.generate_webpage_summary_with_recommendations(
        session=mock_session,
        request_data=request_data,
        user_id=1,
        tag_count=5
    )

    # Then (검증)
    # - Fallback 로직이 실행되어 기본 요약 정보가 반환되었는지 확인
    assert result["summary"] == "기본 요약입니다."
    assert result["recommended_tags"] == ["fallback_tag"]
    assert result["recommended_category"] == "fallback_category"
    assert result["confidence_score"] == 0.5

    # - 기본 요약 생성은 호출되었는지 확인
    service.openai_service.generate_webpage_summary.assert_called_once()
    # - 예외를 발생시킨 서비스가 호출되었는지 확인
    mock_user_profiling_instance.get_user_top_keywords.assert_called_once()
    # - Fallback 로직의 서비스들이 호출되었는지 확인
    service.openai_service.generate_webpage_tags.assert_called_once()
    service.openai_service.recommend_webpage_category.assert_called_once()


# --- YouTube 관련 새로운 기능 테스트 ---
@pytest.mark.asyncio
async def test_generate_youtube_summary_from_url_with_transcript(clipper_service, mock_session, mocker):
    """
    자막이 있는 YouTube URL에 대한 요약 생성 테스트
    """
    # Given
    service = clipper_service
    url = "https://www.youtube.com/watch?v=test123"
    user_id = 1
    tag_count = 5
    
    # Mock YouTube URL extractor
    mock_extractor = AsyncMock()
    mocker.patch.object(service, 'youtube_url_extractor', mock_extractor)
    
    # Mock 완전한 정보 추출 결과
    complete_info = {
        'extraction_success': True,
        'metadata': {
            'title': '테스트 비디오',
            'description': '테스트 설명',
            'best_thumbnail': 'https://example.com/thumb.jpg'
        },
        'transcript': {
            'success': True,
            'transcript': '테스트 자막 내용',
            'language': 'ko',
            'is_auto_generated': False,
            'extraction_method': 'manual_ko'
        },
        'extraction_timestamp': '2024-01-01T00:00:00'
    }
    mock_extractor.extract_complete_info.return_value = complete_info
    
    # Mock AI 라우터
    mock_ai_router = AsyncMock()
    mocker.patch.object(service, 'ai_router', mock_ai_router)
    
    # Mock 요약 생성
    mock_ai_router.generate_youtube_summary.return_value = "테스트 요약"
    
    # Mock 스마트 추출기
    mock_smart_extractor = AsyncMock()
    mocker.patch.object(service, 'smart_extractor', mock_smart_extractor)
    mock_smart_extractor.extract_youtube_tags_and_category.return_value = {
        'tags': ['테스트', 'YouTube'],
        'category': '교육',
        'metadata': {'processing_method': 'smart'}
    }
    
    # When
    result = await service.generate_youtube_summary_from_url(
        session=mock_session,
        url=url,
        user_id=user_id,
        tag_count=tag_count
    )
    
    # Then
    assert result['success'] is True
    assert result['video_info']['title'] == '테스트 비디오'
    assert result['summary'] == "테스트 요약"
    assert result['tags'] == ['테스트', 'YouTube']
    assert result['category'] == '교육'
    assert result['analysis_method'] == 'full_transcript'
    
    # 자막이 있는 경우 일반적인 YouTube 요약 메서드 호출 확인
    mock_ai_router.generate_youtube_summary.assert_called_once_with(
        title=complete_info['metadata']['title'],
        transcript=complete_info['transcript']['transcript'],
        user_id=user_id
    )


@pytest.mark.asyncio
async def test_generate_youtube_summary_from_url_no_transcript(clipper_service, mock_session, mocker):
    """
    자막이 없는 YouTube URL에 대한 요약 생성 테스트 (메타데이터만 사용)
    """
    # Given
    service = clipper_service
    url = "https://www.youtube.com/watch?v=test456"
    user_id = 1
    tag_count = 3
    
    # Mock YouTube URL extractor
    mock_extractor = AsyncMock()
    mocker.patch.object(service, 'youtube_url_extractor', mock_extractor)
    
    # Mock 자막 없는 상황
    complete_info = {
        'extraction_success': True,
        'metadata': {
            'title': '자막 없는 비디오',
            'description': '자막이 없는 비디오 설명',
            'best_thumbnail': 'https://example.com/thumb2.jpg',
            'tags': ['tag1', 'tag2'],
            'categories': ['엔터테인먼트'],
            'channel': '테스트 채널',
            'duration_formatted': '05:30',
            'view_count': 1000000
        },
        'transcript': {
            'success': False,
            'transcript': '',
            'error': '자막을 사용할 수 없습니다',
            'extraction_method': 'no_transcript_available'
        }
    }
    mock_extractor.extract_complete_info.return_value = complete_info
    
    # Mock AI 라우터 (메타데이터 전용 분석에 필요한 메서드들을 모의)
    mock_ai_router = service.ai_router  # 이미 모의되어 있음
    
    # 메타데이터 전용 분석은 generate_youtube_summary_from_metadata_only 메서드에서 처리
    # 이 메서드에서는 AI 서비스를 직접 호출하므로 여기서는 생략
    pass
    
    # When
    result = await service.generate_youtube_summary_from_url(
        session=mock_session,
        url=url,
        user_id=user_id,
        tag_count=tag_count
    )
    
    # Then
    assert result['success'] is True
    assert result['video_info']['title'] == '자막 없는 비디오'
    assert 'YouTube 영상: 자막 없는 비디오' in result['summary']
    assert 'YouTube' in result['tags']  # 기본 태그가 포함되어야 함
    assert result['category'] == "엔터테인먼트"  # 메타데이터에서 가져온 카테고리
    assert result['analysis_method'] == 'basic_metadata'  # 변경된 분석 방법
    assert 'AI 분석 없이' in result['warning']  # 변경된 경고 메시지
    
    # AI 라우터가 호출되지 않았는지 확인 (자막이 없으므로 AI 사용 안함)
    mock_ai_router.generate_youtube_summary.assert_not_called()
