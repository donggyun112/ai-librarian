# PoC 메모: Postgres 단일 스택(부모 + 자식)

## 핵심 이점

- 의존성 1개: Postgres만 관리하면 됨(트랜잭션/백업/복구를 한 번에).
- 일관성 보장: 부모/자식을 한 트랜잭션으로 넣어 재색인·롤백 시 안전.
- 확장 용이: 성능 한계가 보이면 읽기 캐시로 Redis를 얹어 단계적 확장.
- 토큰·속도 밸런스: 부모 문서를 1~2KB로 유지해 RAG 컨텍스트 비용 절감.

## 데이터 모델(최소 스키마)

- 벡터(자식 청크): LangChain `PGVector` 기본 테이블 `langchain_pg_embedding`
  - `embedding`(vector), `page_content`(text), `cmetadata`(jsonb: `parent_id`, `view`, `lang`, `order` 등)
- 부모 문서: `docstore_parent`
  - `id` text PK(= `parent_id`), `content` text(대표 본문 1~2KB 권장), `metadata` jsonb(선택)

## 운영 포인트

- 인제스트: 자식 업서트와 부모 업서트를 동일 트랜잭션으로 묶어 정합성 유지(필요 시).
- 인덱스: HNSW(cosine) + JSONB GIN + BTREE(view/lang/parent_id)로 메타 필터/ANN 최적화.
- 캐시: 고QPS 구간에서 부모 본문을 Redis로 캐싱(키=`parent_id`, 값=utf-8 bytes)하여 읽기 지연 감소.
- 관측: SQL로 상태 점검(실행 계획, 크기, 인덱스 히트) 및 문제 재현이 용이.

## 설치/확장(0)

- 확장 설치

```sql
CREATE EXTENSION IF NOT EXISTS vector;
-- 선택: 텍스트 유사도/보조 검색을 원하면
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

- 부모 테이블(요약)

```sql
CREATE TABLE IF NOT EXISTS docstore_parent (
  id         text PRIMARY KEY,
  content    text NOT NULL,
  metadata   jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
```

- 트리거/인덱스(요약)

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_docstore_parent_updated ON docstore_parent;
CREATE TRIGGER trg_docstore_parent_updated
BEFORE UPDATE ON docstore_parent
FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE INDEX IF NOT EXISTS idx_docstore_parent_meta_gin
  ON docstore_parent USING GIN (metadata);
```

- 인제스트 요약
  - 자식: `PGVector.add_documents()` (메타: `parent_id`, `view`, `lang` 등)
  - 부모: `INSERT ... ON CONFLICT (id) DO UPDATE ...`로 대표 본문 업서트

- 검색 요약
  - `PGVector`에서 메타 필터로 자식 검색 → `parent_id` 중복 제거 → `docstore_parent`에서 부모 복원
  - 또는 `MultiVectorRetriever(id_key="parent_id")`로 부모 단위 결과를 직접 획득

