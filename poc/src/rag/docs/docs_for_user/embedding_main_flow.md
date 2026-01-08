# embedding.py 실행 흐름 문서

이 문서는 `embedding.py`의 `main()`이 어떤 순서로 어떤 메서드를 호출하며, 각 메서드가 어떤 역할을 하는지 요약합니다. 입력(텍스트/PDF/Markdown)을 세그먼트화하고 부모-자식 문서 메타를 구성한 뒤, 임베딩을 계산하여 Postgres(pgvector)에 적재하는 전체 파이프라인을 설명합니다.

## 실행 진입점
- `__main__`: 인자 `sys.argv[1]`의 글롭 패턴을 `main(glob_args)`로 전달합니다. 기본값은 `"test/*.txt"`입니다.
- `.env` 환경변수 로드 후 다음 주요 값들을 사용합니다:
  - 연결/컬렉션: `PG_CONN`, `COLLECTION_NAME`
  - 임베딩: `EMBEDDING_PROVIDER`(voyage|gemini), `VOYAGE_MODEL`, `GEMINI_EMBED_MODEL`, `EMBEDDING_DIM`
  - 레이트리밋/배치: `RATE_LIMIT_RPM`, `MAX_CHARS_PER_REQUEST`, `MAX_ITEMS_PER_REQUEST`, `MAX_DOCS_TO_EMBED`
  - 부모 그룹핑: `PARENT_MODE`(unit|page|section|page_section), `PAGE_REGEX`, `SECTION_REGEX`
  - 스키마/확장: `CUSTOM_SCHEMA_WRITE`, 자동 OCR: `ENABLE_AUTO_OCR`

## main() 상단 초기화/DB 준비
1) `build_embeddings()`
- 임베딩 클라이언트를 생성합니다.
  - `EMBEDDING_PROVIDER=gemini`: 내부 `_GeminiEmbeddings`로 `google.generativeai`를 호출하도록 래핑합니다.
  - 기본(voyage): `langchain_voyageai.VoyageAIEmbeddings` 사용.

2) `validate_embedding_dimension(embeddings, EMBDDING_DIM)`
- 모델이 반환한 벡터 길이와 기대 차원수를 비교하여 불일치 시 경고합니다.

3) `apply_db_level_tuning()`
- `IVFFLAT_PROBES`, `HNSW_EF_SEARCH`, `HNSW_EF_CONSTRUCTION` 환경변수를 감지해 데이터베이스 파라미터를 적용합니다(있을 때만).

4) `PGVector(...)` 인스턴스 생성
- LangChain `PGVector` 벡터 스토어를 초기화합니다(`distance_strategy="COSINE"`, `use_jsonb=True`, `embedding_length=EMBDDING_DIM`).

5) 입력 파일 수집 및 사전 점검
- `glob.glob(input_glob)`으로 파일 목록을 정렬 수집. 없으면 경고 후 종료.

6) 스키마/확장 준비
- `ensure_extension_vector()`: `CREATE EXTENSION IF NOT EXISTS vector;`
- `ensure_parent_docstore()`: 멀티벡터 리트리버용 부모 저장소 `docstore_parent` 테이블/트리거/GIN 인덱스 생성.
- `ensure_custom_schema()`: `CUSTOM_SCHEMA_WRITE=true`일 때 커스텀 스키마(`child_chunks`, `parent_docs` + 인덱스/트리거) 생성.

## 파일 단위 파이프라인 (main 루프)
각 파일 `path`에 대해 다음 순서로 처리합니다.

1) 입력 파싱 선택
- PDF: `extract_text_from_pdf(path)` → 우선 `pdfminer.six`, 실패 시 `pdftotext` CLI.
  - `is_low_text_density(txt)`로 희소하면 OCR 제안 로그 출력.
  - `ENABLE_AUTO_OCR=true`이며 `ocrmypdf`가 있으면 사이드카 `.txt` 생성 후 로드 시도.
  - 결과 텍스트가 있으면 `parse_ocr_text(txt)`로 세그먼트화.
- Markdown: `parse_markdown_file(path)` → 내부 `parse_markdown_text(raw)` 사용.
- 일반 텍스트: `parse_ocr_file(path)` → 내부 `parse_ocr_text(raw)` 사용.

2) 세그먼트화(텍스트/코드/이미지)
- `parse_ocr_text(raw)`
  - `normalize`(OCR 특수문자/공백 정리) → `split_paragraph`(빈 줄 기준 분단) → `is_code_block`(코드 힌트·기호 분포·들여쓰기 등)로 코드 여부 판정 → `guess_code_lang`(python/javascript 추정) → `RawSegment(kind='text'|'code', language, order)` 리스트 반환.
