# 시멘틱 서치 정확도 향상 방안 보고서

## 1. 배경 요약
- 현재 임베딩 파이프라인은 `embedding.py` → `EmbeddingPipeline.run()` 흐름으로 구성되어 있으며, 설정 로딩(`embedding/config.py:37`), 임베딩 프로바이더 생성(`embedding/embeddings_provider.py:44`), 벡터 스토어 초기화(`embedding/pipeline.py:207`), 입력 파일 수집 및 파싱(`embedding/pipeline.py:26`, `embedding/parsers.py:171`), Parent/Child 문서 구축(`embedding/parents.py:20`)을 거쳐 PGVector에 저장합니다. (참조: `embedding_call_flow.md`)
- 멀티 헤딩 구조(Parent/Child)로 문서를 계층화하고, PGVector 인덱스를 `DbSchemaManager.ensure_indexes()`로 보강하여 RAG 시 빠른 근거 탐색을 지원합니다. (참조: `embedding_summary.md`)
- VoyageAI·Gemini 임베딩을 환경 변수로 선택하며, `validate_embedding_dimension()`로 차원 정합성을 검증합니다. (참조: `embedding/embeddings_provider.py:60`)

## 2. 개선 제안 요약
- 데이터 전처리 품질을 높여 노이즈를 줄이고, 문맥 단위 세분화 전략을 고도화합니다.
- 임베딩 모델·하이퍼파라미터를 실증적으로 비교하고 상황에 따라 혼합 전략을 적용합니다.
- 부모/자식 문서 메타데이터와 벡터 인덱스 파라미터를 튜닝해 검색 랭킹의 일관성을 강화합니다.
- 쿼리 후처리(재랭킹, 쿼리 확장)와 온라인/오프라인 평가 체계를 도입해 지속적으로 정확도를 모니터링합니다.

## 3. 세부 개선안

### 3.1 데이터 전처리 및 세분화 고도화
- **OCR 품질 진단 루프 추가**: `PdfExtractor.extract()`와 `OcrParser.parse_text()` 단계에서 OCR 품질 스코어(예: confidence 평균)를 수집하고, 임계치 이하일 때 재시도 파라미터(언어 힌트, DPI 업스케일)를 조정해 입력 노이즈를 감소시킵니다.
- **문서 타입별 동적 청킹**: `DocumentBuilder`가 사용하는 `RecursiveCharacterTextSplitter` 기본 규칙을 문서 타입별로 분기하여, PDF는 헤딩 간격 기반, 코드 파일은 함수/클래스 블록 기반으로 chunk 크기를 자동 조절합니다. (`embedding/pipeline.py:33`)
- **Context 확장 메타데이터 보강**: `ParentDocumentBuilder.assign_parent_by_page_section()`에 상위 헤딩 계층, 문서 버전, 태그 정보를 추가 보관하여 검색 시 필터/부스팅에 활용합니다. (`embedding/parents.py:32`)
- **중복 컨텐츠 정규화**: `compute_doc_id` 해시 입력에 전처리된 텍스트 외에도 정규화된 경로/헤딩을 포함해, 동일 내용이 다른 경로로 유입될 때 중복을 더욱 확실히 제거합니다. (`embedding/storage.py:213`)

### 3.2 임베딩 모델 및 하이퍼파라미터 전략
- **모델 AB 테스트**: `EmbeddingProviderFactory.create()`에서 지원하는 VoyageAI·Gemini 모델을 쿼리/문서 샘플셋으로 교차 비교하여, 문서 타입별 최적 조합(예: OCR 텍스트는 VoyageAI, 코드 스니펫은 Gemini)을 찾고 Hybrid 저장 또는 다중 인덱스 운영을 검토합니다. (`embedding/embeddings_provider.py:44`)
- **차원/정규화 모니터링**: `validate_embedding_dimension()` 결과를 로그에 남기고, 임베딩 값 분포(노름, 평균)를 주기적으로 점검하여 모델 업데이트 시 스케일 변화로 인한 거리 왜곡을 사전에 인지합니다. (`embedding/embeddings_provider.py:60`)
- **쿼리/문서 임베딩 분리 전략**: 문서 임베딩은 기존 모델을 유지하되, 질의 임베딩에 대해 질의 특성화 모델(예: instruction-tuned)로 변환해 의미적 매칭을 강화하는 Dual Encoder 구성을 도입합니다.

