# 기능 추가 배경과 이유(멀티 벡터 1단계)

이 문서는 `docs/CHANGES.md`의 "기능 추가(멀티 벡터 1단계)"에 포함된 세 가지 항목을 왜 도입했는지 배경과 효과를 설명합니다.

## 1) 메타 확장: parent_id/view 추가
- 왜 필요한가:
  - 단일 벡터로는 서로 다른 표현(자연어 설명, 코드, 이미지 캡션)을 동시에 잘 포착하기 어렵습니다. 뷰(view)별 임베딩을 저장하려면 각 청크가 어떤 관점에서 생성되었는지(`view`)와 어느 상위 문맥(유닛)에 속하는지(`parent_id`)가 필수입니다.
  - 검색 시 child(뷰별 청크) 결과를 상위 문맥(부모 유닛)으로 복원하기 위해 `parent_id`가 필요합니다.
- 기대 효과:
  - 뷰별 검색과 재랭킹이 가능해져 쿼리 유형(코드/자연어)에 강건한 검색 성능 확보.
  - RAG 입력 구성 시 같은 `parent_id`를 가진 텍스트·코드·브리지 텍스트를 쉽게 묶어 문맥 품질 향상.
- 대안/트레이드오프:
  - 대안: 단일 뷰만 유지하고 후처리로 보완 → 코드/자연어 혼재 질의에서 품질 저하.
  - 트레이드오프: 메타가 증가하고 저장 데이터가 다소 늘어남.
- 운영 영향:
  - 쿼리/필터에서 `view`와 `parent_id` 사용 가능. 멀티 뷰 전략과 궁합이 좋음.

### 예시와 효과 비교
- 예시 쿼리 A(자연어): "파이썬에서 파일을 여는 방법"
  - 단일 벡터: 코드 스니펫과 설명이 섞인 청크 중 임베딩 분포에 따라 코드가 과소/과대 반영될 수 있음.
  - 멀티 뷰(+meta): `view=text`에서 파일 I/O 설명, `view=code`에서 `open(path, 'r')` 코드가 각각 상위 노출. `parent_id`로 하나의 유닛에 묶여 RAG 컨텍스트 품질 향상.
- 예시 쿼리 B(코드 중심): "TypeError: can't concat str to bytes 해결"
  - 단일 벡터: 에러 메시지와 해결 코드가 하나의 청크에 공존하지 않으면 누락 가능.
  - 멀티 뷰(+meta): `view=code`에서 해결 코드가 직접 매칭되고, `view=text`에서 원인 설명이 함께 랭크되어 상보적 컨텍스트 제공.

## 2) DB 인덱스 보강: parent_id/view BTREE
- 왜 필요한가:
  - 뷰별 검색(`view=...`)과 부모 복원(`parent_id` 그룹핑)을 빈번히 수행합니다. 풀스캔을 피하고 일관된 지연(latency)을 확보하려면 해당 필드에 대한 인덱스가 필요합니다.
- 기대 효과:
  - 메타 필터 기반 검색의 성능·안정성 개선(특히 데이터가 커질수록 효과 증대).
  - 검색 결과를 상위 문맥으로 빠르게 묶을 수 있어 후처리 비용 감소.
- 대안/트레이드오프:
  - 대안: JSONB GIN만 의존 → 정확한 equality 필터/정렬에서는 BTREE보다 비효율적일 수 있음.
  - 트레이드오프: 인덱스 공간 증가, 색인/업데이트 비용 소폭 증가.
- 운영 영향:
  - 인덱스 유지보수 필요(대규모 재색인 시 생성 전략 고려). 읽기 성능 향상으로 총합 이득.

### 예시와 효과 비교
- 시나리오: 코퍼스 100만 청크 중 `view='code'`만 상위 k 검색 후 `parent_id`로 그룹핑
  - 인덱스 없음: JSONB 전체 스캔 + 필터, 지연 변동 큼, CPU 부담 큼.
  - 인덱스 보강: `view`=코드 범위를 즉시 축소, 상위 후보 집합에 대해 `parent_id` 그룹핑 효율적.
- 운영 팁:
  - 쓰기(업서트) 배치 시 인덱스 수가 많을수록 비용 증가 → 배치 크기/트랜잭션 조절로 완화.

