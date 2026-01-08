# PoC: PGVector + Postgres 단일 DocStore 설계

본 문서는 벡터 임베딩(자식 청크)과 부모 문서(DocStore)를 모두 Postgres 내에서 운영하는 단일 스택 설계를 제안합니다. 목표는 인프라 단순화(한 DB), 트랜잭션 일관성, 운영/관측성 향상입니다.

## 목표(Goal)

- Multi-Vector Retriever를 사용하되, 부모 문서(대표 본문)와 자식 청크(임베딩 대상)를 한 DB(Postgres + pgvector)에 담아 의존성을 최소화하고 운영을 단순화하여 PoC를 빠르게 검증한다.

## 목표/범위

- 목표: PGVector + Postgres만으로 멀티뷰 검색(텍스트/코드)과 부모 문서 복원을 지원
- 범위: 스키마/인덱스, 인제스트·검색 플로우, 예시 코드, 운영 고려사항
- 비범위: 임베딩 품질/LLM 프롬프팅, 이미지 임베딩(별도 컬렉션 권장)

## 아키텍처 개요

- 벡터 테이블: LangChain `PGVector` 기본 테이블(`langchain_pg_embedding`) 사용
  - 자식 문서(청크) 저장: `page_content` + `embedding` + `cmetadata(JSONB)`
  - 메타: `parent_id`, `unit_id`, `view(text|code)`, `lang`, `order` 등
- 부모 DocStore(신규): `docstore_parent` 테이블
  - 부모 키 = `parent_id`(=unit_id)
  - 부모 콘텐츠 = 대표 텍스트(요약/헤더/선정 문단)
  - 부모 메타 = 원본 파일/뷰 요약 등(선택)

## 스키마 제안

```sql
-- 벡터 확장 (이미 embedding.py에서 ensure_extension_vector() 수행)
CREATE EXTENSION IF NOT EXISTS vector;

-- 부모 문서 저장소
CREATE TABLE IF NOT EXISTS docstore_parent (
  id           text PRIMARY KEY,          -- parent_id (unit_id)
  content      text NOT NULL,             -- 대표 부모 콘텐츠 (1~2KB 권장)
  metadata     jsonb DEFAULT '{}'::jsonb, -- 부가 메타 (선택)
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now()
);

-- 업데이트 타임스탬프 유지
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

-- 메타 검색/필터 대비 인덱스
CREATE INDEX IF NOT EXISTS idx_docstore_parent_meta_gin ON docstore_parent USING GIN (metadata);
```

참고: 부모 콘텐츠를 바이트(`bytea`)나 JSON으로 저장할 수도 있으나, 읽기/표시 용도라면 `text`가 단순합니다.

## 인덱스/성능

- 벡터: `embedding vector_cosine_ops` HNSW, `cmetadata` GIN, `view/lang/parent_id` BTREE (이미 `embedding.py`의 `ensure_indexes()`에 포함)
- 부모: `PRIMARY KEY(id)`, `metadata` GIN
- 선택: `pg_trgm`를 활용한 `content` 유사도 인덱스(백업 검색용)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_docstore_parent_content_trgm ON docstore_parent USING gin (content gin_trgm_ops);
```

## 인제스트 플로우(요약)

1) 텍스트/코드 파싱 → 유닛화(`unit_id=parent_id`) → 청크 생성
2) 자식(청크) 저장: `PGVector.add_documents()` (현행과 동일)
3) 부모 생성: `parent_id`별 대표 텍스트 구성(pre_text 우선, 없으면 text 상위 1~2개, 최대 ~2KB)
4) 부모 저장: `INSERT ... ON CONFLICT (id) DO UPDATE SET content=..., metadata=...`

## 검색 플로우(요약)

- 멀티뷰: `PGVector`에서 뷰/언어 필터로 자식을 검색 → `parent_id`로 중복 제거 → `docstore_parent`에서 부모를 `SELECT`로 복원 → 상위 N 부모 반환
- 또는 LangChain `MultiVectorRetriever` 사용 시: Postgres를 백엔드로 한 DocStore 어댑터를 연결(id_key=`parent_id`)

## 예시 코드: 부모 저장/복원 (psycopg)

```python
import os, psycopg
from typing import List, Tuple

PG_CONN = os.environ["PG_CONN"].replace("postgresql+psycopg", "postgresql")

def upsert_parents(rows: List[Tuple[str, str, dict]]):
    # rows: [(parent_id, content_text, metadata_json), ...]
    sql = """
    INSERT INTO docstore_parent (id, content, metadata)
    VALUES (%s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
      content = EXCLUDED.content,
      metadata = docstore_parent.metadata || EXCLUDED.metadata,
      updated_at = now();
    """
    with psycopg.connect(PG_CONN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)

def fetch_parents(ids: List[str]):
    sql = "SELECT id, content, metadata FROM docstore_parent WHERE id = ANY(%s)"
    with psycopg.connect(PG_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (ids,))
            return {rid: (content, meta) for rid, content, meta in cur.fetchall()}
```

## 예시 코드: MultiVectorRetriever 연동(커스텀 Postgres DocStore)

LangChain `MultiVectorRetriever`는 `docstore`로 키-바이트 저장소를 기대합니다. 간단한 어댑터를 통해 Postgres를 연결할 수 있습니다.

```python
from typing import Iterable, List, Tuple, Optional
import json, psycopg

