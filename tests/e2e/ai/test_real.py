# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """AI 도메인 E2E 테스트 (실제 AI API 사용)
# 
# 주의: 이 테스트들은 실제 AI API를 호출하여 과금이 발생합니다.
# 실행 방법: ENABLE_REAL_AI_TESTS=true make test-real-ai
# """
# 
# import os
# 
# import pytest
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.real_ai
# async def test_real_webpage_summarization(
#     skip_if_no_real_ai, client, api_key_header
# ):
#     """실제 AI로 웹페이지 요약 생성 E2E 테스트"""
#     from io import BytesIO
# 
#     # 실제 HTML 콘텐츠
#     html_content = """
#     <html>
#         <head><title>Python Programming</title></head>
#         <body>
#             <h1>Introduction to Python</h1>
#             <p>
#                 Python is a high-level programming language known for
#                 its simplicity and readability.
#             </p>
#             <p>
#                 It is widely used in web development, data science,
#                 machine learning, and automation.
#             </p>
#             <p>
#                 Python's syntax allows programmers to express concepts
#                 in fewer lines of code than languages like Java or C++.
#             </p>
#             <h2>Key Features</h2>
#             <ul>
#                 <li>Easy to learn and use</li>
#                 <li>Extensive standard library</li>
#                 <li>Cross-platform compatibility</li>
#                 <li>Large and active community</li>
#             </ul>
#         </body>
#     </html>
#     """
# 
#     html_file = BytesIO(html_content.encode("utf-8"))
# 
#     # API 호출
#     response = await client.post(
#         "/api/v1/ai/summarize/webpage",
#         data={
#             "url": "https://example.com/python-intro",
#             "user_id": 1,
#             "tag_count": 5,
#             "refresh": False,
#         },
#         files={"html_file": ("test.html", html_file, "text/html")},
#         headers=api_key_header,
#     )
# 
#     # 응답 검증
#     assert (
#         response.status_code == 200
#     ), f"Unexpected status: {response.status_code}, body: {response.text}"
# 
#     data = response.json()
#     assert data["success"] is True
# 
#     # 실제 LLM이 생성한 데이터 검증
#     assert len(data["data"]["summary"]) > 50, "요약이 너무 짧습니다"
#     assert len(data["data"]["tags"]) > 0, "태그가 생성되지 않았습니다"
#     assert data["data"]["category"], "카테고리가 생성되지 않았습니다"
#     assert data["data"]["cached"] is False, "첫 요청은 캐시되지 않아야 합니다"
# 
#     # Python 관련 키워드가 포함되어 있는지 확인
#     summary_lower = data["data"]["summary"].lower()
#     assert (
#         "python" in summary_lower
#         or "프로그래밍" in summary_lower
#         or "programming" in summary_lower
#     ), "요약에 관련 키워드가 없습니다"
# 
#     print(f"\n[E2E Test] 생성된 요약: {data['data']['summary'][:100]}...")
#     print(f"[E2E Test] 생성된 태그: {data['data']['tags']}")
#     print(f"[E2E Test] 생성된 카테고리: {data['data']['category']}")
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.real_ai
# async def test_real_embedding_generation(skip_if_no_real_ai, db_session):
#     """실제 임베딩 생성 E2E 테스트"""
#     from app.core.llm.fallback import create_embedding
# 
#     # 실제 텍스트 임베딩 생성
#     text = (
#         "Python is a powerful programming language for "
#         "data science and machine learning."
#     )
# 
#     embedding = await create_embedding(text)
# 
#     # 임베딩 벡터 검증
#     assert isinstance(embedding, list), "임베딩은 리스트여야 합니다"
#     assert len(embedding) == 3072, f"임베딩 차원이 3072이어야 하는데 {len(embedding)}입니다"
#     assert all(
#         isinstance(v, float) for v in embedding
#     ), "임베딩 값은 모두 float이어야 합니다"
# 
#     # 벡터 노름 확인 (정규화되어 있어야 함)
#     import math
# 
#     norm = math.sqrt(sum(v * v for v in embedding))
#     assert 0.9 < norm < 1.1, f"임베딩 벡터가 정규화되어 있지 않습니다: norm={norm}"
# 
#     print(f"\n[E2E Test] 임베딩 생성 완료: 차원={len(embedding)}, norm={norm:.4f}")
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.real_ai
# async def test_real_vector_search(
#     skip_if_no_real_ai, client, api_key_header, db_session
# ):
#     """실제 벡터 검색 E2E 테스트"""
#     from app.core.utils.datetime import now_utc
#     from app.domains.ai.embedding.service import EmbeddingService
#     from app.domains.contents.models import Content
# 
#     # 테스트 콘텐츠 생성
#     content1 = Content(
#         id=10001,
#         user_id=999,
#         content_type="webpage",
#         source_url="https://example.com/python-ml",
#         title="Python for Machine Learning",
#         summary=(
#             "A comprehensive guide to using Python for "
#             "machine learning projects"
#         ),
#         embedding_status="pending",
#         created_at=now_utc(),
#     )
#     content2 = Content(
#         id=10002,
#         user_id=999,
#         content_type="webpage",
#         source_url="https://example.com/java-oop",
#         title="Java Object-Oriented Programming",
#         summary="Learn object-oriented programming concepts with Java",
#         embedding_status="pending",
#         created_at=now_utc(),
#     )
# 
#     db_session.add_all([content1, content2])
#     await db_session.flush()
# 
#     # 실제 임베딩 생성
#     embedding_service = EmbeddingService(db_session)
# 
#     await embedding_service.create_embeddings_for_content(
#         content_id=content1.id,
#         text=f"{content1.title} {content1.summary}",
#         strategy_id=None,
#     )
#     await embedding_service.create_embeddings_for_content(
#         content_id=content2.id,
#         text=f"{content2.title} {content2.summary}",
#         strategy_id=None,
#     )
# 
#     content1.embedding_status = "completed"
#     content2.embedding_status = "completed"
#     await db_session.commit()
# 
#     # 벡터 검색 실행
#     response = await client.post(
#         "/api/v1/ai/search",
#         json={
#             "query": "Python machine learning tutorial",
#             "user_id": 999,
#             "search_mode": "vector",
#             "page": 1,
#             "size": 10,
#             "threshold": 0.3,
#         },
#         headers=api_key_header,
#     )
# 
#     # 응답 검증
#     assert (
#         response.status_code == 200
#     ), f"Unexpected status: {response.status_code}"
# 
#     data = response.json()
#     assert data["success"] is True
#     assert len(data["data"]) > 0, "검색 결과가 없습니다"
# 
#     # Python ML 콘텐츠가 더 높은 순위에 있어야 함
#     top_result = data["data"][0]
#     assert (
#         "Python" in top_result["title"]
#         or "python" in top_result.get("summary", "").lower()
#     )
# 
#     print(f"\n[E2E Test] 검색 결과 개수: {len(data['data'])}")
#     print(f"[E2E Test] 최상위 결과: {top_result['title']}")
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.real_ai
# async def test_real_youtube_summarization(
#     skip_if_no_real_ai, client, api_key_header
# ):
#     """실제 YouTube 요약 E2E 테스트
# 
#     주의: 이 테스트는 실제 YouTube 영상의 자막이 필요합니다.
#     자막이 없는 영상의 경우 실패할 수 있습니다.
#     """
#     # 유명한 TED Talk 영상 (자막이 있는 영상)
#     # 실제 테스트 시에는 자막이 있는 공개 영상 URL을 사용하세요
#     youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # 예시 URL
# 
#     response = await client.post(
#         "/api/v1/ai/summarize/youtube",
#         json={
#             "url": youtube_url,
#             "user_id": 1,
#             "tag_count": 5,
#             "refresh": False,
#         },
#         headers=api_key_header,
#     )
# 
#     # 자막이 없는 경우 404 또는 특정 에러 코드를 반환할 수 있음
#     # 이 테스트는 자막이 있는 영상에서만 통과합니다
#     if response.status_code == 404:
#         pytest.skip("YouTube 자막을 사용할 수 없습니다")
# 
#     # 정상 응답 검증
#     assert (
#         response.status_code == 200
#     ), f"Unexpected status: {response.status_code}"
# 
#     data = response.json()
#     assert data["success"] is True
#     assert len(data["data"]["summary"]) > 30, "요약이 너무 짧습니다"
#     assert len(data["data"]["tags"]) > 0, "태그가 생성되지 않았습니다"
# 
#     print(f"\n[E2E Test] YouTube 요약 생성: {data['data']['summary'][:100]}...")
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.real_ai
# async def test_real_personalization(skip_if_no_real_ai, db_session):
#     """실제 개인화 추천 E2E 테스트"""
#     from app.core.utils.datetime import now_utc
#     from app.domains.ai.models import Tag, UserTagUsage
#     from app.domains.ai.personalization.service import PersonalizationService
# 
#     user_id = 888
# 
#     # 사용자 태그 사용 이력 생성
#     tag1 = Tag(
#         id=501,
#         tag_name="Python",
#         embedding_vector=None,  # 실제 임베딩은 서비스에서 생성
#         created_at=now_utc(),
#     )
#     tag2 = Tag(
#         id=502,
#         tag_name="Machine Learning",
#         embedding_vector=None,
#         created_at=now_utc(),
#     )
# 
#     db_session.add_all([tag1, tag2])
#     await db_session.flush()
# 
#     # 태그 사용 통계
#     usage1 = UserTagUsage(
#         user_id=user_id,
#         tag_id=tag1.id,
#         use_count=15,
#         last_used_at=now_utc(),
#     )
#     usage2 = UserTagUsage(
#         user_id=user_id,
#         tag_id=tag2.id,
#         use_count=10,
#         last_used_at=now_utc(),
#     )
# 
#     db_session.add_all([usage1, usage2])
#     await db_session.commit()
# 
#     # 개인화 추천
#     service = PersonalizationService(db_session)
# 
#     candidate_tags = [
#         "Deep Learning",
#         "Neural Networks",
#         "Data Science",
#         "JavaScript",
#         "React",
#     ]
# 
#     personalized = await service.personalize_tags(
#         candidate_tags=candidate_tags, user_id=user_id, count=3
#     )
# 
#     # 검증
#     assert len(personalized) == 3, f"3개의 태그를 기대했으나 {len(personalized)}개 반환"
#     assert all(
#         tag in candidate_tags for tag in personalized
#     ), "잘못된 태그가 반환되었습니다"
# 
#     # Python/ML 관련 태그가 더 높은 우선순위를 가져야 함
#     # (Deep Learning, Neural Networks, Data Science가 JavaScript, React보다 우선)
#     ml_related = ["Deep Learning", "Neural Networks", "Data Science"]
#     personalized_ml_count = sum(1 for tag in personalized if tag in ml_related)
# 
#     assert (
#         personalized_ml_count >= 2
#     ), f"ML 관련 태그가 충분히 추천되지 않았습니다: {personalized}"
# 
#     print(f"\n[E2E Test] 개인화 추천 결과: {personalized}")
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.real_ai
# async def test_real_cache_behavior(skip_if_no_real_ai, client, api_key_header):
#     """실제 캐시 동작 E2E 테스트"""
#     from io import BytesIO
# 
#     html_content = (
#         "<html><body><h1>Cache Test</h1>"
#         "<p>This is a cache test.</p></body></html>"
#     )
#     url = "https://example.com/cache-test-e2e"
# 
#     # 첫 번째 요청 (캐시 미스)
#     html_file1 = BytesIO(html_content.encode("utf-8"))
#     response1 = await client.post(
#         "/api/v1/ai/summarize/webpage",
#         data={"url": url, "user_id": 1, "tag_count": 3, "refresh": False},
#         files={"html_file": ("test.html", html_file1, "text/html")},
#         headers=api_key_header,
#     )
# 
#     assert response1.status_code == 200
#     data1 = response1.json()
#     assert data1["data"]["cached"] is False
# 
#     # 두 번째 요청 (캐시 히트)
#     html_file2 = BytesIO(html_content.encode("utf-8"))
#     response2 = await client.post(
#         "/api/v1/ai/summarize/webpage",
#         data={"url": url, "user_id": 1, "tag_count": 3, "refresh": False},
#         files={"html_file": ("test.html", html_file2, "text/html")},
#         headers=api_key_header,
#     )
# 
#     assert response2.status_code == 200
#     data2 = response2.json()
#     assert data2["data"]["cached"] is True
# 
#     # 캐시된 결과는 동일해야 함
#     assert data1["data"]["summary"] == data2["data"]["summary"]
#     assert data1["data"]["tags"] == data2["data"]["tags"]
# 
#     print("\n[E2E Test] 캐시 동작 확인: 첫 요청=미스, 두 번째=히트")
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.real_ai
# async def test_environment_check(skip_if_no_real_ai):
#     """실제 AI 테스트 환경 확인"""
#     # 필수 환경 변수 확인
#     assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다"
#     assert (
#         os.getenv("ENABLE_REAL_AI_TESTS") == "true"
#     ), "ENABLE_REAL_AI_TESTS=true로 설정되어야 합니다"
# 
#     print("\n[E2E Test] 환경 변수 확인 완료")
#     print(f"[E2E Test] OPENAI_API_KEY: {'*' * 20}...")
