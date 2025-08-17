#!/usr/bin/env python3
"""
중복 탐지 시스템 테스트
"""
import asyncio
from app.dedup_detection import DuplicateDetector, SimHashCalculator, BM25Calculator

async def test_duplicate_detection():
    print("=== 중복 탐지 시스템 테스트 ===")
    
    # 1. SimHash 계산 테스트
    print("\n1. SimHash 계산 테스트")
    simhash_calc = SimHashCalculator()
    
    text1 = "Python 프로그래밍 튜토리얼: 기초부터 고급까지"
    text2 = "Python 프로그래밍 기초 튜토리얼 가이드"
    text3 = "JavaScript 개발자를 위한 완전한 가이드"
    
    hash1 = simhash_calc.calculate_simhash(text1)
    hash2 = simhash_calc.calculate_simhash(text2)
    hash3 = simhash_calc.calculate_simhash(text3)
    
    distance_12 = simhash_calc.calculate_distance(hash1, hash2)
    distance_13 = simhash_calc.calculate_distance(hash1, hash3)
    
    print(f"텍스트 1: {text1}")
    print(f"텍스트 2: {text2}")
    print(f"텍스트 3: {text3}")
    print(f"SimHash 1: {hash1}")
    print(f"SimHash 2: {hash2}")
    print(f"SimHash 3: {hash3}")
    print(f"거리 1-2: {distance_12} (유사함)")
    print(f"거리 1-3: {distance_13} (다름)")
    
    # 2. BM25 계산 테스트
    print("\n2. BM25 계산 테스트")
    bm25_calc = BM25Calculator()
    
    documents = [
        (1, "Python 프로그래밍 튜토리얼 기초"),
        (2, "JavaScript 웹 개발 가이드"),
        (3, "Python 고급 프로그래밍 기법"),
        (4, "React 프론트엔드 개발"),
    ]
    
    bm25_calc.build_index(documents)
    
    query = "Python 프로그래밍"
    query_tokens = bm25_calc._tokenize(query)
    
    for doc_id, content in documents:
        score = bm25_calc.calculate_score(query_tokens, doc_id, content)
        print(f"문서 {doc_id}: '{content}' - BM25 스코어: {score:.3f}")
    
    # 3. 중복 탐지기 통합 테스트
    print("\n3. 중복 탐지기 통합 테스트")
    detector = DuplicateDetector()
    
    # 가상의 기존 콘텐츠 시뮬레이션
    from app.dedup_detection import ContentFingerprint
    import datetime
    
    existing_contents = [
        ("Python 완전 정복 가이드", "Python 프로그래밍의 모든 것을 다루는 완전한 가이드입니다", "https://example.com/python-guide"),
        ("JavaScript ES6 신기능", "ES6의 새로운 기능들을 상세히 설명합니다", "https://example.com/js-es6"),
        ("React 컴포넌트 설계", "효율적인 React 컴포넌트 설계 방법론", "https://example.com/react-components"),
    ]
    
    # 지문 생성
    fingerprints = []
    documents = []
    
    for i, (title, summary, url) in enumerate(existing_contents):
        combined_text = f"{title} {summary}"
        keywords = detector._extract_keywords(combined_text)
        simhash = detector.simhash_calc.calculate_simhash(combined_text, keywords)
        
        fingerprint = ContentFingerprint(
            item_id=i+1,
            simhash=simhash,
            keywords=keywords,
            title_normalized=detector._normalize_text(title),
            url_normalized=detector._normalize_url(url),
            content_length=len(combined_text)
        )
        fingerprints.append(fingerprint)
        documents.append((i+1, combined_text))
    
    detector.content_fingerprints = fingerprints
    detector.bm25_calc.build_index(documents)
    
    # 새 콘텐츠와 중복 검사
    new_title = "Python 프로그래밍 완전 가이드"
    new_summary = "Python 언어의 기초부터 고급 기법까지 모든 것을 다룹니다"
    new_url = "https://newsite.com/python-tutorial"
    
    candidates = await detector.find_duplicates(
        title=new_title,
        summary=new_summary,
        url=new_url,
        max_candidates=3
    )
    
    print(f"\n새 콘텐츠: '{new_title}'")
    print(f"요약: '{new_summary}'")
    print(f"URL: '{new_url}'")
    print(f"\n중복 후보 {len(candidates)}개 발견:")
    
    for i, candidate in enumerate(candidates):
        print(f"  {i+1}. Item ID: {candidate.item_id}")
        print(f"     제목: {candidate.title}")
        print(f"     유사도: {candidate.similarity_score:.3f}")
        print(f"     매치 타입: {candidate.match_type}")
        print(f"     SimHash 거리: {candidate.simhash_distance}")
        print(f"     BM25 스코어: {candidate.bm25_score:.3f}")
        print()
    
    print("중복 탐지 시스템 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_duplicate_detection())
