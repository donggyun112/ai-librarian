# OCR Vector DB — 프로젝트 분석

## 개요
- 목적: OCR/일반 텍스트 파일을 수집·전처리하고, 주변 설명과 코드 블록을 연계하여 의미 단위로 묶은 뒤, 청크로 분할해 임베딩을 생성하고 Postgres(pgvector)에 저장/검색합니다.
- 스택: Python, LangChain(`langchain_voyageai`, `langchain_postgres`), Postgres + pgvector, psycopg.
- 진입점: `embedding.py` (기본 글롭 `test/*.txt`).

## 데이터 흐름
1. `glob`로 파일 경로 수집 및 정렬
2. 파일 파싱: 텍스트 정규화 → 문단 분리
3. 세그멘트 구성: 코드 블록 탐지 후 언어(파이썬/자바스크립트) 추정
4. 유닛화: 텍스트와 코드 조합을 하나의 단위(unit)로 묶고 역할 부여
5. 청크화: 텍스트/코드를 각각 기준에 맞게 분할하여 `Document` 생성(메타 포함)
6. 임베딩·업서트: VoyageAI 임베딩 생성 후 PGVector에 배치 업서트
7. 인덱싱: pgvector 확장과 보조 인덱스(멱등) 생성

## 전처리 및 세그멘테이션
- `normalize(text)`: 합자/따옴표/대시 치환, NBSP→공백, 줄끝 공백 제거, 과도한 개행 축소.
- `split_paragraph(text)`: 2개 이상의 연속 개행을 기준으로 단락 분리.
- 코드 탐지 `is_code_block(p)`:
  - 백틱 코드 펜스(\`\`\`)가 있으면 코드로 판정.
  - 없으면 정규식 힌트(`CODE_HINT`)로 코드스멜(파이썬/JS 키워드, 세미콜론, 중괄호 등) 개수를 기준으로 판단.
- 언어 추정 `guess_code_lang(p)`: 파이썬/JS 시그니처 정규식 빈도 비교 후 보조 규칙 적용.
- 세그먼트 타입: `RawSegment(kind, content, language, order)`에서 `kind ∈ {"text", "code"}`.

## 유닛화 전략
- 함수: `unitize_txt_py_js_streaming` → `(unit_id, unit_role, segment)` 튜플 시퀀스 출력.
- 목표 패턴(현실 사례): 설명 텍스트 → Python 코드(연속 가능) → (옵션) 브리지 텍스트 → JavaScript 코드(연속 가능) → (옵션) 후속 텍스트.
- 역할: `pre_text`, `python`, `javascript`, `bridge_text`, `post_text`, `other`.
- 동작 요약:
  - 직전 텍스트를 버퍼링하다가 Python 코드 시작 시 해당 텍스트를 `pre_text`로 유닛에 부착(상한: `max_pre_text_chars`).
  - 파이썬/자바스크립트 연속 블록은 같은 유닛에서 각각 역할로 누적.
  - Python 없이 단독 JS가 나오면 `other`로 방출(억지 결합하지 않음).
  - 기본 옵션: `attach_pre_text=True`, `attach_post_text=False`, `bridge_text_max=0`.

## 청크화
- 텍스트: `RecursiveCharacterTextSplitter`
  - `chunk_size=1200`, `chunk_overlap=150`, 분리자 `['\n##', '\n###', '\n\n', '\n', ' ', '']`.
  - 공개 API `split_text` 사용.
- 코드: `split_code_safely`
  - 줄 단위로 약 1800자까지 누적, 청크 간 5줄 오버랩.
  - 매우 긴 단일 라인도 안전하게 분할.
- 문서 메타데이터:
  - 공통: `source`(파일명), `order`, `kind`, 선택적 `unit_id`, `unit_role`.
  - 코드: `lang`("python", "javascript", 또는 "unknown").

## 임베딩 및 저장
- 임베딩: `VoyageAIEmbeddings(model=VOYAGE_MODEL)` (기본 `voyage-3`).
- 벡터 스토어: `PGVector(connection=PG_CONN, collection_name=COLLECTION_NAME, distance_strategy="COSINE", use_jsonb=True, embedding_length=EMBEDDING_DIM)`.
- 업서트: `upsert_batch(store, docs, batch_size=64)`로 배치 추가.

## 데이터베이스 및 인덱스
- 확장: `ensure_extension_vector()`에서 `CREATE EXTENSION IF NOT EXISTS vector` 실행(멱등).
- 인덱스 대상 테이블: `langchain_pg_embedding` (컬렉션 공용 테이블)
  - HNSW(cosine) 인덱스: `embedding vector_cosine_ops`.
  - JSONB GIN 인덱스: `cmetadata`.
  - 선택 BTREE 인덱스: `(cmetadata->>'unit_id')`, `(…->>'unit_role')`, `(…->>'lang')`.
- 인덱스 이름: `sanitize_identifier(COLLECTION_NAME)`로 영숫자/언더스코어만 허용, 소문자화, 선행 문자가 유효하지 않으면 `_` 접두.

## 환경 변수
- `PG_CONN`: Postgres 연결 문자열(SQLAlchemy/psycopg 호환; psycopg 직접 연결 시 접두 조정).
- `COLLECTION_NAME`: PGVector 컬렉션 이름 및 인덱스 명명에 사용.
- `VOYAGE_MODEL`: Voyage 임베딩 모델(기본 `voyage-3`).
- `EMBEDDING_DIM`: 임베딩 차원(기본 `1024`).

## CLI 사용법
- 실행: `python embedding.py "<glob>"`
- 기본값: 인자 미제공 시 `test/*.txt` 처리.
- 출력: 파싱/업서트 청크 개수 로그, 처리 후 인덱스 생성.

## 적용한 수정 사항(버그 픽스)
- 텍스트 kind 불일치 수정: 텍스트 세그먼트를 `kind="text"`로 통일(이전 `"txt"` → 다운스트림 로직과 정합).
- 공개 API 사용: `TEXT_SPLITTER._split_text` → `TEXT_SPLITTER.split_text`로 교체.
- 인덱스명 안전화: `sanitize_identifier` 추가 후 `COLLECTION_NAME` 기반 인덱스명에 적용(공백/대시 등으로 인한 생성 실패 방지).

## 유의사항 및 개선 제안
- 코드 탐지 민감도: 일반 문서에서 과검출 가능성 존재 → MD 파일의 경우 코드 펜스 우선, 힌트는 보조로 완화 고려.
- 컬렉션 전략: 단일 테이블 공용 구조 → 스키마 분리 또는 컬렉션 필터링/파티셔닝 검토.
- 메타데이터 확장: 청크별 안정적 ID/해시를 추가해 중복 방지와 멱등 업서트 강화.
- 오류 처리: DB/네트워크 작업에 재시도·백오프와 명확한 로깅 도입.
- 동시성: 대용량 처리 시 배치/멀티프로세싱과 커넥션 풀 최적화.
- 검색 필터: JSONB GIN을 활용해 챕터/섹션 등 풍부한 메타로 정밀 필터링.
- 언어 범위: 필요 시 Java/C++/Go 등 확장 또는 코드 펜스의 언어 태그 활용.
- 유닛 연결: 검색 시 `pre_text`+`python`+`javascript` 조합을 문맥 단위로 제공하는 후처리 고려.

## 테스트 아이디어
- 유닛 테스트: `normalize`, `is_code_block`, `guess_code_lang`, `split_code_safely`의 경계 사례 검증.
- 골든 테스트: 합성 문서로 유닛화·메타 생성 결과를 스냅샷 비교.
- 통합 테스트: 소형 픽스처 집합을 인덱싱 후 인덱스 존재 및 쿼리 정확도 확인.

