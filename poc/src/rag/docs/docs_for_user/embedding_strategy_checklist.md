# Multi-Vector Retriever + 단일 DB 임베딩 전략 및 체크리스트

본 문서는 다음 세 문서를 바탕으로, Multi-Vector Retriever 방식과 단일 DB(Postgres + pgvector)를 결합한 임베딩/검색 구현 전략과 체크리스트를 정리합니다.
- docs/poc_pgvector_schema.md
- docs/poc_pgvector_single_docstore.md
- docs/poc_pgvector_single_docstore_notes.md

## 1) 목표/원칙

- 표준 리트리버: LangChain `MultiVectorRetriever` 사용(개발자 친화적, 부모 단위 반환).
- 단일 스택: 부모 문서(대표 본문)와 자식 청크(임베딩)를 Postgres(+pgvector)에 저장(의존성 최소화, 운영 단순화).
- 빠른 PoC: 스키마/인덱스 최소 구성으로 바로 검증, 병목 확인 시 단계적 확장(캐시/별도 스토어).

## 2) 아키텍처 선택

- VectorStore(자식): LangChain `PGVector` 테이블(`langchain_pg_embedding`)
- DocStore(부모): Postgres 테이블 기반(K/V 바이트 스토어 어댑터) — 기본 `docstore_parent`
- 선택적 커스텀 스키마(듀얼 라이트):
  - 자식: `child_chunks(parent_id, view, lang, content, embedding vector(N))`
  - 부모: `parent_docs(parent_id, content, metadata)`

## 3) 환경 변수(예시)

- 필수: `PG_CONN`, `COLLECTION_NAME`, `VOYAGE_MODEL`, `EMBEDDING_DIM`
- 옵션: `CUSTOM_SCHEMA_WRITE=true`(커스텀 스키마 동시 기록), `PARENT_MODE=unit|page|section|page_section`
- 페이지/섹션 감지: `PAGE_REGEX`, `SECTION_REGEX`

## 4) 스키마 보장(DDL)

- pgvector 확장: `CREATE EXTENSION IF NOT EXISTS vector;`
- 기본(권장 최소): `docstore_parent(id, content, metadata, created_at, updated_at)`
- 커스텀(선택): docs/poc_pgvector_schema.md의 `child_chunks`/`parent_docs`와 인덱스(ivfflat/hnsw, BTREE, GIN)

## 5) 인제스트 설계(임베딩 파이프라인)

- 전처리/유닛화:
  - OCR 합자/개행 정리 → 문단 분리 → 코드 블록 감지/언어 추정 → Python 기준 유닛 묶기(pre_text/bridge/code)
- 부모 단위 부여:
  - `PARENT_MODE`에 따라 page/section 기반 `parent_id` 부여(없으면 unit 기반 유지)
- 청크 생성:
  - 텍스트: 재귀 분할(`chunk_size`/`overlap`), 코드: 행 기반 안전 분할(`max_chars`/line overlap)
- 임베딩 계산/저장:
  - PGVector에 `add_documents`(자식 청크)
  - DocStore(Postgres)에 `parent_id`별 대표 본문 업서트(1~2KB)
  - 선택: `CUSTOM_SCHEMA_WRITE=true`이면 `child_chunks`/`parent_docs`에도 동시 기록
- 트랜잭션(선택): 부모/자식 업서트를 하나의 트랜잭션으로 묶어 정합성 강화

## 6) 인덱스/튜닝

- PGVector 테이블: HNSW(cosine) 또는 ivfflat(cosine), JSONB GIN, BTREE(view/lang/parent_id)
- DocStore 테이블: GIN(metadata), updated_at 트리거(옵션), 필요 시 pg_trgm(content)
- 파라미터: ivfflat(lists/probes), HNSW(ef_construction/ef_search) — 데이터량에 맞춰 조정

## 7) 리트리버 구성(MultiVectorRetriever)

