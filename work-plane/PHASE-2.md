# Phase 2: 슈퍼바이저 코어 구현

## 목표
LLM 기반으로 질문을 분석하고, 전략을 수립하며, 워커를 조율하는 슈퍼바이저를 구현합니다.

---

## Task 2.1: 슈퍼바이저 프롬프트 정의

### 작업 내용: `poc/src/supervisor/prompts.py`

```python
"""슈퍼바이저 프롬프트 템플릿"""

ANALYZE_PROMPT = """당신은 질문 분석 전문가입니다.
사용자의 질문을 분석하여 다음 정보를 추출하세요.

## 질문
{question}

## 분석 항목
1. intent: 질문의 핵심 의도 (한 문장)
2. requires_recent_info: 최신 정보가 필요한가? (2024년 이후 정보, 최근 뉴스 등)
3. complexity: 단순 질문인가 복합 질문인가? (simple/complex)
4. keywords: 검색에 활용할 핵심 키워드 (최대 5개)

JSON 형식으로 응답하세요."""


PLAN_PROMPT = """당신은 질문 응답 전략가입니다.
분석 결과를 바탕으로 최적의 실행 계획을 수립하세요.

## 원본 질문
{question}

## 질문 분석
{analysis}

## 사용 가능한 워커
- rag: 내부 문서 벡터 검색 (기술 문서, 매뉴얼 등)
- web_search: 실시간 웹 검색 (최신 정보, 뉴스, 트렌드)
- llm_direct: LLM 직접 답변 (일반 지식, 설명, 분석)

## 전략 옵션
- single: 하나의 워커만 사용
- sequential: 여러 워커를 순차 실행 (앞 결과가 뒤에 영향)
- parallel: 여러 워커를 병렬 실행 후 종합

## 지침
1. 최신 정보가 필요하면 web_search 포함
2. 내부 문서 관련이면 rag 포함
3. 일반적인 설명/분석은 llm_direct
4. 복합 질문은 여러 워커 조합
5. 쿼리 정제: 각 워커에 최적화된 검색어 생성

JSON 형식으로 응답하세요."""


SYNTHESIZE_PROMPT = """당신은 정보 종합 전문가입니다.
수집된 정보를 바탕으로 사용자 질문에 대한 최종 답변을 작성하세요.

## 원본 질문
{question}

## 수집된 정보
{results}

## 지침
1. 질문에 직접적으로 답변하세요
2. 여러 출처의 정보를 자연스럽게 통합하세요
3. 출처가 있다면 언급하세요
4. 정보가 부족하거나 불확실하면 솔직히 밝히세요
5. 한국어로 답변하세요

답변:"""


EVALUATE_PROMPT = """당신은 답변 품질 평가자입니다.
수집된 결과가 질문에 답하기에 충분한지 평가하세요.

## 원본 질문
{question}

## 수집된 결과
{results}

## 평가 기준
1. 질문의 핵심에 답하고 있는가?
2. 정보가 충분한가?
3. 신뢰할 수 있는 정보인가?

## 응답 형식
{{
    "is_sufficient": true/false,
    "confidence": 0.0-1.0,
    "missing_aspects": ["부족한 부분 목록"],
    "suggestion": "추가 조치 제안 (불충분할 경우)"
}}"""
```

### 완료 조건
- 4개의 프롬프트 템플릿 정의 완료

---

## Task 2.2: 슈퍼바이저 메인 클래스

### 작업 내용: `poc/src/supervisor/supervisor.py`

