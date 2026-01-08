## 임베딩 검증 가이드

`TalkFile_001_clean.md`의 임베딩이 Postgres(pgvector)에 정상 저장됐는지 확인하는 절차입니다.

### 1) DB 접속(컨테이너 내부 `psql`)
- PowerShell:
```
docker exec -it pgvector-db psql -U langchain -d vectordb
```
- 프롬프트가 뜨면 SQL을 입력합니다. 종료는 `\q`.

### 2) 기본 테이블 확인
- 컬럼 구조 확인(권장):
```
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='public' AND table_name='langchain_pg_collection';
```
- 컬렉션 목록(대부분 `uuid`, `name` 컬럼을 가집니다):
```
SELECT uuid, name FROM langchain_pg_collection;
```
- 임베딩 카운트(전체):
```
SELECT COUNT(*) FROM langchain_pg_embedding;
```

### 3) 특정 컬렉션/소스 기준 확인
- 현재 컬렉션 이름은 `.env`의 `COLLECTION_NAME` (예: `langchain_book_ocr`).
- 소스 파일로 필터: `cmetadata->>'source' = 'TalkFile_001_clean.md'`
```
-- 컬렉션 UUID 구하기
WITH c AS (
  SELECT uuid FROM langchain_pg_collection WHERE name = 'langchain_book_ocr'
)
SELECT COUNT(*)
FROM langchain_pg_embedding e
WHERE e.collection_id = (SELECT uuid FROM c)
  AND e.cmetadata->>'source' = 'TalkFile_001_clean.md';
```

### 4) 샘플 레코드 조회(메타데이터/내용 확인)
```
WITH c AS (
  SELECT uuid FROM langchain_pg_collection WHERE name = 'langchain_book_ocr'
)
SELECT 
  LEFT(e.document, 160)        AS content_preview,
  e.cmetadata->>'parent_id'     AS parent_id,
  e.cmetadata->>'view'          AS view,
  e.cmetadata->>'lang'          AS lang,
  e.cmetadata->>'unit_role'     AS unit_role,
  e.cmetadata->>'source'        AS source,
  e.cmetadata->>'content_hash'  AS content_hash
FROM langchain_pg_embedding e
WHERE e.collection_id = (SELECT uuid FROM c)
  AND e.cmetadata->>'source' = 'TalkFile_001_clean.md'
ORDER BY e.id
LIMIT 10;
```

### 5) 벡터 차원 확인(모델 차원 일치 여부)
```
-- 랜덤 1건의 임베딩 길이 확인 (코사인 벡터라 길이 값이 아닌 차원 수는 메타에서 확인 필요)
-- 차원은 스키마에서 관리되므로, 보유한 모델 차원(예: 1024)과 설정(EMBEDDING_DIM)이 일치해야 합니다.
SELECT cmetadata->>'view' AS view, vector_dims(embedding) AS dims
FROM langchain_pg_embedding
LIMIT 1;
```

### 6) 부모 문서(docstore) 확인
- 멀티벡터 검색용 부모 문서가 요약 형태로 저장됩니다.
```
SELECT COUNT(*) FROM docstore_parent;

SELECT id AS parent_id, LEFT(content, 200) AS content_preview
FROM docstore_parent
LIMIT 10;
```

### 7) 인덱스 존재 여부(성능 확인)
```
-- 임베딩 테이블 인덱스 나열
\di+ langchain_pg_embedding*

-- JSONB GIN, HNSW 인덱스 등이 존재해야 합니다.
```

### 8) 커스텀 스키마 사용 시(선택)
- `.env`에 `CUSTOM_SCHEMA_WRITE=true`일 때만 해당
```
-- 자식 청크(커스텀)
SELECT COUNT(*) FROM child_chunks;
SELECT parent_id, view, lang, LEFT(content, 160)
FROM child_chunks
LIMIT 10;

-- 부모 문서(커스텀)
SELECT COUNT(*) FROM parent_docs;
SELECT parent_id, LEFT(content, 200)
FROM parent_docs
LIMIT 10;
```

### 9) 애플리케이션 레벨 검증(리트리버)
- PowerShell 예시:
```
python retriever_multi_view_demo.py "검색어"
python retriever_multi_view_demo.py "검색어" text
python retriever_multi_view_demo.py "검색어" code python
```
- 출력 문서의 `id`(parent_id)와 `content` 프리뷰를 확인하세요.

