# embedding.py 임베딩 파이프라인 개요

- 목적: OCR 결과 텍스트(.txt)를 전처리 → 문단/코드 감지 → “유닛” 단위로 문맥·코드를 묶어 청크 생성 → VoyageAI 임베딩으로 pgvector(LangChain Postgres)에 업서트.
- 구성: 전처리/세분화, 코드 판별·언어 추정, 유닛화(streaming pairing), 청크 분할(텍스트/코드), 임베딩/저장, 보조 인덱스 생성.
- 기준 파일: `embedding.py`

## 환경 변수

- `PG_CONN`: Postgres 접속 문자열(예: `postgresql+psycopg://...`).
- `COLLECTION_NAME`: 벡터 컬렉션 이름.
- `VOYAGE_MODEL`: VoyageAI 임베딩 모델명, 기본 `voyage-3`.
- `EMBEDDING_DIM`: 임베딩 차원 수, 기본 `1024`.

## 파이프라인 개요

1) 파일 로딩: glob 패턴으로 입력 텍스트 파일 탐색.
2) 전처리: 합자 치환/공백 정리/개행 축소 후 문단 분리.
3) 코드 감지·언어 추정: Python/JavaScript 휴리스틱.
4) 유닛화: Python 앞 텍스트를 `pre_text`로 묶고, 이어지는 JS를 같은 유닛에 `javascript`로 연결.
5) 청크 분할: 텍스트는 재귀 분할, 코드는 행 단위 안전 분할.
6) 문서화: LangChain `Document`로 변환, 메타데이터 풍부화.
7) 임베딩/업서트: VoyageAI + `PGVector`로 업서트.
8) 인덱스: HNSW(cosine) + JSONB GIN + 보조 BTREE 생성.

## 전처리/세분화

- `normalize(text)`
  - 합자/특수기호 교정(LIGATURES), `\u00A0`→공백, 줄 끝 공백 제거, 과도한 개행 축소, 전체 trim.
  - 주의: LIGATURES 매핑 일부 문자가 환경에 따라 깨져 보일 수 있어 재검증 권장.
- `split_paragraph(text)`
  - 빈 줄(연속 2개 이상의 개행) 기준 문단 분리.

## 코드 블록 판별/언어 추정

