Feature: AI Provider Interface
  AI 제공자들은 공통 인터페이스를 통해 통일된 방식으로 작동해야 함

  Background:
    Given AI 라우터가 초기화되어 있음
    And 사용자 ID 1001이 있음
    And 보드 ID가 생성되어 있음

  Scenario: OpenAI 제공자를 통한 채팅 완성
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    When 사용자가 "안녕하세요, 테스트 메시지입니다" 메시지로 채팅 완성을 요청함
    Then 성공적인 AI 응답을 받아야 함
    And 응답에는 컨텐츠가 포함되어야 함
    And 토큰 사용량이 기록되어야 함
    And WTU가 계산되어야 함

  Scenario: 웹페이지 태그 생성
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    And 웹페이지 컨텐츠 "Python 프로그래밍에 대한 기사입니다"가 있음
    When 사용자가 5개의 태그 생성을 요청함
    Then 성공적인 태그 목록을 받아야 함
    And 태그 개수는 5개여야 함
    And 각 태그는 유효한 문자열이어야 함

  Scenario: 웹페이지 카테고리 추천
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    And 웹페이지 컨텐츠 "FastAPI를 이용한 REST API 개발 가이드"가 있음
    When 사용자가 카테고리 추천을 요청함
    Then 성공적인 카테고리 추천을 받아야 함
    And 카테고리는 유효한 문자열이어야 함

  Scenario: 잘못된 모델명으로 요청 시 오류 처리
    Given 존재하지 않는 "invalid-model" 모델이 지정됨
    When 사용자가 채팅 완성을 요청함
    Then 모델을 찾을 수 없다는 오류가 발생해야 함

  Scenario: 모델 미지정 시 기본 모델 사용
    Given 모델이 지정되지 않음
    When 사용자가 채팅 완성을 요청함
    Then 기본 모델이 자동으로 선택되어야 함
    And 성공적인 AI 응답을 받아야 함

  Scenario Outline: 다양한 모델에서의 일관된 응답 형식
    Given "<model>" 모델이 사용 가능함
    When 사용자가 "테스트 질문입니다" 메시지로 채팅 완성을 요청함
    Then 성공적인 AI 응답을 받아야 함
    And 응답 형식이 일관되어야 함
    And 토큰 사용량이 기록되어야 함

    Examples:
      | model         |
      | gpt-3.5-turbo |
      | gpt-4o-mini   |