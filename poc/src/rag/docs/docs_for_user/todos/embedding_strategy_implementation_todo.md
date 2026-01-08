# Embedding Strategy Implementation To-Do

## 환경 및 사전 준비
- [ ] `.env` 업데이트: `PG_CONN`, `COLLECTION_NAME`, `VOYAGE_MODEL`, `EMBEDDING_DIM`, `CUSTOM_SCHEMA_WRITE`, `IVFFLAT_PROBES`, `HNSW_EF_SEARCH`, `HNSW_EF_CONSTRUCTION` 기본값 검토 및 반영.
- [ ] DB 권한 점검: `ALTER DATABASE ... SET` 명령 실행 권한 확인 및 필요 시 DBA 협의.

## 스키마 및 멱등성 확보
- [ ] `child_chunks` 테이블에 `content_hash` 컬럼 존재 여부 확인 후 미존재 시 추가.
- [ ] `child_chunks` 테이블에 `(parent_id, view, lang, content_hash)` 유니크 인덱스 생성.
- [ ] `parent_docs`·`child_chunks` dual write를 기본 활성화하도록 `ensure_custom_schema()` 및 `dual_write_custom_schema()` 흐름 점검.

## `embedding.py` 개선 작업
- [ ] `validate_embedding_dimension()` 호출 결과를 활용해 벡터 길이 불일치 시 경고 및 스택/모델 정보 출력.
- [ ] `EmbeddingPipeline`에서 문서 해시 기반 ID(`compute_doc_id`)를 활용해 `PGVector.add_documents(ids=...)`로 멱등 업서트 구현.
- [ ] 커스텀 스키마 경로에서도 동일한 ID/해시가 사용되도록 `vector_store_writer` 로직 확인 및 수정.
- [ ] 배치 업서트 시 트랜잭션 범위가 parent/child 모두를 포함하도록 커밋 단위 검토.
- [ ] 파이프라인 종료 시 parent, child, chunk 처리 건수를 요약 로그로 출력.

## DB 레벨 ANN 튜닝
- [ ] `DbSchemaManager.apply_db_level_tuning()`에서 `IVFFLAT_PROBES`, `HNSW_EF_SEARCH`, `HNSW_EF_CONSTRUCTION` 값을 적용하고 실패 시 경고만 남기도록 구현.
- [ ] 해당 파라미터 적용 결과를 로그로 남겨 추적 가능하도록 구성.

## OCR 및 텍스트 전처리
- [ ] `NORMALIZE_MAP`을 활용한 문자 치환이 `OcrParser` 경로에 반영되었는지 확인하고 누락 시 적용.
- [ ] OCR 실패/재시도 시 경고와 함께 후속 조치(리트라이, 스킵 등) 로직 검토.

## 리트리버 스크립트 보완
- [ ] `retriever_multi_view_demo.py`에서 DB 레벨 ANN 파라미터 적용 여부를 진단/출력하는 도우미 추가.
- [ ] 조회 경로에서 `view`, `lang`별 필터링과 커스텀 스키마 사용 시 동작 확인.

## 검증 및 문서화
- [ ] 변경 후 `python embedding.py "test/*.txt"` 등 샘플 실행으로 멱등성 및 로그 출력 확인.
- [ ] `python retriever_multi_view_demo.py "<query>" [view] [lang]` 재현 테스트 수행.
- [ ] 구현 사항을 `docs/embedding_strategy_checklist.md` 또는 신규 문서에 기록.