- `is_code_block(p)`
  - 백틱 코드펜스(```` `) 존재 시 코드.
  - 또는 `CODE_HINT` 정규식 적중 횟수 기반(파이썬/JS 주요 키워드, `=>`, 세미콜론/중괄호 라인 끝 등).
- `guess_code_lang(p)`
  - `PY_SIGNS`/`JS_SIGNS` 매칭 수 비교 → `python` vs `javascript` 결정.
  - 보강 규칙: `def`/`class`는 Python, `console.log`/`=>`/세미콜론 라인끝은 JavaScript.
- `parse_ocr_file(path)`
  - 문단을 `RawSegment(kind, content, language, order)`로 변환.
  - `kind`: `text` 또는 `code`, `language`: `python`/`javascript`/None.

## 유닛화(streaming pairing)

- 함수: `unitize_txt_py_js_streaming(segments, attach_pre_text=True, attach_post_text=False, bridge_text_max=0, max_pre_text_chars=4000)`
- 목적: Python 코드와 그 앞뒤 문맥을 하나의 “유닛(unit_id)”으로 묶고, 이어지는 JavaScript가 있으면 같은 유닛으로 연결.
- 동작 요약
  - 텍스트 버퍼를 유지하다가 Python 코드가 시작되면 새 `unit_id`를 만들고 버퍼를 `pre_text`로 부착(초과분은 `other`).
  - Python 연속 블록을 `python`으로 수집.
  - `bridge_text_max` 범위 내에서 Python–JS 사이 텍스트를 `bridge_text`로 연결(기본 0: 미사용).
  - 바로 이어지는 JS 연속 블록을 `javascript`로 수집.
  - `attach_post_text=False`(기본): JS 뒤 텍스트는 다음 유닛의 `pre_text` 후보로 버퍼링. True면 현재 유닛의 `post_text`로 부착.
  - 고립된 JS(앞선 Python 없음)나 언어 미상 코드는 `other` 처리.
- 출력: `(unit_id|None, unit_role, segment)` 튜플 목록. `unit_role ∈ {pre_text, python, bridge_text, javascript, post_text, other}`.

## 청크 분할

- 텍스트: `RecursiveCharacterTextSplitter`
  - `chunk_size=1200`, `chunk_overlap=150`.
  - `separators=["\n##", "\n###", "\n\n", "\n", " ", ""]`로 의미 단위 우선 분할.
  - `add_start_index=True`로 원문 시작 오프셋 유지.
- 코드: `split_code_safely(code, max_chars=1800, overlap_lines=5)`
  - 행 단위 누적 길이로 안전 분할, 다음 청크에 5라인 겹침.
  - 매우 긴 단일 행은 잘라서 배출.

## 문서 및 메타데이터

- 생성: `build_document_from_unitized(path, unitized)` → `List[Document]`
- 공통 메타: `source`(파일명), `order`, `kind`.
- 유닛 메타: `unit_id`(있으면), `parent_id=unit_id`(Parent-Child 검색 대비), `unit_role`.
- 뷰/언어: 텍스트 `view="text"`, 코드 `view="code"`, 코드에 `lang` 포함.

## 임베딩/저장

- 임베딩: `VoyageAIEmbeddings(model=VOYAGE_MODEL)`
- 저장소: `PGVector(connection=PG_CONN, collection_name=COLLECTION, distance_strategy="COSINE", use_jsonb=True, embedding_length=EMBEDDING_DIM)`
- 업서트: `upsert_batch(store, docs, batch_size=64)` 배치 삽입.

## 인덱스/성능

- `ensure_extension_vector()` → `CREATE EXTENSION IF NOT EXISTS vector;`
- `ensure_indexes()`
  - 테이블: `langchain_pg_embedding`(LangChain Postgres 기본 스키마 가정).
  - 인덱스명: `sanitize_identifier(COLLECTION)`로 안전화한 컬렉션명 사용.
  - HNSW(cosine): `embedding vector_cosine_ops`
  - GIN(JSONB): `cmetadata`
  - BTREE: `cmetadata->>'unit_id'`, `unit_role`, `lang`, `parent_id`, `view`

## 실행 흐름(main)

- 입력: `input_glob`(기본 `test/*.txt`)
- 처리: 파싱 → 유닛화(기본: `attach_pre_text=True`, `attach_post_text=False`, `bridge_text_max=0`) → 문서화 → 업서트
- 종료: 총 청크 수 출력 → 인덱스 생성(멱등) → 완료 로그.

## 기본값/튜닝 포인트

- 모델·차원: `VOYAGE_MODEL`, `EMBEDDING_DIM`.
- 청크링: 텍스트(`chunk_size`, `chunk_overlap`, `separators`), 코드(`max_chars`, `overlap_lines`).
- 유닛화: `attach_pre_text`, `attach_post_text`, `bridge_text_max`, `max_pre_text_chars`.
- 배치 크기: `batch_size`(업서트 성능).

## 특징 요약

- 문맥 보존: Python 앞 텍스트를 `pre_text`로 붙여 코드-설명 회수를 용이하게 함.
- 다언어 코드 대응: Python/JavaScript 휴리스틱 식별 및 연결. 고립된 JS는 `other`로 격리.
- 안전 분할: 텍스트/코드 각각에 최적화된 분할로 청크 품질 유지.
- 메타 풍부화: `unit_id/parent_id/unit_role/view/lang/order` 저장으로 필터/Parent-Child 검색 최적화.
- 성능 고려: HNSW + JSONB GIN + BTREE 보조 인덱스로 검색/필터 성능 확보.

## 주의/한계

- LIGATURES 매핑은 환경/인코딩에 따라 깨질 수 있어 실제 교정 결과 점검 필요.
- 언어 추정은 휴리스틱이므로 혼합/의사코드에는 오탐 가능.
- 기본 `attach_post_text=False`로 JS 뒤 텍스트는 다음 유닛 `pre_text`로 이동(의도된 동작인지 확인 권장).

## 멀티 벡터(멀티 뷰) 리트리빙

- 개념: 하나의 논리 유닛(`unit_id`/`parent_id`) 아래에 서로 다른 관점의 청크를 각각 임베딩해 저장합니다. 텍스트는 `view="text"`, 코드는 `view="code"`(+ `lang`), 같은 `unit_id`로 묶입니다.
- 구현: LangChain의 `MultiVectorRetriever` 클래스를 직접 사용하지는 않으며, `PGVector`에 뷰별 벡터를 저장하고 메타 필터(`view`, `lang`) + `parent_id` 그룹핑으로 멀티뷰 검색을 구성합니다.
- 조회 절차: 쿼리를 뷰별로 수행 → 결과를 `parent_id`로 그룹핑/통합 → 필요 시 그룹 단위 재랭킹/중복 제거.
- 인덱스: `ensure_indexes()`가 `view`, `lang`, `parent_id`, `unit_id` 등에 인덱스를 생성해 필터/그룹핑 성능을 보장합니다.

### 사용 예시

```python
import os
from collections import defaultdict
from langchain_voyageai import VoyageAIEmbeddings
from langchain_postgres import PGVector

emb = VoyageAIEmbeddings(model=os.getenv("VOYAGE_MODEL", "voyage-3"))
store = PGVector(
    connection=os.environ["PG_CONN"],
    collection_name=os.environ["COLLECTION_NAME"],
    embeddings=emb,
    distance_strategy="COSINE",
    use_jsonb=True,
    embedding_length=int(os.environ.get("EMBEDDING_DIM", "1024")),
)

def retrieve_multi_view(query, k_text=4, k_code=4, only_py=False):
    # 뷰별 검색
    results = []
    results += store.similarity_search(query, k=k_text, filter={"view": "text"})
    code_filter = {"view": "code"}
    if only_py:
        code_filter["lang"] = "python"
    results += store.similarity_search(query, k=k_code, filter=code_filter)

    # parent_id로 그룹핑
    groups = defaultdict(list)
    for d in results:
        pid = d.metadata.get("parent_id") or d.metadata.get("unit_id") or "no_parent"
        groups[pid].append(d)
    return groups  # {parent_id: [Documents...]}

# 예시: 코드 위주 검색
groups = retrieve_multi_view("비동기 파일 처리 예시", k_text=3, k_code=7, only_py=True)
```

단일 뷰만 빠르게 보려면 다음처럼 필터만 주면 됩니다.

```python
docs_text = store.similarity_search("쿼리", k=5, filter={"view": "text"})
docs_code = store.similarity_search("쿼리", k=5, filter={"view": "code", "lang": "python"})
```

## 이미지(사진) 관점 통합

- 현재 스크립트는 OCR 텍스트(.txt)만 처리합니다. 이미지를 함께 쓰려면 이미지 임베딩 파이프라인을 추가해야 합니다.
- 권장: 텍스트와 차원이 다른 모델(CLIP 등)을 쓰는 경우 “별도 컬렉션”으로 운용하고, `metadata.view = "image"`를 부여합니다. 조회 시 텍스트/코드/이미지의 결과를 병합해 `parent_id`로 그룹핑하세요.
- 동일 컬렉션 사용(권장 X): 텍스트/이미지 임베딩 차원이 동일해야 하며, 쿼리/색인 일관성을 주의해야 합니다.

