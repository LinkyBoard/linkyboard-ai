"""
YouTube Audio Downloader

YouTube 동영상에서 오디오를 추출하여 MP3 파일로 다운로드하는 모듈입니다.
yt-dlp를 사용하여 다양한 YouTube 형식을 지원합니다.
"""

import os
import tempfile
import time
from typing import Dict, Optional, Tuple
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class YouTubeDownloadError(Exception):
    """YouTube 다운로드 관련 오류"""
    pass


class YouTubeAudioDownloader:
    """YouTube 오디오 다운로드 관리자"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        초기화
        
        Args:
            temp_dir: 임시 파일 저장 디렉토리 (None이면 시스템 기본 임시 디렉토리 사용)
        """
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.downloaded_files = []  # 다운로드한 파일들 추적
        
        # yt-dlp 가용성 확인
        try:
            import yt_dlp
            self._yt_dlp = yt_dlp
            self._available = True
            logger.info("YouTubeAudioDownloader 초기화 완료")
        except ImportError:
            logger.error("yt-dlp가 설치되지 않았습니다")
            self._available = False
            raise YouTubeDownloadError("yt-dlp 패키지가 필요합니다. pip install yt-dlp")
    
    def is_available(self) -> bool:
        """다운로더 사용 가능 여부 확인"""
        return self._available
    
    def _generate_filename(self, url: str) -> str:
        """고유한 파일명 생성"""
        timestamp = int(time.time() * 1000)  # 밀리초 단위 타임스탬프
        hash_suffix = abs(hash(url)) % 10000  # URL 기반 해시
        return f"youtube_audio_{timestamp}_{hash_suffix}"
    
    def _get_yt_dlp_options(self, output_path: str) -> Dict:
        """yt-dlp 옵션 설정"""
        return {
            'format': 'bestaudio[ext=mp3]/best[ext=mp3]/bestaudio',
            'outtmpl': output_path,
            'noplaylist': True,
            'extract_flat': False,
            'quiet': True,
            'no_warnings': True,
            'prefer_ffmpeg': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }
    
    async def download_audio(
        self, 
        url: str, 
        max_duration_seconds: int = 1800  # 30분 제한
    ) -> Tuple[str, Dict]:
        """
        YouTube URL에서 오디오 다운로드
        
        Args:
            url: YouTube 동영상 URL
            max_duration_seconds: 최대 동영상 길이 (초)
            
        Returns:
            Tuple[str, Dict]: (다운로드된 파일 경로, 메타데이터)
            
        Raises:
            YouTubeDownloadError: 다운로드 실패 시
        """
        if not self.is_available():
            raise YouTubeDownloadError("YouTube 다운로더를 사용할 수 없습니다")
        
        # 고유한 파일명 생성
        base_filename = self._generate_filename(url)
        output_template = os.path.join(self.temp_dir, base_filename + ".%(ext)s")
        
        try:
            logger.info(f"YouTube 오디오 다운로드 시작: {url}")
            start_time = time.time()
            
            # yt-dlp 옵션 설정
            ydl_opts = self._get_yt_dlp_options(output_template)
            
            # 메타데이터와 오디오 다운로드
            with self._yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 먼저 메타데이터만 추출하여 시간 확인
                info = ydl.extract_info(url, download=False)
                
                # 동영상 길이 확인
                duration = info.get('duration', 0)
                if duration > max_duration_seconds:
                    raise YouTubeDownloadError(
                        f"동영상이 너무 깁니다 ({duration}초). 최대 {max_duration_seconds}초까지 지원합니다."
                    )
                
                # 실제 다운로드 실행
                ydl.download([url])
            
            download_time = time.time() - start_time
            
            # 실제 생성된 파일 찾기 (yt-dlp가 확장자를 변경할 수 있음)
            audio_file_path = self._find_downloaded_file(base_filename)
            
            if not audio_file_path or not os.path.exists(audio_file_path):
                raise YouTubeDownloadError("다운로드된 오디오 파일을 찾을 수 없습니다")
            
            # 다운로드한 파일 추적
            self.downloaded_files.append(audio_file_path)
            
            # 메타데이터 구성
            metadata = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
                'language': info.get('language', 'unknown'),
                'file_size': os.path.getsize(audio_file_path),
                'download_time': download_time,
                'format_info': {
                    'format_id': info.get('format_id', ''),
                    'ext': info.get('ext', ''),
                    'acodec': info.get('acodec', ''),
                    'abr': info.get('abr', 0),  # audio bitrate
                }
            }
            
            logger.info(
                f"YouTube 오디오 다운로드 완료: {audio_file_path} "
                f"({duration}초, {download_time:.2f}초 소요)"
            )
            
            return audio_file_path, metadata
            
        except self._yt_dlp.DownloadError as e:
            error_msg = f"yt-dlp 다운로드 오류: {str(e)}"
            logger.error(error_msg)
            raise YouTubeDownloadError(error_msg)
        except Exception as e:
            error_msg = f"YouTube 오디오 다운로드 실패: {str(e)}"
            logger.error(error_msg)
            raise YouTubeDownloadError(error_msg)
    
    def _find_downloaded_file(self, base_filename: str) -> Optional[str]:
        """다운로드된 파일 경로 찾기"""
        possible_extensions = ['.mp3', '.m4a', '.wav', '.opus', '.aac']
        
        for ext in possible_extensions:
            file_path = os.path.join(self.temp_dir, base_filename + ext)
            if os.path.exists(file_path):
                return file_path
        
        # 확장자가 다를 수 있으므로 디렉토리에서 패턴 검색
        for file in os.listdir(self.temp_dir):
            if file.startswith(base_filename) and any(file.endswith(ext) for ext in possible_extensions):
                return os.path.join(self.temp_dir, file)
        
        return None
    
    def cleanup_file(self, file_path: str) -> bool:
        """특정 파일 삭제"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                if file_path in self.downloaded_files:
                    self.downloaded_files.remove(file_path)
                logger.debug(f"임시 오디오 파일 삭제: {file_path}")
                return True
        except Exception as e:
            logger.warning(f"파일 삭제 실패 {file_path}: {e}")
        return False
    
    def cleanup_all(self) -> int:
        """다운로드한 모든 파일 삭제"""
        cleaned_count = 0
        for file_path in self.downloaded_files.copy():
            if self.cleanup_file(file_path):
                cleaned_count += 1
        
        logger.info(f"임시 오디오 파일 {cleaned_count}개 정리 완료")
        return cleaned_count
    
    def get_video_info(self, url: str) -> Dict:
        """
        다운로드 없이 비디오 정보만 추출
        
        Args:
            url: YouTube 동영상 URL
            
        Returns:
            Dict: 비디오 메타데이터
            
        Raises:
            YouTubeDownloadError: 정보 추출 실패 시
        """
        if not self.is_available():
            raise YouTubeDownloadError("YouTube 다운로더를 사용할 수 없습니다")
        
        try:
            logger.debug(f"YouTube 비디오 정보 추출: {url}")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with self._yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
                'description': info.get('description', '')[:500],  # 처음 500자만
                'language': info.get('language', 'unknown'),
                'availability': info.get('availability', 'unknown'),
                'formats_available': len(info.get('formats', [])),
            }
            
        except self._yt_dlp.DownloadError as e:
            error_msg = f"yt-dlp 정보 추출 오류: {str(e)}"
            logger.error(error_msg)
            raise YouTubeDownloadError(error_msg)
        except Exception as e:
            error_msg = f"YouTube 비디오 정보 추출 실패: {str(e)}"
            logger.error(error_msg)
            raise YouTubeDownloadError(error_msg)
    
    def __del__(self):
        """소멸자: 정리되지 않은 파일들 정리"""
        try:
            if hasattr(self, 'downloaded_files') and self.downloaded_files:
                self.cleanup_all()
        except:
            pass  # 소멸자에서는 오류를 무시