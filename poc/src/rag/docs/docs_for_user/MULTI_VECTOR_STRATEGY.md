# 멀티 벡터 리트리버 전략 (OCR RAG 서적, Markdown 기반)

## 1) 배경과 목적
- 대상 데이터: OCR된 RAG 학습 서적(설명 텍스트 + 코드 + 이미지), 이를 Markdown으로 변환한 파일.
- 기존 방식: 단일 벡터 임베딩 → 서로 다른 표현(자연어 설명, 코드, 이미지 캡션)을 하나의 표현 공간으로 축소.
- 목표: 관점(view)별 임베딩을 병렬로 보유하고 검색 시 통합하여, 질의 의도(코드/자연어/이미지)에 강건한 검색 품질을 확보.

## 2) 멀티 벡터 리트리버 적합성 판단
- 적합: 코드/설명/이미지가 혼합된 교재 특성상, 단일 벡터는 특정 질의 유형에서 손실이 큼.
- 기대 효과:
  - 코드 중심 질의(함수/시그니처/에러)에서 코드 뷰 매칭 강화.
  - 개념·절차형 질의에서 설명 텍스트/요약 뷰 매칭 강화.
  - 도해·스크린샷 관련 질의에서 이미지 캡션 뷰 매칭 확보.
  - 결과를 “유닛(부모 문맥)” 단위로 복원하여 RAG 컨텍스트 품질 향상.

## 3) 설계 원칙
- Parent-Child(부모-자식) 구조: 유닛(unit)을 부모로, 뷰(view)별 청크를 자식으로 저장.
- 뷰 분리: `text`, `code`, `summary`, `image`(캡션) 등.
- 느슨한 결합: 인덱스/저장 구조는 단순 메타(JSONB)로 관리하여 확장 용이.
- 멱등성: 동일 문서 재처리 시 중복 최소화(해시/ID 설계) 및 인덱스 생성은 멱등.

## 4) 데이터 모델(메타)
- 공통 메타: `source`, `order`, `parent_id`(=unit_id), `view ∈ {text, code, summary, image}`
- 코드 메타: `lang ∈ {python, javascript, unknown}`
- 선택 메타: `unit_role`(pre_text/python/javascript/bridge_text/post_text), `section_title`, `image_url`

예시(JSON):
```json
{
  "source": "ch03.md",
  "order": 42,
  "parent_id": "b5f1…",
  "view": "code",
  "unit_role": "python",
  "lang": "python"
}
```

## 5) 파이프라인 변경(생성 측)
1. 세그먼트/유닛화(기존): `parse_ocr_file` → `unitize_txt_py_js_streaming` 유지.
2. 뷰 구성 추가:
   - `text` 뷰: `pre_text/post_text/bridge_text` 및 일반 텍스트 세그먼트를 수집.
   - `code` 뷰: `python/javascript` 세그먼트만 연결 또는 분리하여 수집.
   - `summary` 뷰: 제목/첫 단락/리스트를 규칙 기반으로 요약(LLM 요약은 선택 적용).
   - `image` 뷰: `![]()` 파싱하여 alt/caption/주변 문장 추출.
3. 청크화:
   - 텍스트: `RecursiveCharacterTextSplitter`(`split_text`)로 1200/150 기준 유지.
   - 코드: `split_code_safely`(~1800자, 5줄 오버랩) 유지.
   - 이미지 캡션: 짧은 캡션 단위(길이 상한)로 저장.
4. 문서화: 각 뷰별 생성된 청크를 `Document`로 만들고, 메타에 `parent_id`/`view` 포함.
5. 저장/업서트: 기존 `PGVector.add_documents` 경로 유지(배치 업서트), 중복 방지를 위해 `id` 또는 `(parent_id, view, order, hash)` 조합을 고려.

## 6) 인덱싱 전략(DB)
- 확장: `CREATE EXTENSION IF NOT EXISTS vector` 유지.
- 벡터 인덱스: HNSW(cosine) on `embedding` 유지.
- 메타 인덱스:
  - JSONB GIN on `cmetadata` 유지.
  - BTREE on `(cmetadata->>'parent_id')`, `(cmetadata->>'view')` 추가.
- 컬렉션: 기존 `collection_name` 기반으로 구분(테이블 공용).

## 7) 검색 파이프라인(쿼리 측)
1. 쿼리 전처리/분류(경량):
   - 코드성 신호(CODE_HINT 유사, 스택트레이스 토큰, 백틱 코드 등) → `code` 뷰 가중치↑
   - 일반 질의/설명형 → `text/summary` 가중치↑
   - 이미지 키워드(“그림/도/스크린샷”) → `image` 가중치↑
