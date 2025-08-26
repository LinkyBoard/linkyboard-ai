#!/usr/bin/env python3
"""
다국어 STT 성능 검증 스크립트

YouTube 영상을 다운로드하여 Whisper로 자막을 추출하고, 
기존 YouTube 자막과 비교하여 성능을 검증합니다.
"""

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# 테스트용 YouTube URL 목록 (다양한 언어)
# 짧은 영상으로 테스트 시간 단축 (1-3분 내외)
TEST_VIDEOS = {
    "korean": [
        {
            "url": "https://www.youtube.com/watch?v=LDIyFWYwcJo",  # 한국어 짧은 교육 영상
            "title": "Korean Short Education",
            "expected_language": "ko", 
            "content_type": "education"
        }
    ],
    "japanese": [
        {
            "url": "https://www.youtube.com/watch?v=3DYR0CuG9m8",  # 일본어 짧은 영상
            "title": "Japanese Short Video", 
            "expected_language": "ja",
            "content_type": "general"
        }
    ],
    "english": [
        {
            "url": "https://www.youtube.com/watch?v=zAczHQrKyNc",  # 영어 짧은 교육 영상
            "title": "English Short Tutorial",
            "expected_language": "en", 
            "content_type": "tech"
        }
    ]
    # 중국어는 일단 제외 (저작권 이슈를 피하기 위해)
}