- VectorStore: `PGVector(connection, collection_name, embeddings, distance_strategy="COSINE", use_jsonb=True, embedding_length=N)`
- DocStore: Postgres ByteStore 어댑터(키=`parent_id`, 값=부모 본문 UTF-8 bytes)
- Retriever: `MultiVectorRetriever(vectorstore=PGVector, docstore=DocStore, id_key="parent_id", search_kwargs={"k": K, "filter": {view/lang}})`

## 8) 조회 패턴

- 텍스트만/코드만/언어 제한: `search_kwargs.filter = {"view": "text" | "code", "lang": "python"}`
- 멀티뷰: 자식(여러 뷰)을 검색 후 `parent_id`로 부모 단위 통합하여 반환(중복 제거)
- 후처리(옵션): parent 그룹 재랭킹, 중복 제거, 스니펫 병합

## 9) 검증 체크리스트

- [ ] env 로딩, 모델 차원(`EMBEDDING_DIM`) 일치 확인
- [ ] 스키마/인덱스 보장 함수 실행(벡터 확장/테이블/인덱스)
- [ ] 파일 1~2개로 소규모 인제스트 → 총 청크/부모 건수 확인
- [ ] DocStore에 부모 본문 저장 확인(길이 ~2KB)
- [ ] 뷰별 검색 동작: text/code/python 필터로 상식적 결과 확인
- [ ] parent_id 그룹핑 품질: page/section 모드 시 같은 단위로 묶이는지 확인
- [ ] 검색 응답 시간/유사도 품질 점검(k, lists/probes/hnsw 파라미터 조정)

## 10) 운영 체크리스트

- [ ] 백업/복구 전략(단일 DB 스냅샷)
- [ ] 접근 제어/암호화(TLS, 최소 권한)
- [ ] 모니터링: 인덱스 상태, 테이블 크기, 쿼리 계획/지연
- [ ] 비용/성능: 인덱스 파라미터 및 배치 크기 튜닝
- [ ] 캐시 전략(선택): 부모 본문 Redis 캐시 도입 기준/키/TTL 정의

## 11) 성능/비용 가이드

- 부모 본문 1~2KB로 유지(RAG 컨텍스트 비용/지연 절감)
- 인제스트 배치: 64~128 단위로 임베딩/DB 쓰기
- 필터 우선: 뷰/언어 메타 필터로 후보군 축소 후 유사도 정렬
- 인덱스 파라미터 튜닝: 데이터량 증가 시 lists/probes(HNSW는 ef_* 파라미터) 조정

## 12) 실패/롤백 전략

- 트랜잭션 묶기: 부모/자식 듀얼 라이트 시 같은 트랜잭션 사용
- 멱등성: 인덱스/테이블 보장, 업서트(ON CONFLICT/merge) 사용
- 재시도: 네트워크 오류/임베딩 실패 시 배치 단위 재시도

## 13) 보안 체크리스트

- 시크릿 관리: DB/모델 키 환경 변수 관리(Secret Manager/Key Vault)
- 네트워크: DB TLS, 보안 그룹/화이트리스트
- PII: 민감 데이터 마스킹/필터링, 접근 로깅

## 14) 마이그레이션/확장 경로

- PoC→운영: 병목 파악 후, 부모 DocStore를 Redis/S3로 분리 가능(코드 변경 최소화: DocStore 어댑터 교체)
- 멀티모달: 이미지 임베딩은 별도 컬렉션/스키마로 추가 후 애플리케이션 레벨 병합
- 벡터 테이블 파티셔닝/압축: 대규모화 시 고려

## 15) 실행 예시

- 인제스트: `python embedding.py "test/*.txt"` (옵션: `CUSTOM_SCHEMA_WRITE=true`, `PARENT_MODE=page_section`)
- 조회: `python retriever_multi_view_demo.py "질의" [view] [lang]`

---

비고: 현재 코드(embedding.py, retriever_multi_view_demo.py)는 위 전략을 대부분 반영합니다. 추가로 트랜잭션 묶기, 파라미터 튜닝, 캐시 계층 등을 환경에 맞게 보완해 운영 품질을 높이세요.
