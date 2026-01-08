## 001-46-52.pdf 임베딩 실행 가이드

`embedding.py`를 사용해 `001-46-52.pdf`를 Postgres(pgvector)에 임베딩하는 방법을 정리했습니다.

### 사전 준비
- Docker 및 Docker Compose 설치
- Python 3.10+ 설치
- `.env`에 유효한 Voyage AI 키 설정: `VOYAGE_API_KEY`

### 1) 데이터베이스 기동
- 명령: `docker compose up -d`
- 이미지: `pgvector/pgvector:pg16`
- 포트: 호스트 `5432` 사용(이미 사용 중이면 매핑 변경 필요)

### 2) 환경 변수 확인
- 파일: `.env`
  - `PG_CONN=postgresql+psycopg://langchain:langchain@localhost:5432/vectordb`
  - `VOYAGE_API_KEY=<your_key>`
  - `COLLECTION_NAME=langchain_book_ocr`
  - `PARENT_MODE=page` (페이지/섹션 단위 묶기 활성화)
  - `RATE_LIMIT_RPM=3` (무료 계정의 낮은 제한 대응용 속도 제한)
  - `MAX_CHARS_PER_REQUEST=4000` (요청당 텍스트 총 길이 제한으로 TPM 초과 방지)
  - `MAX_ITEMS_PER_REQUEST=1` (요청당 텍스트 개수 제한: 1개씩 전송)
  - `MAX_DOCS_TO_EMBED=30` (스모크 테스트: 처음 30개 청크만 처리)
- 선택(고급) 튜닝: `IVFFLAT_PROBES`, `HNSW_EF_SEARCH`, `HNSW_EF_CONSTRUCTION`
- 선택 그룹핑: `PARENT_MODE=unit|page|section|page_section`
- 선택 커스텀 스키마 기록: `CUSTOM_SCHEMA_WRITE=true`

### 3) 파이썬 환경 구성
- 가상환경 생성/활성화(PowerShell): `python -m venv .venv; .\.venv\Scripts\Activate.ps1`
- 의존성 설치:
  - 기본: `pip install -r requirement.txt`
  - 인코딩 문제 발생 시 최소 설치: `pip install langchain-postgres langchain-voyageai python-dotenv psycopg pdfminer.six`

### 4) PDF 임베딩 실행
- 명령: `python embedding.py "001-46-52.pdf"`
- 수행 내용:
  - PDF에서 텍스트 추출(pdfminer/pdftotext)
  - 텍스트가 부족/없으면 자동 OCR 시도(`ENABLE_AUTO_OCR=true`이고 `ocrmypdf`가 설치된 경우)
  - 텍스트/코드 블록 분할 및 캡션(그림/표) 보강
  - Voyage AI로 임베딩 생성
  - pgvector 컬렉션에 upsert 및 인덱스 생성
  - MultiVector 검색용 parent 문서 저장(간단 요약)

### 4-1) Markdown(.md) 임베딩 실행
- 명령: `python embedding.py "TalkFile_001_clean.md"`
- 지원 사항:
  - Markdown 펜스 코드블록(```lang) 언어 감지 → `view=code`, `lang`
  - 이미지 마크다운(`![alt](url)`)을 `view=image`로 분리 저장(alt·url은 metadata에 기록)
  - 일반 텍스트는 `view=text`로 청킹
  - `--- Page Break ---` 라인을 페이지 경계로 인식하여 페이지 번호를 자동 증가(PARENT_MODE=page 사용 시 유효)
- 레이트리밋 대응: `.env`의 `RATE_LIMIT_RPM`/`MAX_CHARS_PER_REQUEST`를 통해 임베딩 요청 속도와 크기를 제어합니다.
  - 추가 제어: `MAX_ITEMS_PER_REQUEST`로 요청당 문서 개수(기본 1) 제한, `MAX_DOCS_TO_EMBED`로 1회 처리량 제한

#### Parent Mode 사용 팁
- `.env`에서 `PARENT_MODE`를 설정하면 임베딩 시 각 청크의 `metadata.parent_id`가 페이지/섹션 기반으로 자동 설정됩니다.
  - `unit`: 파일 내 논리 유닛(기본 분할) 기준
  - `page`: 페이지 기반(`PAGE_REGEX`로 페이지 라인 감지)
  - `section`: 섹션/헤더 기반(`SECTION_REGEX`로 헤더 감지)
  - `page_section`: 페이지와 섹션을 조합하여 부모 ID 생성
- 페이지/섹션 감지 정규식 커스터마이즈(필요 시 `.env`에 설정)
  - `PAGE_REGEX`: 기본값 `(?mi)^\s*(?:page|페이지)\s*([0-9]{1,5})\b`
  - `SECTION_REGEX`: 기본값 `(?m)^(?:#{1,3}\s+.+|Chapter\s+\d+\b|제\s*\d+\s*장\b|\d+\.\d+\s+.+)`
- 부모 ID 예시(파일명 `001-46-52.pdf` 기준)
  - `PARENT_MODE=page` → `001-46-52-p3` (3페이지 섹션)
  - `PARENT_MODE=section` → `001-46-52-s-introduction` (헤더 슬러그화)
  - `PARENT_MODE=page_section` → `001-46-52-p3-s-introduction`

### 5) 결과 확인/조회(선택)
- 예시: `python retriever_multi_view_demo.py "검색어"`
- 필터 사용: `python retriever_multi_view_demo.py "검색어" text python`
 - 부모 기준 조회(SQL 예시):
   - `SELECT DISTINCT cmetadata->>'parent_id' AS parent_id FROM langchain_pg_embedding LIMIT 20;`
   - Parent 텍스트(docstore): `SELECT id, LEFT(content, 200) FROM docstore_parent LIMIT 10;`

### 6) 트러블슈팅
- 5432 포트 충돌: `docker-compose.yml`의 포트 매핑을 예) `55432:5432`로 바꾸고, `PG_CONN`도 동일 포트로 맞춤
- PDF 텍스트가 희박함: OCR 고려
  - 자동 OCR: `.env`의 `ENABLE_AUTO_OCR=true` + `ocrmypdf` 설치 후 `python embedding.py "001-46-52.pdf"`
  - 수동 OCR 예시: `ocrmypdf --sidecar out.txt --skip-text 001-46-52.pdf 001-46-52.ocr.pdf`
  - Windows 설치 가이드: `docs/ocr_setup_windows.md`
- 패키지 설치 실패: 위 최소 설치 커맨드 사용
- 연결 오류: `PG_CONN` 스킴이 `postgresql+psycopg`인지, DB 컨테이너가 기동 중인지 확인

### 참고
- 기본 청킹은 텍스트/코드 혼합 문서에 맞춰져 있으며, 메타데이터(`parent_id`, `view`, `lang`)를 통해 Parent-Child 검색을 지원합니다.
- 페이지/섹션 단위로 묶고 싶다면 실행 전 `.env`의 `PARENT_MODE`를 설정하세요.