## 3) 검색 데모 스크립트: RRF 기반 멀티 뷰 통합
- 왜 필요한가:
  - 멀티 뷰 저장만으로는 품질 개선이 보장되지 않습니다. 검색 단계에서 각 뷰를 별도로 질의하고 결과를 융합하는 파이프라인이 필요합니다.
  - RRF(Reciprocal Rank Fusion)는 구현이 단순하고 다양한 스코어 분포에서 강건하게 작동하는 대표적 late-fusion 방법입니다.
- 기대 효과:
  - 코드·텍스트 뷰 각각의 강점을 살려 상위 결과 품질 개선.
  - `parent_id` 단위로 그룹핑해 RAG 문맥 조립의 시작점을 제공.
- 대안/트레이드오프:
  - 대안: 단일 뷰 검색, 혹은 복잡한 학습형 랭커 도입.
  - 트레이드오프: 뷰 수만큼 검색 호출이 늘어남(캐시/병렬화로 완화 가능).
- 운영 영향:
  - 간단한 예제로 품질/성능을 빠르게 확인 가능. 이후 가중치·MMR·쿼리 분류 등 고도화의 베이스라인으로 활용.

### 예시와 효과 비교
- 실무형 쿼리: "langchain pgvector hnsw 인덱스 생성"
  - 단일 뷰: 텍스트 설명 또는 코드 한쪽으로 쏠림.
  - 멀티 뷰+RRF: `view=text`에서 개념·옵션 설명, `view=code`에서 `CREATE INDEX ... USING hnsw` 스니펫 동시 회수 → RRF 융합으로 상위 후보에 함께 반영.
- 간단 가중치 확장:
  - 코드성 신호 감지 시 `code` 결과에 +α 가중(예: rank 보정), 자연어형은 `text`/`summary` 가중.

---

## 요약
- `parent_id`/`view` 메타는 멀티 뷰 전략의 토대이며, 해당 메타에 맞춘 BTREE 인덱스는 규모가 커져도 성능을 유지하기 위한 필수 요소입니다. RRF 데모 스크립트는 멀티 뷰 검색을 실제로 적용·검증하기 위한 최소 구현으로, 이후 단계적 고도화를 위한 출발점입니다.

부록: 쿼리 유형별 권장 뷰 가중치(초기값)
- 코드/에러 메시지 중심: code 0.6, text 0.3, summary 0.1
- 개념/절차 설명: text 0.6, summary 0.3, code 0.1
- 이미지/도 참조: image 0.7, text 0.2, summary 0.1 (image 뷰 도입 후)

---

## 실제 예시(샘플 Markdown → 유닛/뷰/검색)

### 입력 Markdown 예시
```md
# 파일 I/O 기초

파이썬에서는 `open()` 함수를 사용해 파일을 열 수 있습니다.

```python
with open("data.txt", "r", encoding="utf-8") as f:
    print(f.read())
```

자바스크립트에서도 Node.js 환경에서 fs 모듈을 사용합니다.

```javascript
const fs = require('fs');
const data = fs.readFileSync('data.txt', 'utf-8');
console.log(data);
```

![파일 읽기 예시](imgs/read.png)
그림 3-1. 파일을 읽어 콘솔에 출력하는 예시
```

### 유닛화 결과(개념)
- unit_id: 123e4567-e89b-12d3-a456-426614174000 (예)
- pre_text: "파이썬에서는 open() 함수를 사용해 …"
- python: 코드 블록 1개
- bridge_text: "자바스크립트에서도 Node.js …"
- javascript: 코드 블록 1개
- post_text: (없음)
- image 캡션: alt="파일 읽기 예시", 캡션="그림 3-1. …" (image 뷰 도입 시)

### 생성되는 문서(Child) 예시
- view=text
  - page_content: "파이썬에서는 open() 함수를 사용해 …"
  - metadata: { source: "ch03.md", parent_id: unit_id, view: "text", unit_role: "pre_text" }
- view=code (lang=python)
  - page_content: with open("data.txt", "r", …)
  - metadata: { source: "ch03.md", parent_id: unit_id, view: "code", lang: "python", unit_role: "python" }
- view=code (lang=javascript)
  - page_content: const fs = require('fs'); …
  - metadata: { source: "ch03.md", parent_id: unit_id, view: "code", lang: "javascript", unit_role: "javascript" }
