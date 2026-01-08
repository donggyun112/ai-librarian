# Issue: PGVector 기반 다중 헤딩 임베딩 파이프라인 정리

## 1. 최종 목표
- 텍스트·코드·이미지 캡션 등 다양한 문서 자산을 임베딩해 PostgreSQL + PGVector에 저장하고, 다중 뷰 기반 RAG 검색에 활용 가능한 인덱스를 구축한다.
- 결과적으로, LangChain 기반 검색·생성 파이프라인에서 빠른 주제 탐색과 근거 기반 답변을 동시에 제공할 수 있는 벡터 데이터셋을 확보한다.

## 2. 다중 헤딩(Multi-Heading) 방식 채택 배경
- 단일 헤딩 구조에서는 문서 전체가 동일한 우선순위로 취급돼 요약 수준 검색과 세부 근거 탐색을 동시에 만족시키기 어렵다.
- 기술 매뉴얼·코드·OCR 혼합 데이터셋에서는 페이지/섹션/코드 블록 단위의 문맥을 유지해야 오류 없는 RAG 응답을 만들 수 있다.
- 부모 요약 + 자식 상세 조각의 계층을 유지하면 빠른 주제 탐색과 근거 추적이 모두 가능해지며, 멀티 뷰 검색(텍스트, 코드, 캡션)을 확장하기 용이하다.

## 3. 핵심 문제 정의
- 입력 파일 포맷(PDF, Markdown, 코드 스니펫 등)이 다양하여 일관된 전처리 및 세분화 전략이 필요하다.
- 임베딩 모델(VoyageAI, Gemini 등)과 차원 설정이 혼재돼 있어 환경 구성 및 검증 절차를 명시적으로 관리해야 한다.
- RAG 품질을 높이려면 부모(요약)·자식(세부) 문서 계층을 동시에 구성해 멀티 레벨 검색을 가능하게 해야 한다.

## 4. 변경된 구조 개요
- `embedding/models.py`: `EmbeddingConfig`, `RawSegment`, `UnitizedSegment`, `ParentDocument` 등 파이프라인 전역에서 쓰이는 dataclass 정의.
- `embedding/config.py`: `.env`를 로드해 `EmbeddingConfig`를 생성하고, 정수/불리언 파싱 유틸을 제공.
- `embedding/text_utils.py`: `TextPreprocessor`가 정규화, 코드 블록 감지, 언어 추정, 코드 분할 로직을 담당.
- `embedding/parsers.py`: `OcrParser`, `MarkdownParser`, `PdfExtractor`, `SegmentUnitizer`, `iter_by_char_budget` 등 입력 파싱 및 단위화 책임.
- `embedding/embeddings_provider.py`: `EmbeddingProviderFactory`가 VoyageAI/Gemini를 선택하고, `validate_embedding_dimension`으로 차원 검증.
- `embedding/storage.py`: `DbSchemaManager`, `VectorStoreWriter`, `ParentChildRepository`로 DB 스키마 보장 및 업서트 로직을 캡슐화.
- `embedding/parents.py`: `ParentDocumentBuilder`가 parent_id 할당, 캡션 증강, 부모 콘텐츠 합성을 수행.
- `embedding/pipeline.py`: `EmbeddingPipeline`, `DocumentBuilder`, `InputCollector`가 전체 오케스트레이션과 LangChain 문서 생성을 담당.
- `embedding/utils.py`: 콘텐츠 해시(`HashingService`), 슬러그 변환(`Slugifier`) 유틸리티.
- `embedding.py`: CLI 진입점으로 `load_config`와 `EmbeddingPipeline.run`을 연결하는 파사드.

## 5. 임베딩 파이프라인 요약 (5단계)
1. **환경 초기화 & 설정 로딩**  
   - `.env`에서 모델명, 임베딩 차원, PG 연결 문자열 등을 읽어 `EmbeddingConfig`에 주입.  
   - 예: `VOYAGE_MODEL=voyage-3`, `EMBEDDING_DIM=1024`, `PG_CONN=postgresql://…`.

2. **임베딩 모델 준비 및 검증**  
   - `EmbeddingProviderFactory.create(config)`로 VoyageAI/Gemini 클라이언트 생성.  
   - 샘플 텍스트 임베딩을 통해 실제 벡터 차원이 설정값과 일치하는지 확인(차원 불일치 시 조기 경고).

3. **입력 파일 파싱 & 세그먼트화**  
   - PDF, Markdown, 순수 텍스트 각각에 맞는 파서 적용. 필요 시 OCR 수행.  
   - 코드 블록과 주변 텍스트를 `SegmentUnitizer`로 묶어 문맥 단위 세그먼트를 생성.

4. **LangChain Document 변환 & Parent/Child 구성**  
   - `DocumentBuilder`가 세그먼트를 LangChain `Document`로 변환하고 메타데이터(뷰, 언어, order 등) 추가.  
   - `ParentDocumentBuilder`가 페이지/섹션 기반 parent_id를 부여하고, 부모 문서 요약과 캡션 보강을 수행.

5. **임베딩 생성 & PGVector 업서트**  
   - `VectorStoreWriter.upsert_batch()`가 레이트리밋을 고려해 배치 임베딩 및 업서트 실행.  
   - `compute_doc_id`로 중복 벡터를 제거하고, 처리 후 `ensure_indexes()`로 HNSW/GIN/BTREE 인덱스를 보강.

## 6. 단일 헤딩 vs 다중 헤딩 아키텍처 비교

| 구분 | 단일 헤딩 (Single-Heading) | 다중 헤딩 (Multi-Heading) |
| --- | --- | --- |
| 구조 | 모든 문서 조각이 단일 테이블에 평면 저장 | 부모(Parent)·자식(Child) 문서로 계층 구성 |
| 메타데이터 | 공통 필드만 존재 (예: title, source) | parent_id, section, page, caption 등 다층 메타데이터 |
| 검색 방식 | 단일 레벨 임베딩 검색 → 요약·세부 구분 어려움 | 부모에서 빠른 주제 탐색 후 자식에서 상세 근거 확보 |
| 활용 사례 | FAQ, 간단한 텍스트 검색 | 기술 문서, 코드 베이스, 복잡한 매뉴얼 RAG |

- `embedding.py` 파이프라인은 **다중 헤딩(Multi-Heading)** 전략을 구현한다.  
  - `ParentDocumentBuilder.assign_parent_by_page_section()`에서 parent_id·page·section 메타데이터 부여.  
  - `build_parent_entries()`로 동일 unitId 문서를 묶어 부모 요약 생성.  
  - `ParentChildRepository`가 `parent_docs` / `child_chunks`에 각각 업서트하여 계층 구조를 확립.

## 7. 기대 효과 및 향후 질문
- **기대 효과**: 멀티 레벨 검색, 요약/근거 동시 제공, 대규모 문서의 문맥 유지.  
- **남은 질문**:
  1. 멀티 헤딩 구조에서 추가적으로 필요한 인덱스나 메타데이터는 무엇인가?
  2. OCR 정확도가 낮은 PDF에 대한 보정 전략(예: 재시도, 사용자 피드백)이 필요한가?
  3. Gemini/VoyageAI 선택 기준(비용, 품질)을 어떻게 명문화할 것인가?

---

이 이슈에서는 위 목표/단계를 토대로 파이프라인 구축 현황을 공유하고, 남은 결정을 논의하는 것을 제안합니다. 필요 시 체크리스트나 작업 항목을 추가로 정리해 후속 PR 계획을 세울 수 있습니다.
