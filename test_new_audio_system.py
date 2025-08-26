#!/usr/bin/env python3
"""
새로운 오디오 시스템 테스트

구현한 YouTube STT 시스템의 기본 동작을 검증합니다.
"""

import asyncio
import ssl
import os
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.audio.youtube_stt_service import get_youtube_stt_service, YouTubeSTTServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_new_audio_system():
    """새 오디오 시스템 기본 테스트"""
    # SSL 인증 문제 우회
    ssl._create_default_https_context = ssl._create_unverified_context
    
    print("=== 새로운 YouTube STT 시스템 테스트 ===\n")
    
    try:
        # 서비스 인스턴스 가져오기
        service = get_youtube_stt_service()
        
        # 1. 서비스 가용성 확인
        print("1. 서비스 가용성 확인")
        if service.is_available():
            print("✅ 서비스 사용 가능")
        else:
            print("❌ 서비스 사용 불가")
            return
        
        # 2. 서비스 통계 출력
        print("\n2. 서비스 통계")
        stats = service.get_service_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        # 3. 테스트 YouTube URL
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll
        
        print(f"\n3. 비디오 정보 조회 테스트: {test_url}")
        try:
            video_info = await service.get_video_info(test_url)
            print(f"   제목: {video_info.get('title', 'Unknown')}")
            print(f"   길이: {video_info.get('duration', 0)}초")
            print(f"   업로더: {video_info.get('uploader', 'Unknown')}")
            print(f"   예상 STT 시간: {video_info.get('estimated_stt_time', 0):.1f}초")
            print("✅ 비디오 정보 조회 성공")
        except Exception as e:
            print(f"❌ 비디오 정보 조회 실패: {e}")
            return
        
        # 4. 실제 STT 테스트 (짧은 영상으로)
        print(f"\n4. STT 추출 테스트")
        try:
            result = await service.extract_transcript(test_url)
            
            print("✅ STT 추출 성공!")
            print(f"   감지 언어: {result.language}")
            print(f"   텍스트 길이: {len(result.transcript)}자")
            print(f"   처리 시간: {result.processing_stats['total_time_seconds']:.2f}초")
            print(f"   효율성 점수: {result.processing_stats['efficiency_score']}")
            print(f"   텍스트 미리보기: {result.transcript[:100]}...")
            
            return True
            
        except YouTubeSTTServiceError as e:
            print(f"❌ STT 추출 실패: {e}")
            return False
        
    except Exception as e:
        print(f"❌ 테스트 중 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 리소스 정리
        try:
            if 'service' in locals():
                await service.cleanup_resources()
                print("\n🧹 리소스 정리 완료")
        except:
            pass


async def main():
    """메인 실행 함수"""
    success = await test_new_audio_system()
    
    if success:
        print("\n🎉 새로운 YouTube STT 시스템이 성공적으로 작동합니다!")
        print("이제 기존 시스템을 새 시스템으로 교체할 준비가 되었습니다.")
    else:
        print("\n⚠️  테스트에서 문제가 발견되었습니다. 구현을 검토해주세요.")


if __name__ == "__main__":
    asyncio.run(main())