### 10) 문제 해결 팁
- 결과 0건:
  - `COLLECTION_NAME` 확인(실제 저장된 컬렉션과 일치?), `source` 필터 정확한지 확인
  - 임베딩이 레이트리밋으로 중단되지 않았는지 로그 확인
- 컬럼 이름 불일치:
  - `langchain_pg_collection`의 기본 키는 버전에 따라 `uuid`일 수 있습니다. 먼저 컬럼 구조를 조회하고(2단계) SQL을 맞춰 실행하세요.
- 차원 불일치 경고:
  - `.env`의 `EMBEDDING_DIM`이 사용 중 모델의 차원과 일치하는지 확인(예: Voyage-3는 1024)
- Parent Mode 확인:
  - `PARENT_MODE=page|section|page_section` 설정 여부와 `parent_id` 패턴 확인(`-p<number>`, `-s-<slug>` 등)
- 성능 저하:
  - 인덱스 존재 여부 확인, 컨테이너 자원 확인(CPU/RAM/스토리지 IOPS)

추가 팁(복붙 오류): Windows 터미널에서 붙여넣기 시 `^[[200~`나 `~` 같은 문자가 끼는 경우가 있습니다. 줄을 깨끗하게 지우고 다시 입력하거나, 메모장에 붙여넣어 정리한 후 다시 복사하세요.

## 자주 발생하는 문제 사항(원인/대응)

- 컬럼 이름 불일치로 인한 SQL 오류
  - 증상: `column "id" does not exist`
  - 원인: `langchain_pg_collection`의 PK가 버전에 따라 `uuid`일 수 있음
  - 대응: 먼저 컬럼 구조를 조회한 뒤(`information_schema.columns`) 실제 컬럼명(`uuid`)을 사용

- 임베딩 개수와 로그의 총 청크 수 불일치
  - 증상: 로그에는 `total chunks: 1335`, DB에는 30건 등 적게 보임
  - 원인: `.env`의 `MAX_DOCS_TO_EMBED`로 1회 처리량을 제한했거나, 레이트리밋으로 일부만 처리됨
  - 대응: 스모크 검증 후 `MAX_DOCS_TO_EMBED` 주석 처리/증가, 혹은 VoyageAI 결제수단 추가로 레이트리밋 상향

- 부모 문서 수는 많고(예: 404), 임베딩 청크는 적음(예: 30)
  - 증상: `docstore_parent` 카운트가 높음
  - 원인: 스크립트가 부모(upsert) → 자식(임베딩) 순으로 실행되며, 자식은 스모크 제한 때문에 일부만 저장됨
  - 대응: 정상 동작. 전체 임베딩 후 수치가 수렴함

- 붙여넣기 아티팩트로 인한 구문 오류
  - 증상: `^[[200~` 등 이상한 문자가 포함되어 `syntax error` 발생
  - 대응: 줄을 지우고 다시 타이핑하거나, 메모장 경유 후 깔끔하게 붙여넣기

- 컬렉션 이름 불일치로 결과 0건
  - 증상: 쿼리 결과 0건
  - 원인: `.env`의 `COLLECTION_NAME`과 실제 저장된 컬렉션명이 다름
  - 대응: `SELECT uuid,name FROM langchain_pg_collection;`로 확인 후 쿼리의 이름을 맞춤

- `source` 필터 미스매치
  - 증상: 소스 기준 필터에서 0건
  - 원인: 스크립트는 파일의 베이스이름만 `source`에 저장함(예: `TalkFile_001_clean.md`)
  - 대응: 경로 전체가 아닌 베이스이름으로 필터하거나, 실제 `cmetadata->>'source'` 값을 먼저 조회

- 레이트리밋으로 중도 실패
  - 증상: `voyageai.error.RateLimitError`
  - 원인: 무료 한도(3 RPM/10K TPM) 초과
  - 대응: `.env`의 `RATE_LIMIT_RPM`, `MAX_CHARS_PER_REQUEST`, `MAX_ITEMS_PER_REQUEST`로 요청을 더 잘게 쪼개고 지수 백오프. 빠른 처리 원하면 결제수단 추가
