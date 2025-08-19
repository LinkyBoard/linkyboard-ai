Feature: Clipper Service
  클리퍼 서비스는 웹페이지 요약 및 동기화 기능을 제공해야 함

  Background:
    Given 클리퍼 서비스 API가 초기화되어 있음
    And 사용자 ID 999가 있음

  Scenario: 웹페이지 요약 성공
    Given AI 서비스가 정상 작동함
    And HTML 파일 "test.html"이 준비되어 있음
    When 사용자가 "http://example.com" URL로 요약을 요청함
    Then HTTP 200 응답을 받아야 함
    And 응답에 요약 내용이 포함되어야 함
    And 응답에 추천 태그가 포함되어야 함
    And 응답에 추천 카테고리가 포함되어야 함

  Scenario: 웹페이지 요약 시 필수 필드 누락
    Given HTML 파일이 준비되어 있음
    When 사용자 ID 없이 요약을 요청함
    Then HTTP 422 검증 오류를 받아야 함

  Scenario: 웹페이지 요약 시 HTML 파일 누락
    When HTML 파일 없이 요약을 요청함
    Then HTTP 422 검증 오류를 받아야 함

  Scenario: 웹페이지 요약 시 AI 서비스 오류
    Given AI 서비스가 오류를 발생시킴
    And HTML 파일이 준비되어 있음
    When 사용자가 요약을 요청함
    Then HTTP 500 서버 오류를 받아야 함

  Scenario: 새로운 아이템 동기화
    Given 사용자가 데이터베이스에 존재함
    And HTML 파일이 준비되어 있음
    When 사용자가 새로운 아이템 ID 4001로 동기화를 요청함
    Then HTTP 200 응답을 받아야 함
    And 응답에 성공 메시지가 포함되어야 함
    And 데이터베이스에 새로운 아이템이 생성되어야 함

  Scenario: 기존 아이템 업데이트
    Given 기존 아이템이 데이터베이스에 존재함
    And HTML 파일이 준비되어 있음
    When 사용자가 기존 아이템 ID로 동기화를 요청함
    Then HTTP 200 응답을 받아야 함
    And 응답에 성공 메시지가 포함되어야 함

  Scenario: 동기화 시 필수 필드 누락
    When 아이템 ID 없이 동기화를 요청함
    Then HTTP 422 검증 오류를 받아야 함

  Scenario: 동기화 시 HTML 파일 누락
    When HTML 파일 없이 동기화를 요청함
    Then HTTP 422 검증 오류를 받아야 함

  Scenario: 특수 문자가 포함된 제목으로 동기화
    Given 사용자가 데이터베이스에 존재함
    And HTML 파일이 준비되어 있음
    When 사용자가 특수 문자가 포함된 제목으로 동기화를 요청함
    Then HTTP 200 응답을 받아야 함
    And 특수 문자가 올바르게 처리되어야 함

  Scenario: 대용량 HTML 컨텐츠 처리
    Given 사용자가 데이터베이스에 존재함
    And 대용량 HTML 파일이 준비되어 있음
    When 사용자가 대용량 컨텐츠로 동기화를 요청함
    Then HTTP 200 응답을 받아야 함
    And 대용량 컨텐츠가 성공적으로 처리되어야 함

  Scenario: 태그 개수를 지정한 요약 요청
    Given AI 서비스가 정상 작동함
    And HTML 파일이 준비되어 있음
    When 사용자가 3개의 태그를 요청함
    Then HTTP 200 응답을 받아야 함
    And 정확히 3개의 태그가 반환되어야 함

  Scenario: 기본 태그 개수로 요약 요청
    Given AI 서비스가 정상 작동함
    And HTML 파일이 준비되어 있음
    When 사용자가 태그 개수를 지정하지 않고 요약을 요청함
    Then HTTP 200 응답을 받아야 함
    And 기본 개수의 태그가 반환되어야 함