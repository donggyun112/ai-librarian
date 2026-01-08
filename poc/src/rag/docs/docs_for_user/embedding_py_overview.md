# embedding.py 역할 정리

## 전체 흐름
- .env 값을 읽어 임베딩 모델, Postgres 접속 정보, 배치 크기 등 실행 파라미터를 구성합니다.
- main()이 입력 글로브에 맞는 파일을 순회하며 텍스트 추출 → 세그먼트화 → 문서화 → 임베딩 후 벡터DB에 저장하는 전체 파이프라인을 orchestration 합니다.
- 처리 과정에서 부족한 PDF 텍스트를 자동 OCR로 보강하고, 부모/자식 문서를 동시 관리해 MultiVectorRetriever 전략을 지원합니다.

## 입력 텍스트 전처리
- 
ormalize, split_paragraph, is_code_block, guess_code_lang으로 OCR 결과의 공백·합자·코드 블록을 정리하고 언어를 추정합니다.
- parse_ocr_text/parse_ocr_file은 일반 텍스트, parse_markdown_text/parse_markdown_file은 마크다운을 fence, 이미지, 페이지 브레이크에 맞춰 RawSegment 리스트로 분해합니다.
- extract_text_from_pdf와 is_low_text_density는 PDF에서 텍스트를 뽑거나 부족 시 OCR 경고를 제공합니다.
- ugment_with_captions는 벡터 검색 정확도를 높이기 위해 도표/그림 캡션을 별도 문서로 추가합니다.

## 코드·텍스트 유닛 구성
- RawSegment 데이터클래스는 세그먼트 종류(kind), 원본 콘텐츠, 언어, 순서를 추적합니다.
- unitize_txt_py_js_streaming은 텍스트/파이썬/자바스크립트 블록을 하나의 유닛으로 묶고, 전후 문맥(pre/post/bridge text) 메타데이터를 붙여 parent-child 전략에 최적화된 구조를 만듭니다.

## LangChain 문서 생성
- uild_document_from_unitized는 세그먼트 유닛을 langchain_core.documents.Document 객체로 변환하고, 텍스트는 RecursiveCharacterTextSplitter, 코드는 split_code_safely로 chunking 합니다.
- 문서 메타데이터에는 unit_id, parent_id, unit_role, lang, iew, 순번 등을 채우고, compute_doc_id_for가 parent/view/lang/내용 기반 해시로 중복을 제거합니다.

## 임베딩 공급자 추상화
- .env의 EMBEDDING_PROVIDER를 읽어 VoyageAI(VoyageAIEmbeddings) 또는 Google Gemini(_GeminiEmbeddings)를 선택하고, 필요 시 차원 검증(alidate_embedding_dimension)을 수행합니다.
- Gemini 사용 시 _GeminiEmbeddings가 google.generativeai SDK를 wrapping 하여 embed_documents/embed_query를 제공합니다.

## Postgres 및 PGVector 관리
- ensure_extension_vector, ensure_indexes가 pgvector 확장과 HNSW/GIN/BTREE 인덱스를 idempotent하게 생성합니다.
- pply_db_level_tuning은 환경 변수 기반으로 ivfflat.probes, hnsw.ef_search 등을 데이터베이스 레벨에서 조정합니다.
- ensure_parent_docstore, ensure_custom_schema, dual_write_custom_schema, upsert_child_chunks_custom은 parent_docs/child_chunks 커스텀 스키마를 만들고 동기화 writes를 수행합니다.
- upsert_batch는 PGVector 컬렉션에 배치 단위로 문서를 쓰고, 속도 제한 환경에서는 문자 수/요청 수 기반 batching과 지수 backoff 재시도를 적용합니다.

## Parent/Child 문서 관리
- ssign_parent_by_page_section이 페이지/섹션 정규식에 따라 parent_id를 재구성하여 검색 시 문맥 단위를 세분화합니다.
- uild_parent_entries와 synthesize_parent_content는 자식 chunk에서 대표 텍스트, 헤더, 캡션, 페이지 정보를 모아 요약 parent 문서를 생성합니다.
- upsert_parents/upsert_parents_custom가 docstore_parent 및 parent_docs 테이블에 parent 문서를 upsert합니다.

## 실행 진입점
- main(input_glob)은 파일 탐색, 스키마 보장, 세그먼트 파이프라인 실행, parent/child upsert, 인덱스 생성(ensure_indexes)까지 한 번에 수행하여 OCR/문서 세트를 벡터DB에 밀어넣는 CLI 엔트리 포인트입니다.