```python
"""슈퍼바이저 메인 로직"""
import asyncio
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.schemas.models import (
    QueryAnalysis,
    ExecutionPlan,
    ExecutionStrategy,
    WorkerType,
    WorkerResult,
    SupervisorResponse
)
from src.workers.base import BaseWorker
from .prompts import ANALYZE_PROMPT, PLAN_PROMPT, SYNTHESIZE_PROMPT, EVALUATE_PROMPT
from config import config


class Supervisor:
    """모든 의사결정을 담당하는 슈퍼바이저"""

    def __init__(
        self,
        workers: Dict[WorkerType, BaseWorker],
        model: str = None,
        max_retries: int = None
    ):
        self.workers = workers
        self.model = model or config.OPENAI_MODEL
        self.max_retries = max_retries or config.MAX_RETRIES
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=0,
            api_key=config.OPENAI_API_KEY
        )
        self.execution_log: List[str] = []

    def _log(self, message: str):
        """실행 로그 기록"""
        self.execution_log.append(message)
        print(f"[Supervisor] {message}")

    async def process(self, question: str) -> SupervisorResponse:
        """질문 처리 메인 플로우"""
        self.execution_log = []
        self._log(f"질문 수신: {question}")

        # 1. 질문 분석
        analysis = await self._analyze(question)
        self._log(f"분석 완료: intent={analysis.intent}, recent={analysis.requires_recent_info}")

        # 2. 실행 계획 수립
        plan = await self._plan(question, analysis)
        self._log(f"계획 수립: strategy={plan.strategy}, workers={plan.workers}")

        # 3. 워커 실행
        results = await self._execute(plan)
        self._log(f"실행 완료: {len(results)}개 결과 수집")

        # 4. 결과 평가 및 재시도
        retry_count = 0
        while retry_count < self.max_retries:
            evaluation = await self._evaluate(question, results)
            if evaluation["is_sufficient"]:
                break
            self._log(f"결과 불충분, 재시도 {retry_count + 1}/{self.max_retries}")
            plan = await self._replan(question, analysis, results, evaluation)
            new_results = await self._execute(plan)
            results.extend(new_results)
            retry_count += 1

        # 5. 최종 답변 생성
        response = await self._synthesize(question, results)
        self._log("답변 생성 완료")

        return SupervisorResponse(
            answer=response,
            sources=self._collect_sources(results),
            workers_used=[r.worker for r in results],
            execution_log=self.execution_log,
            total_confidence=self._calculate_confidence(results)
        )

    async def _analyze(self, question: str) -> QueryAnalysis:
        """질문 분석"""
        prompt = ANALYZE_PROMPT.format(question=question)
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])

        # 구조화된 출력으로 파싱
        analysis_llm = self.llm.with_structured_output(QueryAnalysis)
        result = await analysis_llm.ainvoke([HumanMessage(content=prompt)])
        result.original_query = question
        return result

    async def _plan(self, question: str, analysis: QueryAnalysis) -> ExecutionPlan:
        """실행 계획 수립"""
        prompt = PLAN_PROMPT.format(
            question=question,
            analysis=analysis.model_dump_json(indent=2)
        )
        plan_llm = self.llm.with_structured_output(ExecutionPlan)
        return await plan_llm.ainvoke([HumanMessage(content=prompt)])

    async def _execute(self, plan: ExecutionPlan) -> List[WorkerResult]:
        """워커 실행"""
        results = []

        if plan.strategy == ExecutionStrategy.PARALLEL:
            # 병렬 실행
            tasks = []
            for i, worker_type in enumerate(plan.workers):
                query = plan.refined_queries[i] if i < len(plan.refined_queries) else plan.refined_queries[0]
                worker = self.workers.get(worker_type)
                if worker:
                    tasks.append(worker.execute(query))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # 예외 처리
            results = [
                r if isinstance(r, WorkerResult) else WorkerResult(
                    worker=plan.workers[i],
                    query=plan.refined_queries[i] if i < len(plan.refined_queries) else "",
                    content="",
                    success=False,
                    error=str(r)
                )
                for i, r in enumerate(results)
            ]
        else:
            # 순차 실행 (single, sequential)
            for i, worker_type in enumerate(plan.workers):
                query = plan.refined_queries[i] if i < len(plan.refined_queries) else plan.refined_queries[0]
                worker = self.workers.get(worker_type)
                if worker:
                    try:
                        result = await worker.execute(query)
                        results.append(result)
                    except Exception as e:
                        results.append(WorkerResult(
                            worker=worker_type,
                            query=query,
                            content="",
                            success=False,
                            error=str(e)
                        ))

        return results

    async def _evaluate(self, question: str, results: List[WorkerResult]) -> dict:
        """결과 평가"""
        results_text = "\n\n".join([
            f"[{r.worker.value}] (confidence: {r.confidence})\n{r.content}"
            for r in results if r.success
        ])

        prompt = EVALUATE_PROMPT.format(question=question, results=results_text)
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])

        # JSON 파싱 (간단한 구현)
        import json
        try:
            return json.loads(response.content)
        except:
            return {"is_sufficient": True, "confidence": 0.5}

    async def _replan(
        self,
        question: str,
        analysis: QueryAnalysis,
        results: List[WorkerResult],
        evaluation: dict
    ) -> ExecutionPlan:
        """재계획 수립"""
        # 이전에 사용하지 않은 워커 선택
        used_workers = {r.worker for r in results}
        available = [w for w in self.workers.keys() if w not in used_workers]

        if not available:
            # 모든 워커를 이미 사용했다면 가장 신뢰도 높은 워커 재시도
            best_worker = max(results, key=lambda r: r.confidence).worker
            available = [best_worker]

        return ExecutionPlan(
            strategy=ExecutionStrategy.SINGLE,
            workers=[available[0]],
            refined_queries=[question],  # 원본 쿼리로 재시도
            reasoning=f"이전 결과 불충분. {evaluation.get('suggestion', '다른 소스 시도')}"
        )

    async def _synthesize(self, question: str, results: List[WorkerResult]) -> str:
        """최종 답변 생성"""
        results_text = "\n\n".join([
            f"[출처: {r.worker.value}]\n{r.content}"
            for r in results if r.success and r.content
        ])

        if not results_text:
            return "죄송합니다. 질문에 대한 충분한 정보를 찾지 못했습니다."

        prompt = SYNTHESIZE_PROMPT.format(question=question, results=results_text)
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return response.content

    def _collect_sources(self, results: List[WorkerResult]) -> List[str]:
        """출처 수집"""
        sources = []
        for r in results:
            sources.extend(r.sources)
        return list(set(sources))

    def _calculate_confidence(self, results: List[WorkerResult]) -> float:
        """전체 신뢰도 계산"""
        if not results:
            return 0.0
        successful = [r for r in results if r.success]
        if not successful:
            return 0.0
        return sum(r.confidence for r in successful) / len(successful)
```

### 완료 조건
- Supervisor 클래스 완성
- 5단계 플로우 구현 (analyze → plan → execute → evaluate → synthesize)

---

## Task 2.3: __init__.py 작성

### 작업 내용: `poc/src/supervisor/__init__.py`

```python
from .supervisor import Supervisor
from .prompts import ANALYZE_PROMPT, PLAN_PROMPT, SYNTHESIZE_PROMPT, EVALUATE_PROMPT

__all__ = ["Supervisor", "ANALYZE_PROMPT", "PLAN_PROMPT", "SYNTHESIZE_PROMPT", "EVALUATE_PROMPT"]
```

### 완료 조건
- 깔끔한 export 정의

---

## Phase 2 완료 체크리스트

- [ ] prompts.py 작성 완료
- [ ] supervisor.py 작성 완료
- [ ] __init__.py 작성 완료
- [ ] 슈퍼바이저가 구조화된 출력(Pydantic)을 사용함
- [ ] 비동기 실행 지원 (async/await)

---

## 다음 단계
Phase 2 완료 후 [PHASE-3.md](./PHASE-3.md)로 진행합니다.
