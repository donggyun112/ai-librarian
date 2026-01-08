# embedding.py 실행 시 호출 시나리오

## 1. 진입점
1. `embedding.main()` (`embedding.py:7`)
   - CLI 인자(파일 글롭 패턴)를 읽고 환경 설정 로더 및 파이프라인을 준비.
2. `load_config()` (`embedding/config.py:37`)
   - `.env` 값을 읽어 `EmbeddingConfig` dataclass 인스턴스를 생성.
3. `EmbeddingPipeline(config)` 생성자 (`embedding/pipeline.py:97`)
   - 파이프라인에서 사용할 전처리기, 파서, 저장소 매니저, 리포지토리 등 구성요소를 초기화.
4. `EmbeddingPipeline.run(pattern)` (`embedding/pipeline.py:119`)
   - 본격적인 임베딩 생성 및 저장 워크플로를 실행.

## 2. 파이프라인 초기 작업
5. `EmbeddingProviderFactory.create(config)` (`embedding/embeddings_provider.py:44`)
   - 설정에 맞춰 VoyageAI 임베딩 또는 Gemini 임베딩 클라이언트를 생성.
6. `validate_embedding_dimension(embeddings, config.embedding_dim)` (`embedding/embeddings_provider.py:60`)
   - 샘플 텍스트를 임베딩해 벡터 차원이 기대값과 일치하는지 확인.
7. `DbSchemaManager.apply_db_level_tuning()` (`embedding/storage.py:27`)
   - 환경 변수 기반으로 PostgreSQL 검색 파라미터(ivfflat, hnsw 등)를 설정.
8. `_create_vector_store(embeddings)` (`embedding/pipeline.py:207`)
   - `PGVector` 인스턴스를 만들어 LangChain VectorStore 연결을 확보.
9. `InputCollector.collect(pattern)` (`embedding/pipeline.py:26`)
   - 글롭 패턴으로 입력 파일 목록을 수집.
10. `DbSchemaManager.ensure_extension_vector()` (`embedding/storage.py:46`)
    - `vector` 확장이 설치되어 있는지 확인 및 설치.
11. `DbSchemaManager.ensure_parent_docstore()` (`embedding/storage.py:73`)
    - 부모 문서 저장 테이블(`docstore_parent`)과 관련 트리거/인덱스를 보장.
12. (선택) `DbSchemaManager.ensure_custom_schema(config.embedding_dim)` (`embedding/storage.py:107`)
    - 커스텀 스키마(`child_chunks`, `parent_docs`)와 인덱스, 트리거를 생성.

## 3. 파일별 처리 루프
각 파일에 대해 다음 순서가 실행됨:

13. `_parse_file(path)` (`embedding/pipeline.py:139`)
    - 확장자별로 텍스트 세그먼트 추출.
    - PDF: `PdfExtractor.extract()` → 텍스트 부족 시 자동 OCR 시도(`ocrmypdf` 호출 후 다시 읽기) → `OcrParser.parse_text()`.
    - Markdown: `MarkdownParser.parse(path)` → 펜스, 이미지 등 처리.
    - 기타 텍스트: `OcrParser.parse(path)` → 전처리/코드 감지 수행.
14. `SegmentUnitizer.unitize(segments)` (`embedding/parsers.py:171`)
    - Python/JavaScript 코드와 주변 텍스트를 묶어 unit 단위(`UnitizedSegment`)로 정리.
15. `DocumentBuilder.build(path, unitized)` (`embedding/pipeline.py:33`)
    - LangChain `Document`로 변환.
    - 텍스트: `RecursiveCharacterTextSplitter.split_text`.
    - 코드: `TextPreprocessor.split_code_safely`.
    - 이미지: alt/url 메타데이터 추가.
16. `ParentDocumentBuilder.augment_with_captions(documents)` (`embedding/parents.py:60`)
    - 텍스트 뷰에서 표/그림 캡션을 찾아 별도 `Document`로 추가.
17. `ParentDocumentBuilder.assign_parent_by_page_section(documents, path)` (`embedding/parents.py:32`)
    - 페이지/섹션 정규식 기반으로 `parent_id`, `page`, `section` 메타데이터 설정.
18. `ParentDocumentBuilder.build_parent_entries(documents)` (`embedding/parents.py:20`)
    - 동일 unitId를 공유하는 문서를 모아 부모 문서 콘텐츠를 합성.
19. `ParentChildRepository.upsert_parents(parents)` (`embedding/storage.py:273`)
    - 부모 문서를 `docstore_parent`에 업서트.
20. (선택) `ParentChildRepository.dual_write_custom_schema(...)` (`embedding/storage.py:315`)
    - 커스텀 스키마 사용 시 `parent_docs`와 `child_chunks`에 부모/자식 문서를 동시에 저장.
21. `VectorStoreWriter.upsert_batch(store, docs_to_write)` (`embedding/storage.py:213`)
    - 중복 콘텐츠 해시 제거(`compute_doc_id` 호출) 후 레이트리밋 기준으로 배치 업로드.
    - 내부에서 `iter_by_char_budget` (`embedding/parsers.py:234`)로 배치 묶음 생성.

## 4. 루프 종료 후 마무리
22. `DbSchemaManager.ensure_indexes()` (`embedding/storage.py:54`)
    - PGVector 테이블에 HNSW/GIN/BTREE 인덱스를 보장.
23. 파이프라인 종료: 총 문서 수와 부모 문서 수를 출력하고 `[ok] all set` 로그로 마무리.

## 5. 호출 순서와 역할 요약
- **환경 준비**: `load_config` → `EmbeddingPipeline` 생성 → 임베딩 클라이언트 생성/검증 → DB 튜닝 및 VectorStore 준비.
- **스키마 보장**: `ensure_extension_vector`, `ensure_parent_docstore`, `ensure_custom_schema`.
- **파일 처리**: `_parse_file` → `SegmentUnitizer` → `DocumentBuilder` → `ParentDocumentBuilder` → 저장소 업서트 → VectorStore 업서트.
- **정리**: 인덱스 보장 및 최종 로그 출력.

위 순서는 `embedding.py` 실행 시 자동으로 이어지며, 각 단계는 설정된 옵션(예: `CUSTOM_SCHEMA_WRITE`, `ENABLE_AUTO_OCR`, `MAX_DOCS_TO_EMBED`)에 따라 일부 분기/건너뛰기를 수행한다.
