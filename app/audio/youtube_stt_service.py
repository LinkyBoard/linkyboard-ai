"""
YouTube Speech-to-Text Service

YouTube 동영상에서 MP3를 다운로드하고 Whisper로 STT를 수행하는 통합 서비스입니다.
기존 YouTube Transcript API를 대체하는 새로운 접근 방식을 제공합니다.
"""

import asyncio
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from .youtube_downloader import YouTubeAudioDownloader, YouTubeDownloadError
from .whisper_stt import WhisperSTTProcessor, WhisperSTTResult, WhisperSTTError
from .temp_file_manager import get_temp_manager, TempFileManagerError
from app.core.logging import get_logger

logger = get_logger(__name__)


class YouTubeSTTServiceError(Exception):
    """YouTube STT 서비스 관련 오류"""
    pass


class YouTubeSTTResult:
    """YouTube STT 결과 클래스"""
    
    def __init__(
        self,
        transcript: str,
        language: str,
        metadata: Dict,
        processing_stats: Dict
    ):
        self.transcript = transcript
        self.language = language
        self.metadata = metadata
        self.processing_stats = processing_stats
    
    def to_dict(self) -> Dict:
        """결과를 딕셔너리로 변환"""
        return {
            'transcript': self.transcript,
            'language': self.language,
            'metadata': self.metadata,
            'processing_stats': self.processing_stats,
            'success': True
        }


