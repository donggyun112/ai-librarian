# Vision 호출 결정 정책 (OCR/LLM)

## 목적
- PyMuPDF 텍스트 추출과 Vision OCR 호출 판단을 일관적으로 수행한다.
- 비용/지연을 최소화하면서 스캔/혼합 PDF의 텍스트 누락을 줄인다.

## 입력 신호 정의
- text_blocks: `page.get_text("dict")`에서 type == 0인 블록
- image_blocks: `page.get_text("dict")`에서 type == 1인 블록
- total_chars: 텍스트 블록의 총 문자 수
- alpha_ratio: 공백/기호 제외 문자 비율(한글/영문/숫자)
- code_patterns: `_looks_like_code()` 매칭 개수

## 결정 트리 (순서 중요)
1) 텍스트 추출 시도
- 항상 `page.get_text("dict")`를 호출한다.

2) 텍스트 블록 존재 여부
- text_blocks > 0 이면 Step 3
- text_blocks == 0 이면 Step 5

3) 텍스트 충분성 검사
- 조건: total_chars >= 100 AND alpha_ratio >= 0.3
- TRUE: Vision 호출 안 함 (텍스트 보존)
- FALSE: Step 4로 이동

4) 코드 패턴 검사
- 조건: code_patterns >= 2
- TRUE: Vision 호출 안 함 (코드 중심 텍스트 보존)
- FALSE: Vision 호출 (sparse 텍스트 보완)

5) 이미지 중심 문서 처리
- 조건: text_blocks == 0 AND image_blocks > 0
- TRUE: Vision 호출 (이미지 기반 OCR)
- FALSE: OCR 폴백 정책 확인

## 보존/병합 규칙
- 충분한 텍스트가 존재하면 Vision 결과로 대체하지 않는다.
- Vision 결과가 비어 있거나 실패하면 기존 텍스트를 유지한다.
- force_ocr가 켜져 있으면 위 조건과 무관하게 Vision을 호출한다.

## 규칙 요약
Rule 1: 충분한 텍스트면 Vision 호출 안 함
- 기준: total_chars >= 100 AND alpha_ratio >= 0.3
- 보존: PyMuPDF 텍스트

Rule 2: 코드 패턴이 충분하면 Vision 호출 안 함
- 기준: code_patterns >= 2
- 보존: PyMuPDF 텍스트

Rule 3: 이미지 중심이면 Vision 호출
- 기준: text_blocks == 0 AND image_blocks > 0
- 동작: Vision OCR

Rule 4: Vision 실패 시 원본 보존
- 기준: Vision 결과 비어 있음 AND 원본 텍스트 존재
- 동작: 원본 유지

## 시나리오
Scenario A: 텍스트 중심 PDF
- total_chars 2000+, text_blocks > 0
- 결과: Vision 호출 안 함

Scenario B: 혼합 PDF (텍스트 + 이미지)
- text_blocks > 0, total_chars 충분
- 결과: Vision 호출 안 함
- 주의: 페이지 단위 sparse 체크가 필요하면 별도 옵션으로 처리

Scenario C: 스캔 PDF (이미지 중심)
- text_blocks == 0, image_blocks > 0
- 결과: Vision 호출

Scenario D: sparse 텍스트 + 코드 패턴
- total_chars 100 미만, code_patterns >= 2
- 결과: Vision 호출 안 함

## 실패 및 폴백 정책
Vision 호출 조건
- text_blocks == 0 AND image_blocks > 0
- total_chars < 100 AND alpha_ratio < 0.2 AND code_patterns < 2

Vision 미호출 조건
- total_chars >= 100
- code_patterns >= 2
- alpha_ratio >= 0.3 AND total_chars >= 50

OCR 폴백 실행 조건
- `fitz.open()` 오류
- 모든 페이지의 텍스트가 비어 있음
- text_blocks == 0 AND image_blocks == 0 (빈/손상 문서)

OCR 폴백 미실행 조건
- sparse 기준을 만족하지만 텍스트가 유의미한 경우
- alpha_ratio가 높아 텍스트 신뢰도가 충분한 경우
- 코드 패턴이 충분한 경우

## 파라미터
- total_chars_threshold: 100
- alpha_ratio_threshold: 0.3
- code_patterns_threshold: 2
- sparse_alpha_ratio_threshold: 0.2

## 기대 효과
- 텍스트 중심 PDF: LLM 비용/지연 최소화
- 혼합 PDF: 텍스트 보존, 필요 시 추가 OCR 옵션
- 스캔 PDF: OCR 커버리지 확보
- 리스크: 임계치 튜닝 필요

## TODO
- 혼합 PDF의 페이지 단위 OCR 정책 정의
- Vision 결과 품질 기준(최소 문자 수, 언어 비율) 확정