class PostgresByteStore:
    """간단한 키-바이트 DocStore 어댑터 (id => bytes)"""
    def __init__(self, conn_str: str, table: str = "docstore_parent", key_col: str = "id", val_col: str = "content"):
        self.conn_str = conn_str
        self.table = table
        self.key_col = key_col
        self.val_col = val_col
    def mset(self, items: Iterable[Tuple[str, bytes]]):
        sql = f"""
        INSERT INTO {self.table} ({self.key_col}, {self.val_col})
        VALUES (%s, %s)
        ON CONFLICT ({self.key_col}) DO UPDATE SET {self.val_col} = EXCLUDED.{self.val_col}, updated_at = now();
        """
        with psycopg.connect(self.conn_str, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, list(items))
    def mget(self, keys: List[str]) -> List[Optional[bytes]]:
        sql = f"SELECT {self.key_col}, {self.val_col} FROM {self.table} WHERE {self.key_col} = ANY(%s)"
        with psycopg.connect(self.conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (keys,))
                data = {k: v.encode("utf-8") if isinstance(v, str) else v for k, v in cur.fetchall()}
        return [data.get(k) for k in keys]
```

사용 예시(부모는 UTF-8 텍스트로 저장/복원):

```python
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_voyageai import VoyageAIEmbeddings
from langchain_postgres import PGVector

emb = VoyageAIEmbeddings(model=os.getenv("VOYAGE_MODEL", "voyage-3"))
vec = PGVector(
    connection=os.environ["PG_CONN"],
    collection_name=os.environ["COLLECTION_NAME"],
    embeddings=emb,
    distance_strategy="COSINE",
    use_jsonb=True,
    embedding_length=int(os.getenv("EMBEDDING_DIM", "1024")),
)

pg_conn = os.environ["PG_CONN"].replace("postgresql+psycopg", "postgresql")
docstore = PostgresByteStore(pg_conn)

retriever = MultiVectorRetriever(
    vectorstore=vec,
    docstore=docstore,
    id_key="parent_id",
    search_kwargs={"k": 8},
)
parents = retriever.get_relevant_documents("비동기 파일 처리 예시")
```

## 운영/보안 고려

- 트랜잭션: 인제스트 시 자식 업서트와 부모 업서트를 하나의 트랜잭션으로 묶어 일관성 강화 가능
- 백업/복구: 단일 DB 스냅샷으로 백업 단순화
- 접근 제어: 애플리케이션 롤에 `docstore_parent`에 대한 최소 권한 부여
- 모니터링: 인덱스 상태, 테이블 크기, 자주 조회되는 부모 라인, 캐시 히트 비율 관측 추천
- 보안: SSL/TLS, 비밀정보는 환경 변수/비밀관리자 사용

## 장단점 요약

- 장점: 인프라 단순, 트랜잭션 일관성, SQL 기반 디버깅/관측, 비용 절감
- 단점: 고QPS/대용량에서 DocStore-전용 시스템(예: Redis/S3) 대비 탄력성/비용 한계 가능, 내용이 큰 부모를 저장하면 I/O 증가

## 왜 Postgres 하나로 이 PoC에 유리한가

- 의존성 최소화: Redis/S3 등 별도 시스템 없이 단일 DB로 구축해 네트워크·권한·배포 복잡도를 줄이고 PoC 속도를 높임.
- 트랜잭션 일관성: 부모 저장과 자식 임베딩 업서트를 동일 트랜잭션으로 처리 가능해 데이터 정합성 확보가 용이.
- 운영 단순화: 백업/복구, 접근제어, 모니터링, 비용 관리가 한 시스템에 집중되어 초기 운영 부담이 낮음.
- 충분한 성능/기능: pgvector(HNSW), JSONB(GIN), BTREE 인덱스 조합으로 메타 필터 + 근사 최근접 탐색을 PoC 규모에서 충분히 커버.
- 관측/디버깅 용이: SQL로 상태 점검(인덱스, 카디널리티, 실행계획)과 데이터 검증이 쉬워 문제 재현과 튜닝이 빠름.
- 배포 단순성: 애플리케이션 측 연결/풀링/마이그레이션 파이프라인을 하나로 유지해 CI/CD 단계를 단축.
- 비용 효율: 초기 PoC 단계에서 추가 매니지드 서비스 비용(트래픽/스토리지/요청 건수)을 피하고 예산을 절감.
- 확장 경로 보장: PoC로 패턴 검증 후, 병목이 확인되면 부모만 외부 DocStore(예: Redis/S3)로 분리하는 단계적 확장 가능.

## 향후 확장

- 부모 콘텐츠 자동 요약 파이프라인 추가(길이·품질 표준화)
- 페더레이션: 이미지/다른 모달은 별도 컬렉션, 애플리케이션 레벨에서 병합
- TTL/보존정책: 오래된 부모 문서 정리(파티셔닝/정책)
- 테스트: 리그레션 쿼리 셋으로 품질 모니터링

```text
결론: 현재 메타 설계(parent_id/view/lang)를 그대로 활용하면서 Postgres 단일 스택으로 부모-자식 검색을 구성할 수 있습니다. 운영 복잡도를 낮추고 일관성을 높이며, 필요 시 MultiVectorRetriever와도 쉽게 통합됩니다.
```
