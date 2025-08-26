#!/usr/bin/env python3
"""
통합 테스트

새로운 오디오 시스템과 기존 시스템의 통합을 테스트합니다.
"""

import asyncio
import ssl
import os
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.ai.content_extraction.youtube_url_extractor import YouTubeUrlExtractor


async def test_integration():
    """통합 테스트 실행"""
    # SSL 인증 문제 우회
    ssl._create_default_https_context = ssl._create_unverified_context
    
    print("=== YouTube URL 추출기 통합 테스트 ===\n")
    
    try:
        # 추출기 인스턴스 생성
        extractor = YouTubeUrlExtractor()
        
        # 테스트 URL
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = "dQw4w9WgXcQ"
        
        print(f"테스트 URL: {test_url}")
        print(f"비디오 ID: {video_id}")
        
        # 1. 새로운 오디오 STT로 자막 추출 테스트
        print("\n1. 새로운 오디오 STT로 자막 추출")
        try:
            transcript_info = await extractor.extract_transcript(
                video_id, 
                use_audio_stt=True
            )
            
            if transcript_info['success']:
                print("✅ 오디오 STT 자막 추출 성공!")
                print(f"   언어: {transcript_info['language']}")
                print(f"   방법: {transcript_info['extraction_method']}")
                print(f"   길이: {transcript_info['char_count']}자")
                print(f"   처리시간: {transcript_info.get('stt_metadata', {}).get('processing_time', 'N/A')}초")
                print(f"   미리보기: {transcript_info['transcript'][:100]}...")
            else:
                print("❌ 오디오 STT 자막 추출 실패")
                print(f"   오류: {transcript_info.get('error', '알 수 없는 오류')}")
                return False
                
        except Exception as e:
            print(f"❌ 자막 추출 중 오류: {e}")
            return False
        
        # 2. 전체 정보 추출 테스트
        print("\n2. 전체 정보 추출 (메타데이터 + 자막)")
        try:
            complete_info = await extractor.extract_complete_info(test_url)
            
            if complete_info['extraction_success']:
                metadata = complete_info['metadata']
                transcript = complete_info['transcript']
                
                print("✅ 전체 정보 추출 성공!")
                print(f"   제목: {metadata.get('title', 'Unknown')[:50]}...")
                print(f"   길이: {metadata.get('duration_formatted', 'Unknown')}")
                print(f"   자막 성공: {transcript.get('success', False)}")
                print(f"   자막 방법: {transcript.get('extraction_method', 'None')}")
                print(f"   자막 길이: {transcript.get('char_count', 0)}자")
                
                return True
            else:
                print("❌ 전체 정보 추출 실패")
                print(f"   오류: {complete_info.get('error', '알 수 없는 오류')}")
                return False
                
        except Exception as e:
            print(f"❌ 전체 정보 추출 중 오류: {e}")
            return False
    
    except Exception as e:
        print(f"❌ 테스트 중 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """메인 실행 함수"""
    success = await test_integration()
    
    if success:
        print("\n🎉 통합 테스트 성공!")
        print("새로운 오디오 STT 시스템이 기존 시스템과 성공적으로 통합되었습니다.")
    else:
        print("\n⚠️  통합 테스트에서 문제가 발견되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())