- view=image (옵션)
  - page_content: "파일 읽기 예시. 그림 3-1. 파일을 읽어 …"
  - metadata: { source: "ch03.md", parent_id: unit_id, view: "image", image_url: "imgs/read.png" }

### 검색 데모 실행 예시
```bash
python retriever_multi_view_demo.py "파이썬에서 파일 읽는 법"
```

예상 출력(발췌):
```
parents: ['123e4567-e89b-12d3-a456-426614174000']
- parent: 123e4567-e89b-12d3-a456-426614174000
  [view=text] ch03.md: 파이썬에서는 open() 함수를 사용해 파일을 …
  [view=code] ch03.md: with open("data.txt", "r", encoding="utf-8") as f: …
```

설명:
- 동일 쿼리 임베딩으로 `view=text`와 `view=code`에서 각각 top-k를 검색합니다.
- RRF 융합으로 뷰 간 결과를 통합하고, `parent_id` 기준으로 묶어 상위 부모 유닛을 정합니다.
- RAG 컨텍스트 구성 시 위 부모 유닛의 `pre_text + python(+bridge_text)`를 함께 제공하면 응답 품질이 상승합니다.

---

## 이미지 캡션 파싱 적용 사례(예시)

### 입력 Markdown(다양한 캡션 형태)
```md
![배치 업서트 흐름](imgs/upsert.png)
그림 5-2. 업서트 배치 크기와 인덱스 부하 관계

텍스트로 캡션을 쓰는 경우도 있습니다: 업서트는 배치 크기 조절로 인덱스 비용을 분산합니다.

![HNSW 파라미터]
CONNECTIONS와 EF_SEARCH는 검색 지연과 정확도 사이의 트레이드오프를 만듭니다.
```

### 파싱 규칙과 결과
- 규칙(우선순위):
  1) 이미지 태그의 alt 텍스트 사용(있으면)
  2) 바로 다음 줄의 캡션 패턴(“그림/도/Fig.” 등) 채택
  3) 인접 문단 1개를 보조 캡션으로 결합(총 길이 상한 적용)
- 생성되는 image 뷰 예시:
  - page_content: "배치 업서트 흐름. 그림 5-2. 업서트 배치 크기와 인덱스 부하 관계"
  - metadata: { view: "image", image_url: "imgs/upsert.png", parent_id: unit_id, source: "ch05.md" }
  - page_content: "HNSW 파라미터. CONNECTIONS와 EF_SEARCH는 검색 지연과 정확도 사이의 트레이드오프를 만듭니다."
  - metadata: { view: "image", image_url: null, parent_id: unit_id, source: "ch05.md" }

효과: “업서트 배치 크기”, “HNSW EF_SEARCH” 같은 키워드 중심 질의에서 이미지 중심 문맥도 검색 후보에 포함되어, 시각 자료 참조가 필요한 답변 품질이 향상됩니다.

---

## summary 뷰 적용 전/후 비교(예시)

### 상황
- 한 유닛에 설명 텍스트가 3~4개 청크로 분리되고 코드도 2개 청크로 분리됨.
- 질의: "pgvector HNSW 인덱스 생성 절차와 주의점"

### summary 없음(전)
- `view=text`에서 각 청크가 분산되어 등장 → 상위 k 내에 일관된 개요가 부족.
- 사용자 응답 생성 시 문맥 연결이 약해 중복/누락 발생 가능.

### summary 있음(후)
- 규칙 기반 요약 생성(예):
  - page_content: "HNSW 인덱스는 embedding 컬럼에 대해 cosine 연산자를 사용해 생성한다. 인덱스 생성 후 배치 업서트 시 부하를 고려한다."
  - metadata: { view: "summary", parent_id: unit_id, source: "ch05.md" }
- 효과:
  - 질의 임베딩이 summary 청크에 직접 매칭되어 해당 유닛이 상위에 안정적으로 랭크.
  - RAG 컨텍스트에 summary + 핵심 코드 스니펫을 함께 제공하여 간결하고 정확한 답변 유도.

트레이드오프: summary 생성 비용(추가 처리 시간/LLM 사용 시 비용)과 저장 공간 증가. 초기에는 규칙 기반(헤더/첫 문단/리스트)으로 경량 운영 후, 필요 시 LLM 요약로 전환 권장.
