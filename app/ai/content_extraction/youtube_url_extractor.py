"""
YouTube URL에서 메타데이터와 자막을 자동으로 추출하는 서비스
"""

import re
from typing import Dict, Any, Optional, List
import yt_dlp
from app.core.logging import get_logger

logger = get_logger(__name__)


class YouTubeUrlExtractor:
    """
    YouTube URL에서 메타데이터와 자막을 자동으로 추출하는 클래스
    """
    
    def __init__(self):
        """YouTube URL 추출기 초기화"""
        self.ydl_opts = {
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
        }
        logger.info("YouTubeUrlExtractor initialized")
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """
        YouTube URL에서 비디오 ID를 추출합니다.
        
        Args:
            url: YouTube URL
            
        Returns:
            비디오 ID 또는 None
        """
        try:
            patterns = [
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?.*[?&]v=([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:m\.)?youtube\.com\/watch\?.*[?&]v=([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?(?:m\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)',
                r'(?:https?:\/\/)?youtu\.be\/([a-zA-Z0-9_-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    logger.info(f"Extracted YouTube video ID: {video_id}")
                    return video_id
            
            logger.warning(f"Could not extract video ID from URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting video ID from URL {url}: {e}")
            return None
    
    async def extract_video_metadata(self, url: str) -> Dict[str, Any]:
        """
        YouTube URL에서 비디오 메타데이터를 추출합니다.
        
        Args:
            url: YouTube URL
            
        Returns:
            비디오 메타데이터 딕셔너리
        """
        try:
            logger.info(f"Extracting metadata from YouTube URL: {url}")
            
            # URL 유효성 검사
            if not self._is_valid_youtube_url(url):
                raise ValueError("Invalid YouTube URL format")
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                video_info = ydl.extract_info(url, download=False)
            
            if not video_info:
                raise ValueError("Could not extract video information")
            
            # 비디오 가용성 확인
            availability = video_info.get('availability')
            if availability and availability not in ['public', 'unlisted']:
                raise ValueError(f"Video is not available: {availability}")
            
            # 메타데이터 정제 및 구조화
            metadata = {
                'video_id': video_info.get('id'),
                'title': video_info.get('title', 'Untitled'),
                'description': video_info.get('description', ''),
                'uploader': video_info.get('uploader', 'Unknown'),
                'channel': video_info.get('channel', 'Unknown Channel'),
                'upload_date': video_info.get('upload_date'),
                'duration': video_info.get('duration'),  # seconds
                'view_count': video_info.get('view_count'),
                'like_count': video_info.get('like_count'),
                'thumbnail': video_info.get('thumbnail'),
                'thumbnails': video_info.get('thumbnails', []),
                'tags': video_info.get('tags', []),
                'categories': video_info.get('categories', []),
                'language': video_info.get('language'),
                'availability': video_info.get('availability')
            }
            
            # 썸네일 URL 선택 (가장 고해상도)
            if metadata['thumbnails']:
                best_thumbnail = max(
                    metadata['thumbnails'], 
                    key=lambda x: x.get('width', 0) * x.get('height', 0)
                )
                metadata['best_thumbnail'] = best_thumbnail.get('url')
            else:
                metadata['best_thumbnail'] = metadata['thumbnail']
            
            # 길이 포맷팅
            if metadata['duration']:
                metadata['duration_formatted'] = self._format_duration(metadata['duration'])
            else:
                metadata['duration_formatted'] = "Unknown"
            
            # 업로드 날짜 포맷팅
            if metadata['upload_date']:
                metadata['upload_date_formatted'] = self._format_upload_date(metadata['upload_date'])
            else:
                metadata['upload_date_formatted'] = "Unknown"
            
            logger.info(f"Successfully extracted metadata for video: {metadata['title'][:50]}...")
            return metadata
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to extract metadata from {url}: {error_msg}")
            
            # 상세한 에러 분석 및 사용자 친화적 메시지 제공
            user_friendly_error, suggestions = self._analyze_metadata_error(error_msg, url)
            
            metadata = self._get_empty_metadata_result(url)
            metadata['error'] = user_friendly_error
            metadata['error_suggestions'] = suggestions
            metadata['original_error'] = error_msg  # 디버깅용
            return metadata
    
    async def extract_transcript(
        self, 
        video_id: str, 
        languages: List[str] = ['ko', 'ko-KR', 'en', 'ja', 'es', 'fr', 'de', 'zh', 'pt', 'ru'],
        format_type: str = 'text'
    ) -> Dict[str, Any]:
        """
        YouTube 비디오의 자막을 추출합니다.
        
        새로운 오디오 STT 방식을 사용하여 yt-dlp + Whisper로 자막을 추출합니다.
        (다국어 지원, IP 차단 문제 없음)
        
        Args:
            video_id: YouTube 비디오 ID
            languages: 선호 언어 리스트 (기본값: 주요 10개 언어) - 현재 사용되지 않음
            format_type: 포맷 타입 ('text', 'srt')
            
        Returns:
            자막 정보 딕셔너리
        """
        try:
            logger.info(f"Extracting transcript for video ID: {video_id}")
            
            # 새로운 오디오 STT 시스템으로 자막 추출
            try:
                logger.info(f"Trying new audio STT system for video: {video_id}")
                from app.audio.youtube_stt_service import get_youtube_stt_service
                
                # YouTube URL 재구성
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # STT 서비스로 자막 추출
                stt_service = get_youtube_stt_service()
                
                if stt_service.is_available():
                    stt_result = await stt_service.extract_transcript(youtube_url)
                    
                    # STT 결과를 기존 포맷으로 변환
                    transcript_info = {
                        'video_id': video_id,
                        'transcript': stt_result.transcript,
                        'language': stt_result.language,
                        'is_auto_generated': True,  # STT는 항상 자동 생성
                        'available_languages': [stt_result.language],
                        'format_type': format_type,
                        'success': True,
                        'extraction_method': f'audio_stt_{stt_result.language}',
                        'word_count': len(stt_result.transcript.split()),
                        'char_count': len(stt_result.transcript),
                        'stt_metadata': {
                            'processing_time': stt_result.processing_stats['total_time_seconds'],
                            'efficiency_score': stt_result.processing_stats['efficiency_score'],
                            'video_duration': stt_result.processing_stats['video_duration_seconds'],
                            'model_used': stt_result.metadata['stt_info']['model_used']
                        }
                    }
                    
                    logger.info(f"Audio STT successful: {len(stt_result.transcript)} chars, "
                               f"language: {stt_result.language}, "
                               f"processing time: {stt_result.processing_stats['total_time_seconds']:.1f}s")
                    
                    return transcript_info
                else:
                    logger.warning("Audio STT service not available")
                    
            except Exception as stt_error:
                logger.warning(f"Audio STT failed for {video_id}: {stt_error}")
            
            # 2단계: 폴백 시스템 - 오디오 STT 실패 시 명확한 에러 메시지 제공
            logger.warning(f"Audio STT system failed, no fallback available for video: {video_id}")
            
            return {
                'video_id': video_id,
                'transcript': f"자막 추출에 실패했습니다. 새로운 오디오 STT 시스템을 사용할 수 없는 상태입니다.",
                'language': None,
                'is_auto_generated': False,
                'available_languages': [],
                'format_type': format_type,
                'success': False,
                'extraction_method': 'fallback_failed',
                'word_count': 0,
                'char_count': 0
            }
            
        except Exception as e:
            logger.error(f"Failed to extract transcript for video {video_id}: {e}")
            
            # 자막 추출 오류 분석
            user_friendly_error, suggestions = self._analyze_transcript_error(str(e), video_id)
            
            return {
                'video_id': video_id,
                'transcript': '',
                'language': None,
                'is_auto_generated': False,
                'available_languages': [],
                'format_type': format_type,
                'success': False,
                'error': user_friendly_error,
                'error_suggestions': suggestions,
                'original_error': str(e)  # 디버깅용
            }
    
    async def extract_complete_info(self, url: str) -> Dict[str, Any]:
        """
        YouTube URL에서 메타데이터와 자막을 모두 추출합니다.
        
        Args:
            url: YouTube URL
            
        Returns:
            완전한 비디오 정보 딕셔너리
        """
        try:
            logger.info(f"Extracting complete information from YouTube URL: {url}")
            
            # 1. 비디오 ID 추출
            video_id = self.extract_video_id(url)
            if not video_id:
                raise ValueError("Could not extract video ID from URL")
            
            # 2. 메타데이터 추출
            metadata = await self.extract_video_metadata(url)
            
            # 3. 자막 추출 (새로운 오디오 STT 시스템 사용)
            transcript_info = await self.extract_transcript(video_id)
            
            # 4. 결과 통합
            complete_info = {
                'url': url,
                'extraction_success': True,
                'metadata': metadata,
                'transcript': transcript_info,
                'combined_content': self._create_combined_content(metadata, transcript_info),
                'extraction_timestamp': self._get_current_timestamp()
            }
            
            logger.info(f"Complete extraction successful for: {metadata.get('title', 'Unknown')[:50]}...")
            return complete_info
            
        except Exception as e:
            logger.error(f"Complete extraction failed for {url}: {e}")
            return {
                'url': url,
                'extraction_success': False,
                'error': str(e),
                'metadata': self._get_empty_metadata_result(url),
                'transcript': {
                    'video_id': None,
                    'transcript': '',
                    'success': False,
                    'error': str(e)
                },
                'extraction_timestamp': self._get_current_timestamp()
            }
    
    def _format_duration(self, duration_seconds: int) -> str:
        """초를 시:분:초 형태로 포맷팅"""
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def _format_upload_date(self, upload_date: str) -> str:
        """업로드 날짜 포맷팅 (YYYYMMDD -> YYYY-MM-DD)"""
        try:
            if len(upload_date) == 8:
                return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
            return upload_date
        except:
            return upload_date
    
    def _create_combined_content(self, metadata: Dict, transcript_info: Dict) -> str:
        """메타데이터와 자막을 결합한 텍스트 생성"""
        try:
            parts = []
            
            # 제목
            if metadata.get('title'):
                parts.append(f"제목: {metadata['title']}")
            
            # 설명 (처음 200자만)
            if metadata.get('description'):
                description = metadata['description'][:200]
                if len(metadata['description']) > 200:
                    description += "..."
                parts.append(f"설명: {description}")
            
            # 자막
            if transcript_info.get('transcript'):
                parts.append(f"자막: {transcript_info['transcript']}")
            
            return "\n\n".join(parts)
        except:
            return metadata.get('title', '') + "\n\n" + transcript_info.get('transcript', '')
    
    def _get_empty_metadata_result(self, url: str) -> Dict[str, Any]:
        """빈 메타데이터 결과 반환"""
        return {
            'video_id': None,
            'title': 'Unknown YouTube Video',
            'description': '',
            'uploader': 'Unknown',
            'channel': 'Unknown Channel',
            'upload_date': None,
            'duration': None,
            'view_count': None,
            'like_count': None,
            'thumbnail': None,
            'thumbnails': [],
            'best_thumbnail': None,
            'tags': [],
            'categories': [],
            'language': None,
            'availability': None,
            'duration_formatted': "Unknown",
            'upload_date_formatted': "Unknown"
        }
    
    def _get_current_timestamp(self) -> str:
        """현재 시간의 ISO 포맷 문자열 반환"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _is_valid_youtube_url(self, url: str) -> bool:
        """YouTube URL 유효성 검사"""
        try:
            # 더 간단하고 유연한 YouTube URL 검사
            youtube_domains = [
                'youtube.com',
                'www.youtube.com',
                'm.youtube.com',
                'youtu.be',
                'www.youtu.be'
            ]
            
            # 기본적인 URL 구조 확인
            if not url or len(url.strip()) < 10:
                return False
            
            url_lower = url.lower()
            
            # YouTube 도메인 확인
            for domain in youtube_domains:
                if domain in url_lower:
                    # 비디오 ID 패턴이 있는지 확인
                    if ('v=' in url_lower or 
                        'youtu.be/' in url_lower or 
                        'embed/' in url_lower or 
                        'shorts/' in url_lower):
                        return True
            
            return False
        except:
            return False
    
    def _analyze_metadata_error(self, error_msg: str, url: str) -> tuple[str, list[str]]:
        """메탄데이터 추출 오류 분석 및 사용자 친화적 메시지 생성"""
        error_lower = error_msg.lower()
        suggestions = []
        
        if "video unavailable" in error_lower or "private video" in error_lower:
            user_error = "비디오를 사용할 수 없습니다. 비공개 비디오이거나 삭제된 비디오일 수 있습니다."
            suggestions = [
                "비디오가 여전히 존재하는지 YouTube에서 직접 확인해주세요",
                "공개 비디오인지 확인해주세요",
                "다른 YouTube URL로 다시 시도해주세요"
            ]
        elif "invalid youtube url" in error_lower or "invalid url format" in error_lower:
            user_error = "올바르지 않은 YouTube URL 형식입니다."
            suggestions = [
                "올바른 YouTube URL 형식: https://www.youtube.com/watch?v=VIDEO_ID",
                "https://youtu.be/VIDEO_ID 형식도 지원합니다",
                "URL을 다시 한 번 확인해주세요"
            ]
        elif "sign in to confirm your age" in error_lower or "age" in error_lower:
            user_error = "연령 제한이 있는 비디오입니다. 로그인이 필요한 콘텐츠입니다."
            suggestions = [
                "연령 제한이 없는 비디오로 다시 시도해주세요",
                "커뮤니티 가이드라인에 따라 제한된 콘텐츠일 수 있습니다"
            ]
        elif "network" in error_lower or "timeout" in error_lower or "connection" in error_lower:
            user_error = "네트워크 연결 문제가 발생했습니다."
            suggestions = [
                "인터넷 연결을 확인해주세요",
                "잠시 후 다시 시도해주세요",
                "VPN을 사용 중이라다 비활성화 후 시도해주세요"
            ]
        elif "blocked" in error_lower or "403" in error_lower:
            user_error = "YouTube에서 액세스가 차단되었습니다."
            suggestions = [
                "잠시 후 다시 시도해주세요",
                "너무 많은 요청으로 인한 일시적 제한일 수 있습니다",
                "IP 주소 변경 후 다시 시도해주세요"
            ]
        elif "region" in error_lower or "country" in error_lower:
            user_error = "지역 제한으로 인해 비디오에 액세스할 수 없습니다."
            suggestions = [
                "해당 지역에서 시청 가능한 비디오로 대체해주세요",
                "VPN 사용을 고려해보세요 (합법적 범위 내에서)"
            ]
        else:
            user_error = f"비디오 정보를 가져올 수 없습니다: {error_msg[:100]}..."
            suggestions = [
                "URL이 올바른지 확인해주세요",
                "비디오가 여전히 존재하는지 확인해주세요",
                "잠시 후 다시 시도해주세요"
            ]
        
        return user_error, suggestions
    
    def _analyze_transcript_error(self, error_msg: str, video_id: str) -> tuple[str, list[str]]:
        """자막 추출 오류 분석 및 사용자 친화적 메시지 생성"""
        error_lower = error_msg.lower()
        suggestions = []
        
        if "no transcript" in error_lower or "transcript not available" in error_lower:
            user_error = "이 비디오에는 자막이 제공되지 않습니다."
            suggestions = [
                "비디오 제목과 설명으로 분석됩니다",
                "자막이 있는 다른 비디오를 사용해보세요",
                "채널 주인에게 자막 추가를 요청해보세요"
            ]
        elif "disabled" in error_lower:
            user_error = "이 비디오는 자막이 비활성화되어 있습니다."
            suggestions = [
                "영상 제작자가 자막을 비활성화한 상태입니다",
                "다른 YouTube 비디오를 사용해보세요",
                "비디오 제목과 설명만으로 분석합니다"
            ]
        elif "youtube transcript api" in error_lower:
            user_error = "YouTube 자막 서비스에 연결할 수 없습니다."
            suggestions = [
                "YouTube 서비스에 일시적 문제가 있을 수 있습니다",
                "잠시 후 다시 시도해주세요",
                "많은 요청으로 인한 일시적 제한일 수 있습니다"
            ]
        elif "could not retrieve" in error_lower or "fetch" in error_lower:
            user_error = "자막 데이터를 가져올 수 없습니다."
            suggestions = [
                "비디오 ID가 올바른지 확인해주세요",
                "비디오가 너무 최근에 업로드된 경우일 수 있습니다",
                "잠시 후 다시 시도해주세요"
            ]
        else:
            user_error = f"자막 처리 중 오류가 발생했습니다: {error_msg[:100]}..."
            suggestions = [
                "비디오 URL을 다시 확인해주세요",
                "비디오에 자막이 있는지 확인해주세요",
                "잠시 후 다시 시도해주세요"
            ]
        
        return user_error, suggestions


# 서비스 인스턴스 생성 (싱글톤 패턴)
youtube_url_extractor = YouTubeUrlExtractor()