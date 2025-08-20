"""
YouTube URL에서 메타데이터와 자막을 자동으로 추출하는 서비스
"""

import re
from typing import Dict, Any, Optional, List
import yt_dlp
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import SRTFormatter, TextFormatter
    TRANSCRIPT_API_AVAILABLE = True
except ImportError as e:
    print(f"Warning: YouTube Transcript API not available: {e}")
    TRANSCRIPT_API_AVAILABLE = False
from app.core.logging import get_logger

logger = get_logger(__name__)


class MockFetchedTranscript:
    """FetchedTranscript 호환 클래스"""
    def __init__(self, snippets_data, language_code, language, is_generated=False):
        self.language_code = language_code
        self.language = language
        self.is_generated = is_generated
        # snippets 데이터를 MockSnippet으로 변환
        self.snippets = []
        for item in snippets_data:
            if hasattr(item, 'text'):
                # 이미 FetchedTranscriptSnippet 객체인 경우
                self.snippets.append(item)
            elif isinstance(item, dict) and 'text' in item:
                # 딕셔너리 형태인 경우
                mock_snippet = type('MockSnippet', (), {'text': item['text']})()
                self.snippets.append(mock_snippet)
            else:
                # 다른 형태인 경우 그대로 추가 (text 속성이 있는지 확인)
                self.snippets.append(item)


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
            
            # 특정 오류 타입에 따른 상세한 에러 메시지
            if "Video unavailable" in error_msg or "Private video" in error_msg:
                error_msg = "비디오를 사용할 수 없습니다 (비공개 또는 삭제됨)"
            elif "Invalid YouTube URL" in error_msg:
                error_msg = "올바르지 않은 YouTube URL입니다"
            elif "Sign in to confirm your age" in error_msg:
                error_msg = "연령 제한이 있는 비디오입니다"
            elif "network" in error_msg.lower() or "timeout" in error_msg.lower():
                error_msg = "네트워크 오류가 발생했습니다"
            else:
                error_msg = f"메타데이터 추출 실패: {error_msg}"
            
            metadata = self._get_empty_metadata_result(url)
            metadata['error'] = error_msg
            return metadata
    
    async def extract_transcript(
        self, 
        video_id: str, 
        languages: List[str] = ['ko', 'ko-KR', 'en', 'ja'],
        format_type: str = 'text'
    ) -> Dict[str, Any]:
        """
        YouTube 비디오의 자막을 추출합니다.
        
        Args:
            video_id: YouTube 비디오 ID
            languages: 선호 언어 리스트
            format_type: 포맷 타입 ('text', 'srt')
            
        Returns:
            자막 정보 딕셔너리
        """
        try:
            logger.info(f"Extracting transcript for video ID: {video_id}")
            
            # API 사용 가능성 확인
            if not TRANSCRIPT_API_AVAILABLE:
                raise Exception("YouTube Transcript API is not available")
            
            transcript_info = {
                'video_id': video_id,
                'transcript': '',
                'language': None,
                'is_auto_generated': False,
                'available_languages': [],
                'format_type': format_type,
                'success': False
            }
            
            # API 인스턴스 생성
            api = YouTubeTranscriptApi()
            
            # TranscriptList를 통해 더 정교한 자막 처리
            try:
                transcript_list = api.list(video_id)
                logger.info(f"Found transcript list for video: {video_id}")
                
                fetched_transcript = None
                selected_language = None
                
                # 선호 언어 순서대로 자막 추출 시도
                for lang in languages:
                    try:
                        logger.info(f"Trying to find transcript in language: {lang}")
                        transcript = transcript_list.find_transcript([lang])
                        fetched_transcript = transcript.fetch()
                        selected_language = transcript.language_code
                        logger.info(f"Successfully found transcript in {lang}")
                        
                        # FetchedTranscript 객체로 변환 (기존 코드와 호환성 위해)
                        fetched_transcript = MockFetchedTranscript(
                            fetched_transcript, 
                            transcript.language_code, 
                            transcript.language,
                            transcript.is_generated
                        )
                        break
                        
                    except Exception as lang_error:
                        logger.debug(f"Failed to get transcript in {lang}: {lang_error}")
                        continue
                
                # 선호 언어가 없으면 한국어 번역 자막 시도
                if not fetched_transcript and 'ko' in languages:
                    try:
                        logger.info("Trying to fetch Korean translated transcript")
                        # 영어 자막을 한국어로 번역
                        english_transcript = transcript_list.find_transcript(['en'])
                        if english_transcript and hasattr(english_transcript, 'translate'):
                            translated_transcript = english_transcript.translate('ko')
                            translated_data = translated_transcript.fetch()
                            
                            fetched_transcript = MockFetchedTranscript(
                                translated_data,
                                'ko',
                                'Korean (Translated)',
                                True  # 번역된 자막은 자동 생성으로 표시
                            )
                            selected_language = "ko-translated"
                            logger.info("Successfully got Korean translated transcript")
                        
                    except Exception as translate_error:
                        logger.debug(f"Failed to get translated transcript: {translate_error}")
                
                # 여전히 없으면 기본 언어로 시도
                if not fetched_transcript:
                    try:
                        logger.info("Trying to fetch transcript in any available language")
                        # 첫 번째 사용 가능한 자막 사용
                        available_transcript = transcript_list.find_transcript(['en'])  # 영어가 가장 일반적
                        transcript_data = available_transcript.fetch()
                        
                        fetched_transcript = MockFetchedTranscript(
                            transcript_data,
                            available_transcript.language_code,
                            available_transcript.language,
                            available_transcript.is_generated
                        )
                        selected_language = available_transcript.language_code
                        logger.info(f"Got transcript in {selected_language}")
                        
                    except Exception as default_error:
                        logger.debug(f"Failed to get any transcript: {default_error}")
                        
            except Exception as list_error:
                logger.error(f"Failed to get transcript list: {list_error}")
                # Fallback to original method
                fetched_transcript = None
                selected_language = None
            
            if fetched_transcript:
                try:
                    # FetchedTranscript 객체에서 snippets 추출
                    if hasattr(fetched_transcript, 'snippets') and fetched_transcript.snippets:
                        # snippets에서 텍스트만 추출
                        transcript_text_parts = []
                        for snippet in fetched_transcript.snippets:
                            if hasattr(snippet, 'text'):
                                transcript_text_parts.append(snippet.text)
                        
                        formatted_transcript = ' '.join(transcript_text_parts)
                        
                        # 포맷팅 (간단한 정리)
                        formatted_transcript = formatted_transcript.replace('\n', ' ')
                        formatted_transcript = ' '.join(formatted_transcript.split())  # 중복 공백 제거
                        
                        # 언어 정보 추출
                        language = getattr(fetched_transcript, 'language_code', selected_language)
                        if not language:
                            language = getattr(fetched_transcript, 'language', selected_language)
                        
                        transcript_info.update({
                            'transcript': formatted_transcript,
                            'language': language,
                            'success': True,
                            'word_count': len(formatted_transcript.split()),
                            'char_count': len(formatted_transcript),
                            'is_auto_generated': getattr(fetched_transcript, 'is_generated', False)
                        })
                        
                        logger.info(f"Successfully extracted transcript: {len(formatted_transcript)} chars, "
                                   f"language: {language}, snippets: {len(fetched_transcript.snippets)}")
                    else:
                        logger.warning(f"No snippets found in transcript for video {video_id}")
                        transcript_info['transcript'] = "자막 스니펫을 찾을 수 없습니다."
                except Exception as process_error:
                    logger.error(f"Error processing transcript data: {process_error}")
                    transcript_info['transcript'] = f"자막 처리 중 오류 발생: {process_error}"
            else:
                logger.warning(f"No transcript available for video {video_id}")
                transcript_info['transcript'] = "자막을 사용할 수 없습니다."
            
            return transcript_info
            
        except Exception as e:
            logger.error(f"Failed to extract transcript for video {video_id}: {e}")
            return {
                'video_id': video_id,
                'transcript': '',
                'language': None,
                'is_auto_generated': False,
                'available_languages': [],
                'format_type': format_type,
                'success': False,
                'error': str(e)
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
            
            # 3. 자막 추출
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


# 서비스 인스턴스 생성 (싱글톤 패턴)
youtube_url_extractor = YouTubeUrlExtractor()