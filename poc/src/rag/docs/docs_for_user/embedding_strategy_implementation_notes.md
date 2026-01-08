# 임베딩 전략 구현 노트

이 문서는 `docs/embedding_strategy_checklist.md`를 코드에 반영하면서 추가된 안전성/멱등성, 선택적 튜닝 항목을 요약합니다.

## 변경 요약

- 차원 검증: `embedding.py`에서 모델 출력 벡터 길이가 `EMBEDDING_DIM`과 일치하는지 한 번 점검(네트워크/권한 이슈 시 경고만 표시).
- 안정적 문서 ID: 벡터 적재 시 콘텐츠 해시 기반의 결정적 ID를 생성하여 재실행 시 중복 삽입을 방지(`PGVector.add_documents(ids=...)` 사용, 미지원 버전은 자동 폴백).
- child 중복 방지 스키마: 커스텀 테이블 `child_chunks`에 `content_hash` 컬럼과 `(parent_id, view, lang, content_hash)` 유니크 인덱스를 추가하여 멱등 삽입 보장.
- 트랜잭션 이중쓰기(커스텀 스키마): 부모(`parent_docs`)와 자식(`child_chunks`) 쓰기를 하나의 트랜잭션으로 처리.
- 선택적 ANN 튜닝: DB 권한이 있을 경우 `IVFFLAT_PROBES`, `HNSW_EF_SEARCH`, `HNSW_EF_CONSTRUCTION` 환경변수로 기본 파라미터를 설정(실패해도 경고만).
- OCR 정규화 개선: 취약한 치환 매핑을 안전한 `NORMALIZE_MAP`으로 교체.
- 실행 요약: 적재 종료 시 총 chunk 수와 parent 수를 로그로 출력.

## 신규/변경 환경 변수

- `IVFFLAT_PROBES`: 정수(옵션). 설정 시 `ALTER DATABASE CURRENT SET ivfflat.probes = <값>` 시도.
- `HNSW_EF_SEARCH`: 정수(옵션). 설정 시 `ALTER DATABASE CURRENT SET hnsw.ef_search = <값>` 시도.
- `HNSW_EF_CONSTRUCTION`: 정수(옵션). 설정 시 `ALTER DATABASE CURRENT SET hnsw.ef_construction = <값>` 시도.

DB 역할 권한이 필요합니다. 실패 시 적재/조회는 계속 진행되며 경고만 표시됩니다.

## 개발자 참고

- VectorStore 멱등 처리: `(parent_id, view, lang, content)`로 `content_hash`를 만들고 `doc:<hash>` 형태의 안정적 ID를 생성하여 `PGVector.add_documents`에 전달합니다. 만약 설치된 `langchain_postgres` 버전이 `ids=`를 지원하지 않으면 자동으로 ID 없이 동작합니다.
- 커스텀 스키마 멱등성: `ensure_custom_schema()`가 `content_hash` 컬럼과 유니크 인덱스를 정의합니다. 기존 테이블 호환을 위해 `ADD COLUMN IF NOT EXISTS`도 포함되어 있습니다.
- 이중쓰기: `dual_write_custom_schema()`는 부모와 자식을 한 트랜잭션에서 처리합니다. 반면 LangChain을 통한 `langchain_pg_embedding` 쓰기는 동일 트랜잭션으로 묶이지 않습니다.
- 차원 점검: `validate_embedding_dimension()`이 1회 `embed_documents(["__dim_check__"])`를 호출해 벡터 길이를 확인하고 불일치 시 경고합니다.

## 수정 파일

- `embedding.py`
  - 정규화 맵 추가, 차원 검증, DB 레벨 튜닝, 중복 방지 ID 로직, 커스텀 스키마 트랜잭션 이중쓰기, 총계 로그 추가.
  - 커스텀 스키마에 `content_hash`와 유니크 인덱스 추가.
- `retriever_multi_view_demo.py`
  - 시작 시(조회) 선택적 DB 레벨 ANN 튜닝 시도.

## 한계/주의

- DB 권한: ANN 파라미터 변경은 DB 권한이 필요하며, 적용되더라도 이후 세션에 반영됩니다.
- 완전한 트랜잭션 일관성: `langchain_pg_embedding`에 대한 쓰기는 LangChain 경유로 이루어져 커스텀 스키마 쓰기와 같은 트랜잭션으로 묶이지 않습니다.

## 사용 방법

1) 필수 환경변수 설정: `PG_CONN`, `COLLECTION_NAME`, `VOYAGE_MODEL`, `EMBEDDING_DIM`.
2) 선택: `CUSTOM_SCHEMA_WRITE=true`로 커스텀 스키마와 트랜잭션 이중쓰기 활성화.
3) 선택(튜닝): 권한이 있다면 `IVFFLAT_PROBES`, `HNSW_EF_SEARCH`, `HNSW_EF_CONSTRUCTION` 설정.
4) 적재: `python embedding.py "test/*.txt"`
5) 조회: `python retriever_multi_view_demo.py "<query>" [view] [lang]`
