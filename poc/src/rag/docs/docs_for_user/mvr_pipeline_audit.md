# MVR 파이프라인 감리 보고서

## 실행 전제/맥락
- 데이터: OCR된 학습서(텍스트/코드/그림 캡션 혼합)
- 설계 의도: 자식(views: text/code/ocr)은 벡터스토어에 임베딩 저장, 부모 문서는 Postgres DocStore에 `parent_id`로 집계/복원
- 근거: embedding.py, retriever_multi_view_demo.py, tools/*.py 및 스키마/체크리스트 문서 일치 여부 점검(테스트 없이 정적 검토)

## 결론
- 자식 청크 임베딩 → parent_id 집계 → 부모 DocStore 조회 흐름은 코드만으로 보아 설계 의도에 맞게 구현되어 있음.
  - LangChain `PGVector`에 자식(view=text/code) 임베딩 저장
  - `docstore_parent`에 parent_id별 부모 요약 저장(멱등 upsert)
  - `MultiVectorRetriever(id_key='parent_id')`로 벡터 히트를 parent_id로 묶고, Postgres DocStore에서 부모 본문을 조회

## 구현 확인(코드 기준)
- 자식 임베딩
  - 생성: `build_document_from_unitized()` → `Document(page_content, metadata)`에 `view`(text|code), `lang`, `order`, `source`, `unit_id/parent_id` 부여
  - parent_id 부여: 기본 `unit` 모드에서는 `unit_id=parent_id`; `assign_parent_by_page_section()`가 `PAGE_REGEX`/`SECTION_REGEX`로 재지정 지원
  - 저장: `upsert_batch()`가 `PGVector.add_documents(...)` 호출. `content_hash` 기반 결정적 ID(`doc:<hash>`) 전달(미지원 버전은 fallback)
  - 인덱스: `ensure_indexes()` → HNSW(cosine), JSONB GIN(cmetadata), BTREE(view/lang/parent_id 등)
- 부모 집계/저장
  - 집계: `build_parent_entries()`가 `parent_id`별로 자식 묶어 ~2KB 요약(`synthesize_parent_content()`)
  - 저장: `upsert_parents()` → `docstore_parent(id, content, metadata)` 멱등 upsert
  - 커스텀 스키마(옵션): `ensure_custom_schema()`로 `child_chunks`/`parent_docs` 생성(+유니크 인덱스), `dual_write_custom_schema()`로 트랜잭션 이중쓰기
- 부모 DocStore 조회
  - 어댑터: `PostgresByteStore`로 `docstore_parent`를 ByteStore(id→bytes)로 제공(`mget`)
  - 리트리버: `MultiVectorRetriever(vectorstore=PGVector, docstore=PostgresByteStore, id_key='parent_id')`, view/lang 필터 지원

## 즉시 고쳐야 할 오류/리스크(우선순위)
1) 고아 청크(parent_id 없음) 발생 가능
- 원인: `unitize_txt_py_js_streaming(..., attach_post_text=False)` 기본값으로 JS 블록 이후 텍스트가 같은 unit에 붙지 않음 → parent_id 비어 있는 청크가 생길 수 있음
- 영향: 검색 히트가 부모 DocStore에서 복원되지 않아 품질 저하/누락
- 제안: 기본값을 `attach_post_text=True`로 변경하거나, 청크 생성 후 parent_id 없는 문서를 제외/재부여. 최소한 벡터 삽입 전 필터링

2) 벡터스토어 중복 삽입 가능성(버전 의존)
- 현황: `ids=` 전달하나, `langchain_postgres` 버전에 따라 미지원 시 fallback으로 ID 없이 삽입 → 재실행 중복 위험
- 제안: 사용 버전에서 `ids` 지원 여부 확인. 미지원 시 `content_hash` 기반 선삭제/중복 방지 로직 추가

3) 임베딩 차원 불일치 시 런타임 오류 위험
- 현황: `validate_embedding_dimension()`가 경고만 출력. `EMBEDDING_DIM` ≠ 모델 출력 차원일 때 삽입 시점 오류 가능
- 제안: 경고가 아닌 강제 실패(Assert) 또는 `embedding_length`를 모델 실제 차원으로 동기화 후 진행(로그 알림)

4) 트랜잭션 일관성 불완전
- 현황: 커스텀 스키마(`parent_docs`/`child_chunks`)는 트랜잭션 처리되지만 `langchain_pg_embedding` 쓰기는 별개(LangChain 경유)
- 영향: 일부 실패 시 벡터스토어와 DocStore 간 불일치 가능
- 제안: 파일 단위 보상처리(재시도/정리) 또는 적재 완료 후 정합성 점검 루틴 추가

5) 페이지/섹션 정규식 기본값 신뢰성
- 현황: 기본 `PAGE_REGEX`/`SECTION_REGEX` 문자열에 비ASCII 기호가 포함된 흔적. 데이터셋에 따라 오탐/미탐 가능
- 제안: 실제 데이터셋 기준으로 환경변수에 명시 설정. 기본값은 더 단순/안전한 패턴으로 조정 권장

6) 인덱스 스코프 관리
- 현황: `ensure_indexes()`가 공용 테이블 `langchain_pg_embedding`에 인덱스 생성. 컬렉션 증가 시 과다/중복 가능
- 제안: 운영 시 컬렉션 분리(스키마/테이블 분리) 또는 인덱스 설계를 단일화/공용화 전략으로 조정

## 참고(양호한 점)
- DocStore 경로: `docstore_parent` 멱등 upsert, `PostgresByteStore.mget`로 UTF-8 bytes 반환, MVR와 인터페이스 일치
- 커스텀 스키마: `child_chunks`에 `content_hash` 유니크 인덱스 + `ON CONFLICT DO NOTHING` 멱등, `parent_docs` upsert 멱등
- 인덱싱: 벡터(HNSW, cosine) + JSONB GIN + BTREE 보조 인덱스 구성 적절
- 성능 파라미터: `IVFFLAT_PROBES`/`HNSW_*` 환경변수로 DB 레벨 기본값 설정 시도(권한 없으면 경고)

