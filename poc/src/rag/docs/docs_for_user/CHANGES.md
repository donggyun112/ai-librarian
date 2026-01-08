# 변경 사항 요약

## 개요
이 문서는 embedding 파이프라인과 검색 전략 개선을 위해 적용된 변경 사항을 요약합니다.

## 버그 수정
- 텍스트 kind 정정: `parse_ocr_file`에서 텍스트 세그먼트를 `kind="text"`로 통일(`"txt"` 사용으로 인한 다운스트림 불일치 해결).
- Splitter 공개 API 사용: `TEXT_SPLITTER._split_text` → `TEXT_SPLITTER.split_text`로 교체(버전 호환성 개선).
- 인덱스명 안전화: `sanitize_identifier` 도입으로 `COLLECTION_NAME` 기반 인덱스명의 식별자 제약 문제(공백/대시 등) 예방.

## 기능 추가(멀티 벡터 1단계)
- 메타 확장: 문서 메타에 `parent_id`(= `unit_id`)와 `view` 추가
  - 텍스트 세그먼트 → `view: "text"`
  - 코드 세그먼트 → `view: "code"`, `lang` 유지
- DB 인덱스 보강:
  - BTREE 인덱스 추가: `(cmetadata->>'parent_id')`, `(cmetadata->>'view')`
  - 기존 HNSW(cosine), JSONB GIN, unit_id/unit_role/lang 인덱스 유지
- 검색 데모 스크립트 추가: `retriever_multi_view_demo.py`
  - 뷰별 검색(코드/텍스트) → RRF(Rank Fusion)로 결과 통합 → `parent_id` 기준 그룹핑 반환

## 문서화
- 프로젝트 분석: `PROJECT_ANALYSIS.md` → 프로젝트 개요, 파이프라인, 인덱스, 환경 변수, 수정 사항 및 개선 제안
- 멀티 벡터 전략: `MULTI_VECTOR_STRATEGY.md` → 배경/목적, 설계, 데이터 모델, 검색/인덱싱, 단계별 이행 계획, 리스크, KPI, 테스트

## 파일 경로 변경
- 문서 파일을 `docs/` 디렉터리로 이동했습니다.
  - `docs/PROJECT_ANALYSIS.md`
  - `docs/MULTI_VECTOR_STRATEGY.md`
  - `docs/CHANGES.md`(본 문서)

## 다음 단계 제안
- 쿼리 타입별 가중치(코드/자연어) 적용
- Markdown 이미지 캡션 파서 추가 및 `image` 뷰 확장
- `summary` 뷰(규칙 기반/LLM 보강) 도입
- 간단한 평가 스크립트로 KPI 측정(Recall@k, MRR 등)