### 3.3 Vector Store 및 인덱스 튜닝
- **HNSW/IVFFLAT 파라미터 최적화**: `DbSchemaManager.apply_db_level_tuning()`과 `ensure_indexes()`에서 설정하는 `lists`, `probes`, `ef_search` 값을 문서량과 응답 지연에 맞춰 튜닝하고, 검색 로그 기반으로 성능-정확도 곡선을 구축합니다. (`embedding/storage.py:27`, `embedding/storage.py:54`)
- **커스텀 스키마 활용 극대화**: `ensure_custom_schema()`와 `dual_write_custom_schema()` 사용을 기본 활성화하여(`CUSTOM_SCHEMA_WRITE=true`), Parent/Child 테이블에 별도 인덱스를 두고 부모-자식 조인 비용을 최소화합니다. (`embedding/storage.py:107`, `embedding/storage.py:315`)
- **메타데이터 기반 필터링**: Parent 문서에 저장된 `page`, `section`, 문서 타입을 인덱스 컬럼으로 추가하고, 질의 시 후보 집합을 줄인 뒤 벡터 검색을 수행하는 하이브리드(필터 + 벡터) 전략을 적용합니다.

### 3.4 검색 후처리 및 랭킹 강화
- **Cross-Encoder 재랭커 도입**: 벡터 검색 Top-K 결과를 소수(K=20 내외)로 줄인 후, 사전 학습된 Cross-Encoder(예: `cross-encoder/ms-marco-MiniLM-L-6-v2`)로 재평가하여 상위 문서를 재정렬합니다. 이를 LangChain 체인에 후단 처리로 붙여 재현율·정밀도를 동시에 개선합니다.
- **쿼리 확장·리라이팅**: 사용자 질의를 `TextPreprocessor`와 유사한 토큰 정규화 후, 도메인별 동의어 사전이나 LLM 기반 의도 파악으로 보강해, 의미가 드러나지 않는 키워드 문서를 더 잘 매칭합니다. (`embedding/text_utils.py`)
- **Parent-Child 일관성 스코어링**: Parent 요약(부모 문서)과 Child 조각의 유사도를 쿼리와 함께 고려해, 상위 부모가 선택되면 관련 자식 조각을 우선 제공하는 계층적 랭킹 규칙을 도입합니다. (`embedding/parents.py:20`)

### 3.5 평가 및 모니터링 체계
- **골든셋 기반 Offline 평가**: 대표 질의-답변 쌍을 수집하여 NDCG, Recall@K 지표를 계산하고, 모델/파라미터 변경 시 회귀 테스트로 활용합니다.
- **Online 피드백 루프**: 검색 사용 로그에 대한 클릭/조회/유효성 피드백을 `docstore_parent`와 연결 저장하여, 재랭커 학습 데이터로 전환하거나 비효율 chunk를 재분할하는 자동 트리거를 만들 수 있습니다. (`embedding/storage.py:273`)
- **경보 및 대시보드화**: 임베딩 성공률, OCR 리트라이율, HNSW 검색 지연 등 핵심 지표를 모니터링해 정확도 저하 신호를 조기에 발견합니다.

## 4. 우선순위 제안
1. 문서 타입별 청킹 고도화 및 Parent 메타데이터 확장으로 바로 체감되는 검색 품질 개선.
2. 임베딩 모델 AB 테스트와 Cross-Encoder 재랭킹으로 Top-K 정확도 상승.
3. HNSW/IVFFLAT 파라미터 튜닝 및 커스텀 스키마 활성화로 응답 지연과 정확도를 균형 있게 맞춤.
4. 골든셋 구축과 모니터링 자동화를 통해 향후 변경 사항의 품질 보증 체계 마련.

---
본 보고서는 `embedding_call_flow.md`, `embedding_summary.md`에서 정리된 현재 구조를 토대로 작성되었으며, 각 개선안은 모듈별 책임 경계를 유지한 채 적용할 수 있도록 구성했습니다.