- `parse_markdown_text(raw)`
  - 펜스 코드블록(````lang`)을 그대로 캡처하고, 이미지(`![alt](url)`)를 `kind='image'` 세그먼트로 분리. 텍스트만 정규화. 순서 보존.

3) 유닛(Unit) 구성
- `unitize_txt_py_js_streaming(segments, attach_pre_text=True, attach_post_text=False, bridge_text_max=0)`
  - 연속 텍스트를 버퍼링하여 이후 최초 python 코드블록의 `pre_text`로 귀속(과도한 길이는 `other`로 배출).
  - 하나의 유닛에 `python` → (옵션 `bridge_text`) → `javascript` 순으로 결합. 단독 js는 상황에 따라 `other` 처리.
  - 결과는 `(unit_id, unit_role, RawSegment)` 목록(`unit_role ∈ {pre_text, python, javascript, post_text, other, bridge_text}`).

4) 자식 `Document` 생성
- `build_document_from_unitized(path, unitized)`
  - 텍스트: `RecursiveCharacterTextSplitter`로 분할(`chunk_size=1200`, `overlap=150`).
  - 코드: `split_code_safely`로 함수/클래스 경계를 우선해 분할.
  - 이미지: `alt/url` 메타를 포함한 텍스트 콘텐츠 생성.
  - 공통 메타: `source`, `order`, `kind`, `unit_id`, `parent_id(=unit_id)`, `view(text|code|image)`, `lang(코드 시)`.

5) 캡션 보강
- `augment_with_captions(docs)`
  - 텍스트 뷰에서 `figure|fig.|table|그림` 패턴의 캡션 라인을 찾아 `view=figure|table`, `kind=caption`인 별도 문서를 추가(다음 짧은 줄을 보강 텍스트로 덧붙임).

6) 부모 ID 할당(페이지/섹션 기반)
- `assign_parent_by_page_section(docs, path)`
  - `PARENT_MODE=unit|page|section|page_section`에 따라 `parent_id`를 재할당.
  - 페이지: `PAGE_REGEX` 또는 `--- Page Break ---` 카운터.
  - 섹션: `SECTION_REGEX`(헤더/장/번호 체계)로 탐지.
  - 파일명 슬러그를 접두어로 하여 `parent_id`를 생성(예: `file-p3-s-intro`).

7) 부모 문서 합성 및 업서트
- `build_parent_entries(docs)`
  - `parent_id`별 자식 묶음에서 `synthesize_parent_content(childs, pid)`로 대표 텍스트를 합성(헤더/캡션 힌트 + 선행 문장 요약, ~2000자 제한).
  - 부모 메타: 최초 `page`, `order`, `views`, `source_set` 등을 집계.
- `upsert_parents(parents)`
  - 부모 문서를 `docstore_parent`에 UPSERT.
- `dual_write_custom_schema(embeddings, parents, docs)`
  - `CUSTOM_SCHEMA_WRITE=true`일 때, 트랜잭션 내에 `parent_docs` UPSERT 후 자식 `child_chunks` 임베딩 계산→벡터와 함께 INSERT(고유 인덱스로 중복 방지).

8) 자식 청크 벡터 적재
- `upsert_batch(store, docs)`
  - `compute_doc_id_for()`로 `content_hash` 기반 dedup.
  - `MAX_CHARS_PER_REQUEST`/`MAX_ITEMS_PER_REQUEST` 예산에 맞춘 마이크로 배치.
  - `RATE_LIMIT_RPM`에 따른 슬리핑과 지수 백오프로 레이트리밋 대응.

9) 마무리/인덱스 생성
- 누계 로그 출력: 총 청크/부모 개수.
- `ensure_indexes()`
  - `langchain_pg_embedding`에 HNSW(cosine) 벡터 인덱스, `cmetadata` JSONB GIN, 주요 필드 BTREE 인덱스(`parent_id`, `view`, `unit_role`, `lang`, `source`, `order`)를 컬렉션명 접두어로 생성(멱등).

## 주요 헬퍼 요약
- 텍스트 정리/감지: `normalize`, `split_paragraph`, `is_code_block`, `guess_code_lang`.
- 코드 분할: `split_code_safely`.
- 식별자/중복: `sanitize_identifier`, `content_hash`, `compute_doc_id_for`.
- PDF/품질: `extract_text_from_pdf`, `is_low_text_density`.
- 스키마/적재(커스텀): `ensure_custom_schema`, `upsert_parents_custom`, `upsert_child_chunks_custom`.

## 실행 예시
```bash
# 텍스트 파일 일괄 임베딩
python embedding.py "data/*.txt"

# 마크다운 파일 임베딩
python embedding.py "notes/**/*.md"

# PDF + 자동 OCR 활성화(설정 필요)
set ENABLE_AUTO_OCR=true
python embedding.py "scans/*.pdf"
```

## 환경변수 체크리스트
- 연결/컬렉션: `PG_CONN`, `COLLECTION_NAME`
- 임베딩: `EMBEDDING_PROVIDER`, `VOYAGE_MODEL`, `GEMINI_EMBED_MODEL`, `EMBEDDING_DIM`
- 배치/제한: `RATE_LIMIT_RPM`, `MAX_CHARS_PER_REQUEST`, `MAX_ITEMS_PER_REQUEST`, `MAX_DOCS_TO_EMBED`
- 그룹핑: `PARENT_MODE`, `PAGE_REGEX`, `SECTION_REGEX`
- 스키마/확장/보조: `CUSTOM_SCHEMA_WRITE`, `ENABLE_AUTO_OCR`

---
본 문서는 `embedding.py`의 실제 코드 흐름을 기준으로 작성되었으며, 환경 설정에 따라 일부 단계가 생략되거나(예: 커스텀 스키마/DB 튜닝) 분기가 달라질 수 있습니다.

