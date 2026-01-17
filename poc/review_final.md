🧠 한 줄 요약

RAG 스택의 구조는 성숙 단계에 들어섰지만, 워커 이벤트 루프 차단·무효화된 최적화 플래그·CLI 로깅 규칙 재위반·타입 힌트 미완·API 테스트 부재로 인해 아직 머지 불가다.

📌 3줄 요약

FastAPI 라우트는 threadpool로 고쳐졌지만, LangGraph 워커 내부에서 여전히 동기 DB 작업을 직접 실행해 이벤트 루프가 멈춤.

--optimize 플래그가 파이프라인에 전혀 전달되지 않아 사실상 no-op이며, CLI 로깅(print) 위반도 재발.

새 REST 엔드포인트에 대한 테스트가 전무하고, _parse_file 타입 힌트 요구사항도 아직 충족되지 않음.

🚨 핵심 이슈 정리 (우선순위 기준)
1️⃣ LangGraph 워커 이벤트 루프 차단 (치명적)

파일: poc/src/rag/worker.py:44

문제:

SearchUseCase.execute (무거운 동기 DB 쿼리)를
async 워커 내부에서 직접 호출

영향:

해당 툴 실행 동안 LangGraph 전체 이벤트 루프 freeze

요구사항:

asyncio.to_thread() 또는 executor로 명시적 오프로딩

👉 FastAPI에서는 고쳤지만, worker 경로는 아직 미수정이라는 점이 핵심

2️⃣ --optimize 플래그가 무효 (행동 불일치)

파일: poc/src/rag/api/use_cases/search.py:57

문제:

optimize_query / llm_client가 파이프라인에 전달되지 않음

CLI에서는 플래그를 광고하지만, 항상 Gemini가 초기화됨

영향:

사용자 관점에서 옵션이 거짓말

요구사항:

RetrievalPipeline.retrieve(use_self_query=…)로 연결

또는 플래그 자체 제거

3️⃣ CLI 로깅 규칙 재위반 (반복 지적)

파일:

poc/src/rag/api/cli/repl.py:44

poc/src/rag/api/cli/quality.py:95

문제:

여전히 print()로 banner/ack/metrics 출력

의미:

이전 리뷰에서 이미 지적된 사항이 완전히 해소되지 않음

요구사항:

loguru.logger로 통일

👉 이건 기능 문제가 아니라 리뷰 신뢰도 문제

4️⃣ 타입 힌트 미완 (가드레일 위반 지속)

파일: poc/src/rag/api/use_cases/ingest.py:246

문제:

_parse_file 반환 타입이 List[Any]

요구사항:

List[RawSegment]처럼 구체 타입 명시

영향:

pyright/mypy 여전히 실패

5️⃣ 새 REST 엔드포인트 테스트 부재

파일: poc/src/api/routes.py:356

문제:

/rag/ingest, /rag/search에 대한 FastAPI/CLI 테스트 없음

영향:

새 코드 경로에 회귀 방지 장치가 없음

요구사항:

최소한 happy-path API 테스트 1~2개 필요

✅ 잘 된 점 (여전히 유효)

ingestion / retrieval / generation / worker 레이어 분리 유지

use case 중심 오케스트레이션 → CLI/API/worker 공유

DB/스토리지 헬퍼 중앙화로 스키마·인덱스 관리 개선

CLI + worker 단위 테스트로 import/기본 제어 흐름 검증

📋 체크리스트 재평가

LangChain / LangGraph: ❌ (워커 이벤트 루프 차단)

Type Hints: ❌

Security: ✅

Tests: ❌ (REST 엔드포인트 미커버)

Side Effects / Bugs: ❌

🔑 핵심 키워드

LangGraph event loop block · asyncio.to_thread · --optimize no-op · CLI print 재발 · _parse_file 타입 힌트 · API 테스트 부재