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
        어떤 언어의 자막이든 추출하여 AI를 통해 한글로 요약합니다.
        자동 생성, 수동 작성, 번역 등 모든 가능한 자막을 시도합니다.
        
        Args:
            video_id: YouTube 비디오 ID
            languages: 선호 언어 리스트 (기본값: 주요 10개 언어)
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
                'success': False,
                'extraction_method': None  # 추출 방법 추가
            }
            
            # API 인스턴스 생성
            api = YouTubeTranscriptApi()
            
            # TranscriptList를 통해 더 정교한 자막 처리
            try:
                transcript_list = api.list(video_id)
                logger.info(f"Found transcript list for video: {video_id}")
                
                # 사용 가능한 자막 언어 정보 수집
                available_languages = []
                manually_created = []
                auto_generated = []
                
                for transcript in transcript_list:
                    lang_info = {
                        'language_code': transcript.language_code,
                        'language': transcript.language,
                        'is_generated': transcript.is_generated
                    }
                    available_languages.append(lang_info)
                    
                    if transcript.is_generated:
                        auto_generated.append(transcript)
                    else:
                        manually_created.append(transcript)
                
                transcript_info['available_languages'] = available_languages
                logger.info(f"Available languages: {[l['language_code'] for l in available_languages]}")
                logger.info(f"Manual: {len(manually_created)}, Auto: {len(auto_generated)}")
                
                fetched_transcript = None
                selected_language = None
                extraction_method = None
                
                # 1단계: 선호 언어 순서로 수동 작성된 자막 찾기
                for lang in languages:
                    for transcript in manually_created:
                        if transcript.language_code == lang or transcript.language_code.startswith(lang):
                            try:
                                logger.info(f"Found manual transcript in {lang}: {transcript.language_code}")
                                transcript_data = transcript.fetch()
                                fetched_transcript = MockFetchedTranscript(
                                    transcript_data, 
                                    transcript.language_code, 
                                    transcript.language,
                                    transcript.is_generated
                                )
                                selected_language = transcript.language_code
                                extraction_method = f"manual_{lang}"
                                break
                            except Exception as e:
                                logger.debug(f"Failed to fetch manual transcript {lang}: {e}")
                                continue
                    if fetched_transcript:
                        break
                
                # 2단계: 선호 언어 순서로 자동 생성된 자막 찾기
                if not fetched_transcript:
                    for lang in languages:
                        for transcript in auto_generated:
                            if transcript.language_code == lang or transcript.language_code.startswith(lang):
                                try:
                                    logger.info(f"Found auto-generated transcript in {lang}: {transcript.language_code}")
                                    transcript_data = transcript.fetch()
                                    fetched_transcript = MockFetchedTranscript(
                                        transcript_data, 
                                        transcript.language_code, 
                                        transcript.language,
                                        transcript.is_generated
                                    )
                                    selected_language = transcript.language_code
                                    extraction_method = f"auto_{lang}"
                                    break
                                except Exception as e:
                                    logger.debug(f"Failed to fetch auto transcript {lang}: {e}")
                                    continue
                        if fetched_transcript:
                            break
                
                # 2.5단계: 선호 언어가 없으면 모든 수동 자막 시도
                if not fetched_transcript and manually_created:
                    logger.info("Trying any available manual transcript")
                    for transcript in manually_created:
                        try:
                            logger.info(f"Attempting manual transcript: {transcript.language_code}")
                            transcript_data = transcript.fetch()
                            fetched_transcript = MockFetchedTranscript(
                                transcript_data, 
                                transcript.language_code, 
                                transcript.language,
                                transcript.is_generated
                            )
                            selected_language = transcript.language_code
                            extraction_method = f"manual_any_{transcript.language_code}"
                            logger.info(f"Successfully extracted manual transcript: {transcript.language_code}")
                            break
                        except Exception as e:
                            logger.debug(f"Failed to fetch manual transcript {transcript.language_code}: {e}")
                            continue
                
                # 2.7단계: 수동 자막도 없으면 모든 자동 자막 시도
                if not fetched_transcript and auto_generated:
                    logger.info("Trying any available auto-generated transcript")
                    for transcript in auto_generated:
                        try:
                            logger.info(f"Attempting auto transcript: {transcript.language_code}")
                            transcript_data = transcript.fetch()
                            fetched_transcript = MockFetchedTranscript(
                                transcript_data, 
                                transcript.language_code, 
                                transcript.language,
                                transcript.is_generated
                            )
                            selected_language = transcript.language_code
                            extraction_method = f"auto_any_{transcript.language_code}"
                            logger.info(f"Successfully extracted auto transcript: {transcript.language_code}")
                            break
                        except Exception as e:
                            logger.debug(f"Failed to fetch auto transcript {transcript.language_code}: {e}")
                            continue
                
                # 3단계: 번역 자막 시도 (모든 사용 가능한 언어로 번역 시도)
                if not fetched_transcript:
                    logger.info("Trying translated transcripts")
                    # 번역 가능한 자막들을 찾아서 한국어로 번역 시도
                    all_transcripts = manually_created + auto_generated
                    for transcript in all_transcripts:
                        if hasattr(transcript, 'translate'):
                            try:
                                logger.info(f"Attempting to translate {transcript.language_code} to Korean")
                                translated_transcript = transcript.translate('ko')
                                translated_data = translated_transcript.fetch()
                                
                                fetched_transcript = MockFetchedTranscript(
                                    translated_data,
                                    'ko',
                                    f'Korean (Translated from {transcript.language})',
                                    True  # 번역된 자막은 자동 생성으로 표시
                                )
                                selected_language = f"ko-translated-from-{transcript.language_code}"
                                extraction_method = f"translated_ko_from_{transcript.language_code}"
                                logger.info(f"Successfully translated {transcript.language_code} to Korean")
                                break
                            except Exception as translate_error:
                                logger.debug(f"Translation from {transcript.language_code} failed: {translate_error}")
                                continue
                
                # 4단계: DirectAPI로 더 많은 자막 시도
                if not fetched_transcript:
                    logger.info("Trying direct API calls for all possible transcripts")
                    try:
                        # 모든 사용 가능한 자막 목록을 다시 한 번 확인
                        all_available = list(transcript_list)
                        logger.info(f"Total available transcripts: {len(all_available)}")
                        
                        for transcript in all_available:
                            try:
                                logger.info(f"Direct attempt: {transcript.language_code} ({'manual' if not transcript.is_generated else 'auto'})")
                                transcript_data = transcript.fetch()
                                
                                # 데이터 유효성 검사
                                if transcript_data and len(transcript_data) > 0:
                                    fetched_transcript = MockFetchedTranscript(
                                        transcript_data,
                                        transcript.language_code,
                                        transcript.language,
                                        transcript.is_generated
                                    )
                                    selected_language = transcript.language_code
                                    extraction_method = f"direct_api_{transcript.language_code}"
                                    logger.info(f"Successfully extracted via direct API: {transcript.language_code}")
                                    break
                                else:
                                    logger.debug(f"Empty transcript data for {transcript.language_code}")
                            except Exception as e:
                                logger.debug(f"Direct API failed for {transcript.language_code}: {e}")
                                continue
                    except Exception as direct_error:
                        logger.debug(f"Direct API approach failed: {direct_error}")
                        
            except Exception as list_error:
                logger.error(f"Failed to get transcript list: {list_error}")
                # 완전 실패 시 빈 결과 반환
                transcript_info['error'] = f"자막 목록을 가져올 수 없습니다: {str(list_error)}"
                return transcript_info
            
            # 추출된 자막 처리
            if fetched_transcript:
                try:
                    # FetchedTranscript 객체에서 snippets 추출
                    if hasattr(fetched_transcript, 'snippets') and fetched_transcript.snippets:
                        # snippets에서 텍스트만 추출
                        transcript_text_parts = []
                        for snippet in fetched_transcript.snippets:
                            if hasattr(snippet, 'text') and snippet.text.strip():
                                transcript_text_parts.append(snippet.text.strip())
                        
                        formatted_transcript = ' '.join(transcript_text_parts)
                        
                        # 포맷팅 개선
                        formatted_transcript = formatted_transcript.replace('\n', ' ')
                        formatted_transcript = ' '.join(formatted_transcript.split())  # 중복 공백 제거
                        
                        # 언어 정보 추출
                        language = getattr(fetched_transcript, 'language_code', selected_language)
                        if not language:
                            language = getattr(fetched_transcript, 'language', selected_language)
                        
                        # 최소 길이 검사
                        if len(formatted_transcript.strip()) < 10:
                            logger.warning(f"Transcript too short ({len(formatted_transcript)} chars), treating as failed")
                            transcript_info['transcript'] = f"추출된 자막이 너무 짧습니다 ({len(formatted_transcript)}자)."
                            transcript_info['success'] = False
                        else:
                            transcript_info.update({
                                'transcript': formatted_transcript,
                                'language': language,
                                'success': True,
                                'word_count': len(formatted_transcript.split()),
                                'char_count': len(formatted_transcript),
                                'is_auto_generated': getattr(fetched_transcript, 'is_generated', False),
                                'extraction_method': extraction_method
                            })
                            
                            logger.info(f"Successfully extracted transcript via {extraction_method}: {len(formatted_transcript)} chars, "
                                       f"language: {language}, snippets: {len(fetched_transcript.snippets)}")
                    else:
                        logger.warning(f"No snippets found in transcript for video {video_id}")
                        transcript_info['transcript'] = "자막 스니펫을 찾을 수 없습니다."
                        transcript_info['extraction_method'] = "failed_no_snippets"
                        transcript_info['success'] = False
                except Exception as process_error:
                    logger.error(f"Error processing transcript data: {process_error}")
                    transcript_info['transcript'] = f"자막 처리 중 오류 발생: {process_error}"
                    transcript_info['extraction_method'] = "failed_processing"
                    transcript_info['success'] = False
            else:
                logger.warning(f"No transcript available for video {video_id}")
                # 자막이 없는 경우도 사용자에게 명확하게 알림
                if transcript_info.get('available_languages'):
                    available_langs = [f"{lang['language_code']}({'auto' if lang['is_generated'] else 'manual'})" for lang in transcript_info['available_languages']]
                    transcript_info['transcript'] = f"자막을 추출할 수 없습니다. 사용 가능한 언어: {', '.join(available_langs)}"
                else:
                    transcript_info['transcript'] = "이 비디오에는 자막이 제공되지 않습니다."
                transcript_info['extraction_method'] = "no_transcript_available"
                transcript_info['success'] = False
            
            return transcript_info
            
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