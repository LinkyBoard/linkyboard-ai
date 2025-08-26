#!/usr/bin/env python3
"""
빠른 다국어 STT 테스트
간단한 YouTube 영상 하나로 전체 파이프라인 테스트
"""

import os
import tempfile
import time
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

async def quick_test():
    """빠른 테스트 실행"""
    
    # 테스트할 YouTube URL (공개 교육 영상)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll (일반적으로 사용 가능)  
    
    # 임시 디렉토리 생성
    with tempfile.TemporaryDirectory(prefix="quick_stt_test_") as temp_dir:
        logger.info(f"임시 디렉토리: {temp_dir}")
        
        try:
            # 1. YouTube 오디오 다운로드
            logger.info("=== 1단계: YouTube 오디오 다운로드 ===")
            import yt_dlp
            
            audio_file = os.path.join(temp_dir, "test_audio.mp3")
            
            ydl_opts = {
                'format': 'bestaudio[ext=mp3]/best[ext=mp3]/bestaudio',
                'outtmpl': audio_file,
                'noplaylist': True,
            }
            
            download_start = time.time()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
                logger.info(f"영상 정보: {info.get('title', 'Unknown')} ({info.get('duration', 0)}초)")
                ydl.download([test_url])
            
            download_time = time.time() - download_start
            logger.info(f"다운로드 완료: {download_time:.2f}초")
            
            # 실제 생성된 파일 찾기 (yt-dlp가 파일명을 변경할 수 있음)
            audio_files = [f for f in os.listdir(temp_dir) if f.endswith(('.mp3', '.m4a', '.wav'))]
            if audio_files:
                actual_audio_file = os.path.join(temp_dir, audio_files[0])
                logger.info(f"오디오 파일 확인: {actual_audio_file}")
            else:
                logger.error("오디오 파일을 찾을 수 없습니다")
                return
            
            # 2. Whisper STT 처리
            logger.info("=== 2단계: Whisper STT 처리 ===")
            import whisper
            import ssl
            
            # SSL 인증 문제 우회
            ssl._create_default_https_context = ssl._create_unverified_context
            
            model = whisper.load_model("base")
            logger.info("Whisper base 모델 로드 완료")
            
            transcribe_start = time.time()
            result = model.transcribe(actual_audio_file, verbose=False)
            transcribe_time = time.time() - transcribe_start
            
            logger.info(f"전사 완료: {transcribe_time:.2f}초")
            logger.info(f"감지된 언어: {result['language']}")
            logger.info(f"전사 텍스트 길이: {len(result['text'])} 문자")
            
            # 3. 결과 출력
            logger.info("=== 3단계: 결과 분석 ===")
            
            text = result['text'].strip()
            segments = result['segments']
            
            logger.info(f"\n--- 전사 결과 ---")
            logger.info(f"언어: {result['language']}")
            logger.info(f"전체 텍스트: {text[:200]}{'...' if len(text) > 200 else ''}")
            logger.info(f"세그먼트 수: {len(segments)}")
            
            # 처리 시간 분석
            video_duration = info.get('duration', 0)
            if video_duration > 0:
                processing_ratio = transcribe_time / video_duration
                logger.info(f"처리 시간 비율: {processing_ratio:.2f}x (영상 {video_duration}초 → 처리 {transcribe_time:.1f}초)")
            
            # 4. YouTube 자막과 비교 (가능한 경우)
            logger.info("=== 4단계: YouTube 자막 비교 ===")
            try:
                ydl_subtitle_opts = {
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['en', 'ko', 'ja'],
                    'skip_download': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_subtitle_opts) as ydl:
                    info_with_subs = ydl.extract_info(test_url, download=False)
                    available_subs = list(info_with_subs.get('subtitles', {}).keys())
                    available_auto = list(info_with_subs.get('automatic_captions', {}).keys())
                    
                    logger.info(f"사용 가능한 자막: {available_subs}")
                    logger.info(f"자동 생성 자막: {available_auto}")
                    
            except Exception as e:
                logger.warning(f"자막 정보 확인 실패: {e}")
            
            # 5. 성능 요약
            logger.info("=== 성능 요약 ===")
            logger.info(f"✅ 다운로드: {download_time:.1f}초")
            logger.info(f"✅ STT 처리: {transcribe_time:.1f}초")  
            logger.info(f"✅ 전체 소요: {download_time + transcribe_time:.1f}초")
            logger.info(f"✅ 언어 감지: {result['language']} ({'✅ 정확' if result['language'] == 'en' else '⚠️ 부정확'})")
            logger.info(f"✅ 전사 품질: {len(text)} 문자, {len(segments)} 세그먼트")
            
            return {
                'success': True,
                'download_time': download_time,
                'transcribe_time': transcribe_time,
                'detected_language': result['language'],
                'text_length': len(text),
                'segments_count': len(segments),
                'video_duration': video_duration
            }
            
        except Exception as e:
            logger.error(f"테스트 실패: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    asyncio.run(quick_test())