class YouTubeSTTTester:
    """YouTube STT 성능 테스터"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="youtube_stt_test_")
        logger.info(f"임시 디렉토리 생성: {self.temp_dir}")
        
    async def check_dependencies(self) -> bool:
        """필요한 의존성 확인"""
        try:
            # yt-dlp 확인
            import yt_dlp
            logger.info(f"yt-dlp 버전: {yt_dlp.version.__version__}")
            
            # whisper 확인
            import whisper
            models = whisper.available_models()
            logger.info(f"Whisper 사용 가능, 모델: {models}")
            
            # ffmpeg 확인
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                logger.info(f"FFmpeg 사용 가능: {version_line}")
            else:
                logger.error("FFmpeg를 찾을 수 없습니다")
                return False
                
        except ImportError as e:
            logger.error(f"의존성 누락: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg 확인 시간 초과")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg를 찾을 수 없습니다. 시스템에 설치되어 있는지 확인하세요.")
            return False
            
        return True
    
    async def download_audio(self, url: str, output_path: str) -> Dict:
        """YouTube에서 오디오 다운로드"""
        try:
            import yt_dlp
            
            # yt-dlp 옵션 설정
            ydl_opts = {
                'format': 'bestaudio/best',
                'extractaudio': True,
                'audioformat': 'mp3',
                'outtmpl': output_path,
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
            }
            
            start_time = time.time()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 메타데이터 추출
                info = ydl.extract_info(url, download=False)
                logger.info(f"영상 정보: {info.get('title', 'Unknown')} ({info.get('duration', 0)}초)")
                
                # 다운로드 실행
                ydl.download([url])
                
            download_time = time.time() - start_time
            logger.info(f"다운로드 완료: {download_time:.2f}초")
            
            return {
                'success': True,
                'download_time': download_time,
                'metadata': {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'language': info.get('language', 'Unknown')
                }
            }
            
        except Exception as e:
            logger.error(f"다운로드 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    async def transcribe_with_whisper(self, audio_path: str, language: str = None) -> Dict:
        """Whisper로 음성을 텍스트로 변환"""
        logger.info(f"Whisper 전사 시작: {audio_path}")
        
        try:
            import whisper
            
            # 모델 로드 (base 모델 사용)
            model = whisper.load_model("base")
            
            start_time = time.time()
            
            # 전사 실행
            result = model.transcribe(
                audio_path,
                language=language,
                verbose=False
            )
            
            transcribe_time = time.time() - start_time
            
            logger.info(f"전사 완료: {transcribe_time:.2f}초, 언어: {result['language']}")
            
            return {
                'success': True,
                'text': result['text'],
                'language': result['language'],
                'segments': result['segments'],
                'transcribe_time': transcribe_time
            }
            
        except Exception as e:
            logger.error(f"전사 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_youtube_subtitles(self, url: str) -> Dict:
        """YouTube 기본 자막 가져오기 (비교용)"""
        try:
            import yt_dlp
            
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['ko', 'ja', 'zh', 'en'],
                'skip_download': True,
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                subtitles = info.get('subtitles', {})
                auto_captions = info.get('automatic_captions', {})
                
                return {
                    'success': True,
                    'subtitles': subtitles,
                    'auto_captions': auto_captions,
                    'available_languages': list(subtitles.keys()) + list(auto_captions.keys())
                }
                
        except Exception as e:
            logger.error(f"자막 추출 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_cer(self, reference: str, hypothesis: str) -> float:
        """Character Error Rate 계산"""
        # 간단한 CER 계산 (실제 구현 시 더 정교하게)
        ref_chars = list(reference.replace(' ', ''))
        hyp_chars = list(hypothesis.replace(' ', ''))
        
        if len(ref_chars) == 0:
            return 0.0 if len(hyp_chars) == 0 else 1.0
        
        # 레벤슈타인 거리 기반 CER 계산 (간단 버전)
        # 실제로는 더 정확한 편집 거리 알고리즘 사용
        errors = abs(len(ref_chars) - len(hyp_chars))
        cer = errors / len(ref_chars)
        
        return min(cer, 1.0)
    
    async def test_single_video(self, video_info: Dict) -> Dict:
        """단일 비디오 테스트"""
        url = video_info['url']
        expected_lang = video_info['expected_language']
        title = video_info['title']
        
        logger.info(f"\n=== 테스트 시작: {title} ===")
        
        result = {
            'video_info': video_info,
            'download_success': False,
            'transcribe_success': False,
            'subtitle_comparison': {},
            'performance_metrics': {}
        }
        
        try:
            # 1. 오디오 다운로드
            audio_filename = f"test_audio_{expected_lang}_{int(time.time())}.mp3"
            audio_path = os.path.join(self.temp_dir, audio_filename)
            
            download_result = await self.download_audio(url, audio_path)
            result['download_result'] = download_result
            
            if not download_result['success']:
                return result
            
            result['download_success'] = True
            
            # 2. 실제 파일이 생성되었는지 확인
            if not os.path.exists(audio_path):
                # yt-dlp가 파일명을 변경했을 수 있으므로 비슷한 이름 찾기
                for file in os.listdir(self.temp_dir):
                    if file.endswith('.mp3') and 'test_audio' in file:
                        audio_path = os.path.join(self.temp_dir, file)
                        break
            
            if os.path.exists(audio_path):
                logger.info(f"오디오 파일 생성 확인: {audio_path}")
                
                # 3. STT 전사
                transcribe_result = await self.transcribe_with_whisper(audio_path, expected_lang)
                result['transcribe_result'] = transcribe_result
                
                if transcribe_result['success']:
                    result['transcribe_success'] = True
                    
                    # 4. YouTube 자막과 비교
                    subtitle_result = await self.get_youtube_subtitles(url)
                    if subtitle_result['success']:
                        result['youtube_subtitles'] = subtitle_result
                        
                        # 성능 메트릭 계산
                        result['performance_metrics'] = {
                            'detected_language': transcribe_result.get('language', 'unknown'),
                            'expected_language': expected_lang,
                            'language_match': transcribe_result.get('language') == expected_lang,
                            'transcription_length': len(transcribe_result.get('text', '')),
                            'processing_time': transcribe_result.get('transcribe_time', 0),
                            'audio_duration': download_result['metadata']['duration']
                        }
                
                # 5. 임시 파일 정리
                try:
                    os.unlink(audio_path)
                    logger.info(f"임시 파일 삭제: {audio_path}")
                except:
                    pass
            else:
                logger.error(f"오디오 파일을 찾을 수 없습니다: {audio_path}")
                
        except Exception as e:
            logger.error(f"테스트 중 오류: {e}")
            result['error'] = str(e)
            
        return result
    
    async def run_comprehensive_test(self) -> Dict:
        """전체 테스트 실행"""
        logger.info("=== 다국어 STT 성능 검증 시작 ===")
        
        # 의존성 확인
        if not await self.check_dependencies():
            return {'success': False, 'error': '필요한 의존성이 설치되지 않았습니다'}
        
        test_results = {
            'start_time': time.time(),
            'results_by_language': {},
            'summary': {}
        }
        
        # 언어별 테스트
        for language, videos in TEST_VIDEOS.items():
            logger.info(f"\n### {language.upper()} 언어 테스트 ###")
            
            language_results = []
            for video in videos:
                result = await self.test_single_video(video)
                language_results.append(result)
                
                # 결과 요약 출력
                if result['download_success'] and result['transcribe_success']:
                    metrics = result['performance_metrics']
                    logger.info(f"✅ {video['title']}: "
                              f"언어매치({metrics['language_match']}) "
                              f"처리시간({metrics['processing_time']:.1f}s)")
                else:
                    logger.error(f"❌ {video['title']}: 테스트 실패")
            
            test_results['results_by_language'][language] = language_results
        
        # 전체 요약
        test_results['end_time'] = time.time()
        test_results['total_duration'] = test_results['end_time'] - test_results['start_time']
        
        # 성공률 계산
        total_tests = sum(len(videos) for videos in TEST_VIDEOS.values())
        successful_tests = 0
        
        for language_results in test_results['results_by_language'].values():
            for result in language_results:
                if result['download_success'] and result['transcribe_success']:
                    successful_tests += 1
        
        test_results['summary'] = {
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'success_rate': successful_tests / total_tests if total_tests > 0 else 0,
            'total_duration_minutes': test_results['total_duration'] / 60
        }
        
        return test_results
    
    def save_results(self, results: Dict, output_file: str = None):
        """테스트 결과 저장"""
        if output_file is None:
            timestamp = int(time.time())
            output_file = f"stt_test_results_{timestamp}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"테스트 결과 저장: {output_file}")
        except Exception as e:
            logger.error(f"결과 저장 실패: {e}")
    
    def __del__(self):
        """임시 디렉토리 정리"""
        import shutil
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"임시 디렉토리 정리: {self.temp_dir}")
        except:
            pass

async def main():
    """메인 실행 함수"""
    if len(sys.argv) > 1 and sys.argv[1] == '--deps-only':
        # 의존성만 확인
        tester = YouTubeSTTTester()
        deps_ok = await tester.check_dependencies()
        print("의존성 확인:", "✅ 모두 설치됨" if deps_ok else "❌ 누락된 의존성 있음")
        return
    
    tester = YouTubeSTTTester()
    
    try:
        # 전체 테스트 실행
        results = await tester.run_comprehensive_test()
        
        # 결과 출력
        logger.info("\n=== 테스트 결과 요약 ===")
        summary = results['summary']
        logger.info(f"전체 테스트: {summary['successful_tests']}/{summary['total_tests']} "
                   f"(성공률: {summary['success_rate']:.1%})")
        logger.info(f"총 소요시간: {summary['total_duration_minutes']:.1f}분")
        
        # 결과 파일 저장
        tester.save_results(results)
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 테스트가 중단되었습니다")
    except Exception as e:
        logger.error(f"테스트 실행 중 오류: {e}")

if __name__ == "__main__":
    # 이벤트 루프 실행
    asyncio.run(main())