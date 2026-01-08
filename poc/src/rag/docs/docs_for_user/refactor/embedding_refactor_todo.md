# embedding.py 리팩터링 TODO

## 사전 준비
- [ ] `embedding.py`의 주요 기능군(환경설정, 텍스트 전처리, 파서, 임베딩/DB 연동, 메인 플로우)을 다이어그램 또는 표로 정리한다.
- [ ] 현재 전역 상수 및 환경변수 의존성을 목록화하고, 기본값/사용 지점을 파악한다.
- [ ] 리팩터링 범위(기능 추가 없이 구조 개선)를 명확히 정의하고 관련자에게 공유한다.

## 모듈 구조 설계
- [ ] `embedding` 패키지 디렉터리를 만들고, 책임 단위별 하위 모듈 초안을 수립한다. 예) `config`, `text`, `parsers`, `embeddings`, `storage`, `pipeline`.
- [ ] 각 모듈의 public API(클래스/함수/데이터 모델)를 정의하고, 기존 코드에서 필요한 교차 참조를 명시한다.
- [ ] 새 구조에 맞는 타입/예외/로그 공통 유틸 위치를 결정한다.

## 클래스 도입 및 파일 분할

### 설정 및 컨텍스트
- [ ] 전역 상수를 `EmbeddingConfig` (dataclass)로 옮기고, 환경 변수 로딩 로직을 `config/loader.py`로 분리한다.
- [ ] `EmbeddingContext`(연결, 레이트리미트, 모델 정보 등)를 만들어 주요 컴포넌트가 의존성 주입으로 받도록 한다.

### 텍스트 전처리 & 코드 감지 (`text/`)
- [ ] `normalize`, `split_paragraph`, `is_code_block`, `guess_code_lang`, `split_code_safely`를 묶는 `TextPreprocessor` 클래스를 만든다.
- [ ] 코드 감지/언어 추정 정규식을 `text/patterns.py`와 같은 모듈로 이동하고, 테스트 가능한 메서드로 노출한다.
- [ ] 전처리 파이프라인 단계(정규화 → 패러그래프 분할 → 코드 분리)를 메서드 체이닝 또는 Strategy 패턴으로 정리한다.

### 문서 세그먼트 파서 (`parsers/`)
- [ ] OCR/PDF/Markdown 처리를 담당하는 클래스를 도입한다. 예) `OcrParser`, `MarkdownParser`, `PdfExtractor`.
- [ ] 각 파서가 공통 인터페이스(예: `BaseSegmentParser.parse(path|text) -> List[RawSegment]`)를 구현하도록 한다.
- [ ] `unitize_txt_py_js_streaming`을 `SegmentUnitizer` 클래스로 옮기고, 텍스트/코드 브릿징 옵션을 설정으로 받는다.

### 임베딩 공급자/모델 (`embeddings/`)
- [ ] `build_embeddings`, `validate_embedding_dimension`, 레이트리밋 상수들을 `EmbeddingProviderFactory`로 캡슐화한다.
- [ ] Provider별 전략 클래스를 분리(예: `VoyageEmbedding`, `GeminiEmbedding`)하고, 공통 인터페이스를 정의한다.
- [ ] 배치 생성 `_iter_by_char_budget`, 레이트리미트 적용 로직을 `EmbeddingBatcher` 또는 `RateLimitedEmbedder`로 이동한다.

### 벡터 스토리지 및 DB (`storage/`)
- [ ] `ensure_extension_vector`, `ensure_indexes`, `ensure_parent_docstore`, `ensure_custom_schema` 등을 `DbSchemaManager` 클래스로 분리한다.
- [ ] `upsert_batch`, `upsert_parents`, `dual_write_custom_schema` 등 쓰기 로직을 `VectorStoreWriter`와 `ParentChildRepository`로 나눈다.
- [ ] SQL/JSON 페이로드 생성을 별도 헬퍼(`storage/formatters.py`)로 떼어낸다.

### 부모/자식 문서 구성 (`pipeline/parents.py`)
- [ ] `build_parent_entries`, `assign_parent_by_page_section`, `synthesize_parent_content`, `augment_with_captions`를 `ParentDocumentBuilder` 클래스로 모은다.
- [ ] 캡션 증강, 페이지/섹션 레이블링을 옵션화하고 테스트 커버리지를 준비한다.

### 애플리케이션 오케스트레이션 (`pipeline/runner.py`)
- [ ] `main` 함수의 제어 흐름을 `EmbeddingPipeline` 클래스(초기화 → 파일 루프 → 파서 선택 → 파이프라인 실행)로 재구성한다.
- [ ] 파일 시스템 접근(glob, 확장자 스위치)을 `InputCollector` 유틸로 따로 빼서 단위 테스트 가능하게 한다.
- [ ] CLI(현재 `if __name__ == "__main__"`)를 얇게 유지하고, 새 파이프라인 클래스를 호출하도록 수정한다.

## 데이터 모델 정의
- [ ] `RawSegment`, 부모/자식 DTO 등을 `models.py`로 이동하거나 Pydantic/dataclass로 명료하게 정의한다.
- [ ] `Document.metadata`에서 사용되는 키와 의미를 문서화하고 상수화한다.

## 점진적 마이그레이션 전략
- [ ] 각 책임 단위별로 테스트(기존 통합 스크립트 + 신규 단위 테스트)를 준비해 리팩터링 전후 행동을 검증한다.
- [ ] 새 클래스 도입 시 기존 함수 호출부를 어댑터/래퍼로 감싸면서 단계적으로 치환한다.
- [ ] 리팩터링 중간 단계에서도 `embedding.py`가 동작하도록 import 경로를 관리하고, 마지막 단계에서 구식을 제거한다.

## 검증 및 문서화
- [ ] 새 구조에서의 실행/배포 방법을 README 또는 개발 문서에 추가한다.
- [ ] 주요 클래스를 대상으로 간단한 사용 예제와 에러 처리 정책을 기록한다.
- [ ] 린트/포맷/타입 체크 워크플로에 새 패키지를 포함하도록 CI 설정을 업데이트한다.

## 마무리
- [ ] `embedding.py` 잔여 기능을 확인하고, 모듈화 후 최소한의 파사드(예: `from embedding.pipeline.runner import main`)만 남긴다.
- [ ] 불필요해진 전역 변수, 유틸 함수, 중복 상수 등을 정리한다.
- [ ] 팀원과 함께 리팩터링 후 코드 리뷰 및 성능/자원 사용 변화를 점검한다.