2. 다중 뷰 검색:
   - 동일 쿼리 임베딩으로 뷰별 필터(`view in {...}`)를 적용해 각각 top-k′ 검색.
   - 스코어 정규화(예: Min-Max, Z-score) 후 가중 합 또는 RRF(Reciprocal Rank Fusion)로 통합.
3. 부모 단위 그룹핑:
   - child 결과를 `parent_id`로 묶고, 통합 점수로 상위 n 부모 선택.
4. 문맥 조립(RAG 입력):
   - 선택된 부모에서 `pre_text` 일부 + 관련 `code` 블록 + 필요 시 `bridge_text`로 컨텍스트 구성.
5. 재랭킹(옵션):
   - MMR로 중복 억제, 쿼리 타입과 `lang` 매칭 시 가중치 보정.

## 8) 모델 선택/운영
- 텍스트/요약/이미지-캡션: `VOYAGE_MODEL` 유지(기본 `voyage-3`).
- 코드: 코드 특화 모델이 있으면 전용 뷰에 사용(없으면 동일 모델 + 뷰 가중치로 보완).
- 멀티모달 미사용 시: 이미지는 텍스트 캡션으로 통일하여 텍스트 임베딩.

## 9) Markdown 이미지 처리
- 파싱: `![](url)`에서 alt 텍스트를 1차 캡션으로 사용.
- 캡션 추출 규칙:
  - 이미지 직후 줄에서 “그림/도/Fig.” 패턴 매칭 시 채택.
  - 주변 문단 1개를 보조 캡션으로 결합(총 길이 상한 적용).
- 메타: `image_url`, `caption_source`(alt/inline/neighbor) 저장.

## 10) 단계별 이행 계획
- 단계 1(핵심 뷰): `text`/`code` 뷰 도입, 메타(`parent_id`, `view`) 추가, 인덱스 보강, 간단한 RRF 기반 통합.
- 단계 2(품질 개선): `summary` 뷰(규칙 요약), 이미지 캡션 파서 및 `image` 뷰 추가, 쿼리 가중 로직 도입.
- 단계 3(고도화): 코드 특화 임베딩, 멀티쿼리/재랭킹, LLM 요약·확장 질의.

## 11) 리스크와 완화
- 코드 과검출/미검출: MD 펜스 언어 태그 우선, 힌트는 보조로 완화.
- 캡션 노이즈: 길이 상한 및 패턴 필터로 정제.
- 스토리지 팽창: 뷰별 청크 수 증가 → 배치 크기/인덱스 병행 최적화, 콜렉션·스키마 전략 검토.
- 성능: 뷰별 검색 병렬화, k′ 조절, 캐시, 인덱스 유지보수.

## 12) 품질 지표(KPI)
- Recall@k, nDCG@k(코드/텍스트/이미지 질의 별도),
- MRR (질의 유형별),
- RAG 최종 응답의 정확도/채점(휴먼 혹은 자동 메트릭),
- 추론 실패율(“미답변/환각” 비율).

## 13) 테스트 계획
- 단위 테스트: `normalize`, `is_code_block`, `guess_code_lang`, `split_code_safely`, 이미지 캡션 파서.
- 골든 테스트: 합성 MD 샘플에 대한 유닛화/뷰 생성/메타 스냅샷.
- 통합 테스트: 소형 코퍼스 인덱싱 → 뷰별 검색 → 그룹핑/통합 점수 검증.

## 14) 마이그레이션
- 기존 단일 벡터 데이터와 공존: 동일 테이블에 `view` 메타가 없는 레코드는 `view='legacy'`로 간주.
- 점진적 재색인: 중요 문서부터 멀티뷰로 재생성.

## 15) 운영 고려사항
- 인덱스 관리: 분석·재색인 기간 중 CONCURRENTLY 옵션 고려(환경 허용 시).
- 모니터링: 업서트 속도, 인덱스 크기, 쿼리 지연, 실패 로그.
- 설정: `COLLECTION_NAME`, `EMBEDDING_DIM`, 뷰 사용 여부(Feature Flag)로 운영 제어.

---

## 구현 체크리스트(요약)
- [ ] `build_document_from_unitized` 확장: 뷰 생성(`text/code/summary/image`), `parent_id`/`view` 메타 부여
- [ ] 이미지 캡션 파서 추가(MD 전용)
- [ ] 인덱스: `(parent_id)`, `(view)` BTREE 추가
- [ ] 검색: 뷰별 top-k′ → RRF/가중 합 → parent 그룹핑 → 컨텍스트 조립
- [ ] 쿼리 전처리: 코드/자연어/이미지 신호 기반 가중치
- [ ] 메트릭/테스트: 샘플 코퍼스 기준 KPI 측정

