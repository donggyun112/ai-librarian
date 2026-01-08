# embedding.py 리팩터링 보고서

## 1. 배경과 목표
- 기존 `embedding.py`는 텍스트 전처리, 파싱, 임베딩 공급자 선택, DB 스키마 관리, 파이프라인 제어 등 다양한 책임을 단일 파일에서 수행하여 유지보수와 테스트가 어려웠음.
- `embedding_refactor_todo.md`에서 정의한 객체지향적 분리 계획을 기반으로, 책임 단위별 클래스를 도입하고 패키지 구조를 재구성하는 것이 목적이었음.
- 리팩터링 범위는 기능 동등성을 유지하면서 모듈화와 의존성 주입을 강화하는 데 집중함.

## 2. 최종 패키지 구조 개요
| 경로 | 주요 역할 |
| --- | --- |
| `embedding/models.py` | 공용 데이터 모델(`EmbeddingConfig`, `RawSegment`, `UnitizedSegment`, `ParentDocument`) |
| `embedding/config.py` | `.env` 기반 설정 로더(`load_config`) |
| `embedding/text_utils.py` | `TextPreprocessor`로 전처리·코드 감지 로직 캡슐화 |
| `embedding/parsers.py` | OCR/Markdown 파서, PDF 추출기, `SegmentUnitizer`, 배치 유틸 |
| `embedding/embeddings_provider.py` | 임베딩 공급자 팩토리, Gemini 어댑터, 차원 검증 |
| `embedding/storage.py` | DB 스키마 보장(`DbSchemaManager`), 벡터 업서트(`VectorStoreWriter`), 부모/자식 저장소(`ParentChildRepository`) |
| `embedding/parents.py` | `ParentDocumentBuilder`로 부모 문서 합성·메타데이터 정리 |
| `embedding/pipeline.py` | `EmbeddingPipeline` 및 보조 헬퍼(`DocumentBuilder`, `InputCollector`) |
| `embedding/utils.py` | 콘텐츠 해시 및 슬러그 유틸 |
| `embedding/__init__.py` | 패키지 퍼블릭 API(`EmbeddingPipeline`, `load_config`) |
| `embedding.py` | 얇은 CLI 파사드 (`load_config` → `EmbeddingPipeline.run`) |

## 3. 주요 모듈별 책임 정리
- **설정 로딩 (`embedding/config.py`)**
  - `.env` 로드 후 `EmbeddingConfig` dataclass 인스턴스 생성.
  - 정수/불리언 파싱 유틸을 도입해 환경 변수를 안전하게 처리.
- **텍스트 전처리 (`embedding/text_utils.py`)**
  - `normalize`, `is_code_block`, `guess_code_lang`, `split_code_safely` 등을 `TextPreprocessor` 클래스로 통합.
  - 정규식/기호 기반 코드 감지를 재사용 가능하도록 제공.
- **세그먼트 파서 (`embedding/parsers.py`)**
  - `OcrParser`, `MarkdownParser`, `PdfExtractor`, `SegmentUnitizer`로 책임 분리.
  - Markdown 이미지·코드 펜스 처리와 파라그래프 단위 분할을 클래스 메서드로 캡슐화.
  - `_iter_by_char_budget`는 `iter_by_char_budget`로 이름 변경되어 저장소 레이어에서 재활용.
- **임베딩 공급자 (`embedding/embeddings_provider.py`)**
  - `EmbeddingProviderFactory`가 설정 기반으로 VoyageAI/Gemini 선택.
  - Gemini API 호출 어댑터(`GeminiEmbeddings`)와 차원 검증 함수 제공.
- **DB/스토리지 (`embedding/storage.py`)**
  - `DbSchemaManager`: 확장, 인덱스, 커스텀 스키마, DB-level 튜닝 관리.
  - `VectorStoreWriter`: 레이트리밋/배치 전략을 적용해 PGVector에 안전 업서트.
  - `ParentChildRepository`: 부모/자식 문서 upsert 및 커스텀 스키마 dual-write 처리.
- **부모 문서 빌더 (`embedding/parents.py`)**
  - `ParentDocumentBuilder`가 페이지/섹션 기반 parent_id, 캡션 증강, 요약 콘텐츠를 담당.
  - 슬러그 변환과 코드 감지 정규식 활용으로 중복 로직 제거.
- **파이프라인 오케스트레이션 (`embedding/pipeline.py`)**
  - `EmbeddingPipeline.run`이 구성 객체를 생성하고 파일 수집 → 파싱 → 문서화 → 부모 생성 → 벡터 업서트 → 인덱스 생성의 전체 플로우를 관리.
  - `DocumentBuilder`가 `UnitizedSegment`를 LangChain `Document`로 변환하며, 이미지/코드/텍스트 뷰를 각각 처리.
- **유틸/파사드**
  - `embedding/utils.py`에서 콘텐츠 해시 계산을 재사용.
  - 루트 `embedding.py`는 CLI 진입점으로, 기존 `main` 로직을 새 파이프라인으로 위임.

## 4. 단계별 진행 사항
1. **사전 분석**: 기존 `embedding.py`에서 함수별 책임을 분류하고, TODO 문서와 매핑.
2. **모델·설정 정리**: 공통 dataclass 정의 및 설정 로더 분리로 전역 변수 제거.
3. **전처리/파서 모듈화**: 텍스트/코드 분리, Markdown/OCR/PDF 처리를 각각 클래스화.
4. **스토리지·임베딩 레이어 구축**: 팩토리, DB 스키마 매니저, 벡터 업서트 클래스를 도입.
5. **파이프라인 재구성**: `EmbeddingPipeline`으로 주 흐름을 캡슐화하고 `embedding.py`는 파사드로 축소.
6. **검증**: `python -c "import embedding; import embedding.pipeline; print('ok')"`로 모듈 임포트 확인.

## 5. 행동 동등성 보존 전략
- 기존 함수 로직을 새로운 클래스 메서드로 옮기되, 인자/리턴 값과 로그 메시지를 최대한 유지.
- `SegmentUnitizer`, `ParentDocumentBuilder`, `VectorStoreWriter` 등 주요 로직은 원래 구현을 그대로 이동하며 약간의 리팩터링(네이밍, 타입 추가)만 수행.
- `EmbeddingPipeline`에서 파일 처리 순서와 조건(캡션 증강, parent assign, custom schema dual write, rate limit 옵션 등)을 기존 흐름과 동일하게 유지.

## 6. 리스크 및 추후 작업
- **테스트**: 단위/통합 테스트가 아직 없으므로, 파서/스토리지/파이프라인 클래스를 대상으로 테스트 케이스를 추가하는 것이 필요.
- **오류 전파**: 일부 예외 처리 구간은 기존과 동일하게 `print` 경고 수준으로 남아 있음. 필요 시 로깅 시스템 도입 고려.
- **성능 확인**: 대규모 문서 처리에서 새 구조가 동일한 성능을 유지하는지 실제 데이터로 검증 필요.
- **문서화**: 개발 문서(`docs/`)에 새 패키지 구조 및 사용법을 반영해야 함.

## 7. 결론
- `embedding.py`가 담당하던 광범위한 책임을 9개 모듈로 재배치하여 가독성과 유지보수성을 향상시킴.
- 환경 설정, 파싱, 전처리, 임베딩, 스토리지, 파이프라인 제어가 각각 명확한 클래스로 구분되어 의존성 주입과 테스트 준비가 쉬워짐.
- 현재 CLI는 기존과 동일한 인터페이스를 제공하므로, 새 구조로 전환한 뒤에도 기존 스크립트/배포 파이프라인에서 추가 수정 없이 사용 가능함.