class YouTubeSTTService:
    """YouTube STT 통합 서비스"""
    
    def __init__(
        self,
        whisper_model: str = "base",
        max_video_duration: int = 1800,  # 30분
        enable_temp_file_management: bool = True
    ):
        """
        YouTube STT 서비스 초기화
        
        Args:
            whisper_model: 사용할 Whisper 모델
            max_video_duration: 최대 동영상 길이 (초)
            enable_temp_file_management: 임시 파일 관리 활성화
        """
        self.max_video_duration = max_video_duration
        self.enable_temp_file_management = enable_temp_file_management
        
        # 컴포넌트 초기화
        try:
            self.downloader = YouTubeAudioDownloader()
            self.stt_processor = WhisperSTTProcessor(whisper_model)
            
            if enable_temp_file_management:
                self.temp_manager = get_temp_manager()
            else:
                self.temp_manager = None
            
            self._available = True
            logger.info(f"YouTubeSTTService 초기화 완료 (모델: {whisper_model})")
            
        except Exception as e:
            logger.error(f"YouTubeSTTService 초기화 실패: {str(e)}")
            self._available = False
            raise YouTubeSTTServiceError(f"서비스 초기화 실패: {str(e)}")
    
    def is_available(self) -> bool:
        """서비스 사용 가능 여부 확인"""
        return (
            self._available and
            self.downloader.is_available() and
            self.stt_processor.is_available()
        )
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """YouTube URL에서 비디오 ID 추출"""
        try:
            parsed = urlparse(url)
            
            if 'youtube.com' in parsed.netloc:
                query_params = parse_qs(parsed.query)
                return query_params.get('v', [None])[0]
            elif 'youtu.be' in parsed.netloc:
                return parsed.path.lstrip('/')
            
            return None
        except Exception:
            return None
    
    def _is_valid_youtube_url(self, url: str) -> bool:
        """유효한 YouTube URL인지 확인"""
        video_id = self._extract_video_id(url)
        return video_id is not None and len(video_id) == 11
    
    async def extract_transcript(
        self,
        youtube_url: str,
        language_hint: Optional[str] = None,
        task: str = "transcribe"
    ) -> YouTubeSTTResult:
        """
        YouTube URL에서 자막 추출
        
        Args:
            youtube_url: YouTube 동영상 URL
            language_hint: 언어 힌트 (None이면 자동 감지)
            task: 'transcribe' 또는 'translate' (영어로 번역)
            
        Returns:
            YouTubeSTTResult: STT 결과
            
        Raises:
            YouTubeSTTServiceError: 처리 실패 시
        """
        if not self.is_available():
            raise YouTubeSTTServiceError("YouTube STT 서비스를 사용할 수 없습니다")
        
        if not self._is_valid_youtube_url(youtube_url):
            raise YouTubeSTTServiceError(f"유효하지 않은 YouTube URL: {youtube_url}")
        
        video_id = self._extract_video_id(youtube_url)
        logger.info(f"YouTube STT 처리 시작: {video_id}")
        
        start_time = time.time()
        audio_file_path = None
        
        try:
            # 1단계: YouTube 오디오 다운로드
            logger.info("YouTube 오디오 다운로드 시작")
            download_start = time.time()
            
            audio_file_path, download_metadata = await self.downloader.download_audio(
                youtube_url,
                max_duration_seconds=self.max_video_duration
            )
            
            download_time = time.time() - download_start
            logger.info(f"오디오 다운로드 완료: {download_time:.2f}초")
            
            # 임시 파일 관리자에 등록
            if self.temp_manager:
                self.temp_manager.register_file(audio_file_path, f"youtube_audio_{video_id}")
            
            # 2단계: Whisper STT 처리
            logger.info("Whisper STT 처리 시작")
            stt_start = time.time()
            
            stt_result: WhisperSTTResult = await self.stt_processor.transcribe_audio(
                audio_file_path,
                language=language_hint,
                task=task,
                temperature=0.0,
                best_of=5,
                word_timestamps=False
            )
            
            stt_time = time.time() - stt_start
            total_time = time.time() - start_time
            
            # 3단계: 결과 구성
            metadata = {
                'video_id': video_id,
                'video_url': youtube_url,
                'video_info': {
                    'title': download_metadata.get('title', 'Unknown'),
                    'duration': download_metadata.get('duration', 0),
                    'uploader': download_metadata.get('uploader', 'Unknown'),
                    'upload_date': download_metadata.get('upload_date', ''),
                    'view_count': download_metadata.get('view_count', 0)
                },
                'audio_info': {
                    'file_size_mb': download_metadata.get('file_size', 0) / 1024 / 1024,
                    'format': download_metadata.get('format_info', {}),
                    'bitrate': download_metadata.get('format_info', {}).get('abr', 0)
                },
                'stt_info': {
                    'model_used': stt_result.model_used,
                    'detected_language': stt_result.language,
                    'segments_count': len(stt_result.segments),
                    'confidence_avg': sum(stt_result.confidence_scores) / len(stt_result.confidence_scores) if stt_result.confidence_scores else 0.0
                }
            }
            
            processing_stats = {
                'download_time_seconds': download_time,
                'stt_time_seconds': stt_time,
                'total_time_seconds': total_time,
                'video_duration_seconds': download_metadata.get('duration', 0),
                'processing_ratio': stt_time / max(download_metadata.get('duration', 1), 1),
                'characters_extracted': len(stt_result.text),
                'words_per_minute': self._calculate_wpm(stt_result.text, download_metadata.get('duration', 0)),
                'efficiency_score': self._calculate_efficiency_score(
                    total_time, 
                    download_metadata.get('duration', 0),
                    len(stt_result.text)
                )
            }
            
            logger.info(
                f"YouTube STT 완료: {video_id}, "
                f"언어: {stt_result.language}, "
                f"길이: {len(stt_result.text)}자, "
                f"처리시간: {total_time:.2f}초"
            )
            
            return YouTubeSTTResult(
                transcript=stt_result.text,
                language=stt_result.language,
                metadata=metadata,
                processing_stats=processing_stats
            )
            
        except YouTubeDownloadError as e:
            error_msg = f"YouTube 다운로드 실패: {str(e)}"
            logger.error(error_msg)
            raise YouTubeSTTServiceError(error_msg)
            
        except WhisperSTTError as e:
            error_msg = f"Whisper STT 실패: {str(e)}"
            logger.error(error_msg)
            raise YouTubeSTTServiceError(error_msg)
            
        except Exception as e:
            error_msg = f"YouTube STT 처리 중 예상치 못한 오류: {str(e)}"
            logger.error(error_msg)
            raise YouTubeSTTServiceError(error_msg)
            
        finally:
            # 임시 파일 정리
            if audio_file_path:
                try:
                    if self.temp_manager:
                        self.temp_manager.cleanup_file(audio_file_path)
                    else:
                        self.downloader.cleanup_file(audio_file_path)
                except Exception as e:
                    logger.warning(f"임시 파일 정리 실패: {e}")
    
    def _calculate_wpm(self, text: str, duration_seconds: float) -> float:
        """분당 단어 수 계산"""
        if duration_seconds <= 0:
            return 0.0
        
        word_count = len(text.split())
        minutes = duration_seconds / 60
        return word_count / minutes if minutes > 0 else 0.0
    
    def _calculate_efficiency_score(
        self, 
        processing_time: float, 
        video_duration: float, 
        text_length: int
    ) -> float:
        """처리 효율성 점수 계산 (0-100)"""
        if processing_time <= 0 or video_duration <= 0 or text_length <= 0:
            return 0.0
        
        # 시간 효율성 (처리 시간 / 비디오 길이가 낮을수록 좋음)
        time_efficiency = min(100, (video_duration / processing_time) * 10)
        
        # 텍스트 밀도 (분당 추출된 문자 수)
        text_density = (text_length / (video_duration / 60)) / 10  # 분당 1000자를 100점으로
        text_density = min(100, text_density)
        
        # 종합 점수 (시간 효율성 70%, 텍스트 밀도 30%)
        efficiency_score = (time_efficiency * 0.7) + (text_density * 0.3)
        
        return round(efficiency_score, 2)
    
    async def get_video_info(self, youtube_url: str) -> Dict:
        """
        다운로드 없이 비디오 정보만 조회
        
        Args:
            youtube_url: YouTube 동영상 URL
            
        Returns:
            Dict: 비디오 정보
        """
        if not self.is_available():
            raise YouTubeSTTServiceError("YouTube STT 서비스를 사용할 수 없습니다")
        
        if not self._is_valid_youtube_url(youtube_url):
            raise YouTubeSTTServiceError(f"유효하지 않은 YouTube URL: {youtube_url}")
        
        try:
            video_info = self.downloader.get_video_info(youtube_url)
            video_info['video_id'] = self._extract_video_id(youtube_url)
            video_info['estimated_stt_time'] = self.stt_processor.estimate_processing_time(
                video_info.get('duration', 0)
            )
            return video_info
            
        except Exception as e:
            error_msg = f"비디오 정보 조회 실패: {str(e)}"
            logger.error(error_msg)
            raise YouTubeSTTServiceError(error_msg)
    
    def get_service_stats(self) -> Dict:
        """서비스 통계 반환"""
        stats = {
            'service_available': self.is_available(),
            'max_video_duration': self.max_video_duration,
            'temp_file_management': self.enable_temp_file_management,
            'downloader_available': self.downloader.is_available() if hasattr(self, 'downloader') else False,
            'stt_available': self.stt_processor.is_available() if hasattr(self, 'stt_processor') else False,
        }
        
        if hasattr(self, 'stt_processor'):
            stats['stt_model_info'] = self.stt_processor.get_model_info()
        
        if self.temp_manager:
            stats['temp_file_stats'] = self.temp_manager.get_stats()
        
        return stats
    
    async def cleanup_resources(self):
        """리소스 정리"""
        try:
            if hasattr(self, 'downloader'):
                self.downloader.cleanup_all()
            
            if hasattr(self, 'stt_processor'):
                self.stt_processor.unload_model()
            
            if self.temp_manager:
                self.temp_manager.cleanup_all()
                
            logger.info("YouTube STT 서비스 리소스 정리 완료")
            
        except Exception as e:
            logger.warning(f"리소스 정리 중 오류: {e}")


# 글로벌 서비스 인스턴스 (레이지 로딩)
_global_service: Optional[YouTubeSTTService] = None


def get_youtube_stt_service() -> YouTubeSTTService:
    """글로벌 YouTube STT 서비스 인스턴스 반환"""
    global _global_service
    
    if _global_service is None:
        _global_service = YouTubeSTTService()
    
    return _global_service