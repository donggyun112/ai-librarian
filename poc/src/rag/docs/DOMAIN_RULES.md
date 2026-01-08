# Domain Rules

> 이 문서는 OCR 기반 문서 인텔리전스 & 벡터 검색 시스템의 **도메인 규칙집**입니다.
> 모든 구현, 리팩토링, 코딩 에이전트는 이 규칙을 엄격히 준수해야 합니다.

---

## 1. 문서 목적

### 1.1 이 문서가 존재하는 이유

이 문서는 아키텍처 드리프트(architectural drift)를 방지하기 위해 존재한다.

`ARCHITECTURE.md`가 시스템의 설계 철학과 구조를 정의한다면, 이 문서는 그 설계를 **강제하는 규칙**만을 명시한다.

### 1.2 위반 시 조치

이 문서의 규칙을 위반하는 구현은 **아키텍처 리뷰 대상**이다.

위반이 발견될 경우:
- 해당 구현은 즉시 수정되어야 한다
- 규칙 자체를 변경해야 하는 경우, 아키텍처 리뷰를 거쳐야 한다

---

## 2. 핵심 엔티티 계층 규칙

### 2.1 엔티티 계층 구조

시스템의 모든 데이터는 다음 계층을 따른다:

```
Document → Concept → Fragment → Embedding
```

- **Document**: 시스템에 입력되는 최상위 단위 (파일)
- **Concept**: 의미적으로 응집된 정보 단위 (Semantic Parent)
- **Fragment**: Concept을 구성하는 개별 정보 조각 (Child)
- **Embedding**: Fragment 또는 Concept의 벡터 표현

### 2.2 소유권 규칙

| 규칙 ID | 규칙 |
|---------|------|
| HIER-001 | Fragment는 반드시 정확히 하나의 Concept에 귀속되어야 한다 (MUST) |
| HIER-002 | Concept은 반드시 정확히 하나의 Document에 귀속되어야 한다 (MUST) |
| HIER-003 | 모든 Fragment는 유효한 `parent_id`를 가져야 한다 (MUST) |
| HIER-004 | `parent_id`는 Fragment 생성 시점에 확정되며 이후 변경되어서는 안 된다 (MUST NOT) |

### 2.3 고아 엔티티 금지

| 규칙 ID | 규칙 |
|---------|------|
| ORPHAN-001 | 고아 엔티티(orphan entity)는 존재해서는 안 된다 (MUST NOT) |
| ORPHAN-002 | 소유권 체인이 끊어진 임베딩은 무효화 대상이다 (MUST) |
| ORPHAN-003 | `parent_id`가 존재하지 않는 Concept을 참조하는 Fragment는 허용되지 않는다 (MUST NOT) |

---

## 3. 임베딩 규칙

### 3.1 임베딩 대상

| 엔티티 | 임베딩 여부 | 규칙 |
|--------|-------------|------|
| Document | NO | Document는 임베딩되어서는 안 된다 (MUST NOT) |
| Concept | CONDITIONAL | 대표 임베딩은 선택적으로 생성할 수 있다 (MAY) |
| Fragment | YES | 최소 길이 조건을 충족하는 Fragment는 임베딩되어야 한다 (MUST) |
| Metadata | NO | 메타데이터는 임베딩되어서는 안 된다 (MUST NOT) |

### 3.2 임베딩 금지 대상

다음은 **절대로 임베딩되어서는 안 된다** (MUST NOT):

| 규칙 ID | 금지 대상 | 이유 |
|---------|-----------|------|
| EMBED-BAN-001 | 파일 경로 및 메타데이터 | 의미적 검색 대상이 아님 |
| EMBED-BAN-002 | 10자 미만의 짧은 텍스트 | 의미적 표현력 부족 |
| EMBED-BAN-003 | 반복되는 보일러플레이트 | 검색 결과 오염 |
| EMBED-BAN-004 | 페이지 번호, 헤더, 푸터 | 문서 구조 정보일 뿐 내용 아님 |
| EMBED-BAN-005 | 이미 임베딩된 동일 콘텐츠 | 중복 방지 |
| EMBED-BAN-006 | 순수 참조 정보 ("그림 3 참조" 등) | 실질적 의미 없음 |

### 3.3 임베딩 소유권

| 규칙 ID | 규칙 |
|---------|------|
| EMBED-OWN-001 | 모든 임베딩은 정확히 하나의 Fragment에 귀속되어야 한다 (MUST) |
| EMBED-OWN-002 | 소유권 체인 `Embedding → Fragment → Concept → Document`가 항상 존재해야 한다 (MUST) |
| EMBED-OWN-003 | 체인이 끊어진 임베딩은 고아(orphan)로 간주하여 정리해야 한다 (MUST) |

### 3.4 결정적 ID 생성

| 규칙 ID | 규칙 |
|---------|------|
| EMBED-ID-001 | 임베딩 ID는 콘텐츠 기반으로 결정적(deterministic)으로 생성되어야 한다 (MUST) |
| EMBED-ID-002 | `doc_id = hash(parent_id + view + lang + content)` 형식을 따라야 한다 (MUST) |
| EMBED-ID-003 | 랜덤 ID 생성은 금지된다 (MUST NOT) |
| EMBED-ID-004 | 동일 콘텐츠는 항상 동일 ID를 가져야 한다 (MUST) |

### 3.5 중복 임베딩 방지

| 규칙 ID | 규칙 |
|---------|------|
| EMBED-DUP-001 | 임베딩 저장 전 `doc_id` 중복 검사를 수행해야 한다 (SHOULD) |
| EMBED-DUP-002 | `content_hash`로 콘텐츠 동일성을 검증해야 한다 (SHOULD) |
| EMBED-DUP-003 | 중복 임베딩이 감지되면 기존 임베딩을 유지하고 새 임베딩을 폐기해야 한다 (MUST) |

---

## 4. Fragment 규칙

### 4.1 Fragment 소유권

| 규칙 ID | 규칙 |
|---------|------|
| FRAG-OWN-001 | Fragment는 반드시 하나의 Concept에 소속되어야 한다 (MUST) |
| FRAG-OWN-002 | `parent_id`는 필수 속성이다 (MUST) |
| FRAG-OWN-003 | `parent_id`가 없는 Fragment는 생성되어서는 안 된다 (MUST NOT) |

### 4.2 View는 속성이다

| 규칙 ID | 규칙 |
|---------|------|
| FRAG-VIEW-001 | View(text, code, image)는 Fragment의 속성이다, 독립 엔티티가 아니다 (MUST) |
| FRAG-VIEW-002 | View를 최상위 엔티티로 취급하는 구현은 금지된다 (MUST NOT) |
| FRAG-VIEW-003 | 동일 Concept 내 여러 View의 Fragment가 공존할 수 있다 (MAY) |
| FRAG-VIEW-004 | View는 Fragment 생성 시 결정되며 이후 변경되어서는 안 된다 (MUST NOT) |

### 4.3 최소 길이 규칙

| 규칙 ID | 규칙 |
|---------|------|
| FRAG-LEN-001 | 임베딩 대상 Fragment는 최소 10자 이상이어야 한다 (MUST) |
| FRAG-LEN-002 | 최소 길이 미달 Fragment는 임베딩에서 제외해야 한다 (MUST) |
| FRAG-LEN-003 | 최소 길이 미달 Fragment는 저장은 가능하나 검색 대상이 되어서는 안 된다 (MUST NOT) |

### 4.4 parent_id 불변성

| 규칙 ID | 규칙 |
|---------|------|
| FRAG-IMMUT-001 | Fragment 생성 시점에 `parent_id`가 확정된다 (MUST) |
| FRAG-IMMUT-002 | 생성 후 `parent_id` 변경은 금지된다 (MUST NOT) |
| FRAG-IMMUT-003 | `parent_id` 변경이 필요한 경우, 기존 Fragment를 삭제하고 새 Fragment를 생성해야 한다 (MUST) |

---

## 5. 검색 및 맥락 규칙

### 5.1 검색 대상과 맥락 제공자의 분리

| 규칙 ID | 규칙 |
|---------|------|
| SEARCH-SEP-001 | 검색 대상(Fragment 임베딩)과 맥락 제공자(Parent 문서)는 분리되어야 한다 (MUST) |
| SEARCH-SEP-002 | 검색: Fragment 임베딩을 대상으로 한다 (MUST) |
| SEARCH-SEP-003 | 맥락: Parent 문서에서 제공한다 (MUST) |
| SEARCH-SEP-004 | 두 역할을 혼용하는 구현은 금지된다 (MUST NOT) |

### 5.2 검색 결과 구성

| 규칙 ID | 규칙 |
|---------|------|
| SEARCH-RES-001 | 검색 결과는 반드시 맥락과 함께 반환되어야 한다 (MUST) |
| SEARCH-RES-002 | Parent 문서 없이 Fragment만 반환하는 것은 금지된다 (MUST NOT) |
| SEARCH-RES-003 | 동일 Concept의 Fragment가 여러 개 검색된 경우 그룹화해야 한다 (SHOULD) |

### 5.3 설명 가능한 검색

| 규칙 ID | 규칙 |
|---------|------|
| SEARCH-EXPL-001 | 검색 결과에는 출처(source) 정보가 포함되어야 한다 (MUST) |
| SEARCH-EXPL-002 | 검색 결과에는 위치(location) 정보가 포함되어야 한다 (MUST) |
| SEARCH-EXPL-003 | 검색 결과에는 유형(view) 정보가 포함되어야 한다 (MUST) |
| SEARCH-EXPL-004 | "왜 이 결과가 검색되었는가"를 답할 수 있어야 한다 (SHOULD) |

### 5.4 단순 Top-K 연결 금지

| 규칙 ID | 규칙 |
|---------|------|
| SEARCH-TOPK-001 | 검색 결과를 단순히 Top-K 형태로 평면 나열하는 것은 지양해야 한다 (SHOULD NOT) |
| SEARCH-TOPK-002 | Concept 단위 그룹화 또는 맥락 확장이 적용되어야 한다 (SHOULD) |

---

## 6. 무효화 및 생명주기 규칙

### 6.1 즉시 무효화 트리거

다음 상황에서는 관련 임베딩을 **즉시 무효화해야 한다** (MUST):

| 규칙 ID | 트리거 | 무효화 범위 |
|---------|--------|-------------|
| INVAL-001 | Fragment의 `page_content` 변경 | 해당 Fragment의 임베딩 |
| INVAL-002 | Concept 삭제 | 해당 Concept의 모든 Fragment 임베딩 |
| INVAL-003 | Document 삭제 | 해당 Document의 모든 Concept 및 Fragment 임베딩 |

### 6.2 연쇄 삭제 규칙

| 규칙 ID | 규칙 |
|---------|------|
| CASCADE-001 | Document 삭제 시 모든 하위 Concept이 연쇄 삭제되어야 한다 (MUST) |
| CASCADE-002 | Concept 삭제 시 모든 하위 Fragment가 연쇄 삭제되어야 한다 (MUST) |
| CASCADE-003 | Fragment 삭제 시 해당 임베딩이 연쇄 삭제되어야 한다 (MUST) |
| CASCADE-004 | 연쇄 삭제 후 고아 엔티티가 남아서는 안 된다 (MUST NOT) |

### 6.3 무효화가 필요 없는 경우

다음 변경은 임베딩 무효화를 트리거하지 **않는다**:

| 규칙 ID | 변경 유형 | 이유 |
|---------|-----------|------|
| NO-INVAL-001 | Concept 내 다른 Fragment 변경 | 각 Fragment는 독립 |
| NO-INVAL-002 | 타임스탬프만 변경 | doc_id 계산에 미포함 |
| NO-INVAL-003 | 비검색용 메타데이터 변경 | 임베딩에 영향 없음 |

**주의**: `view`, `lang`, `parent_id` 변경은 `doc_id` 계산에 포함되므로 무효화를 트리거한다.

---

## 7. 금지된 안티패턴

다음 패턴은 **명시적으로 금지된다** (FORBIDDEN):

### 7.1 청크 우선 설계 (Chunk-First Design)

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-CHUNK-001 | 의미 경계를 무시하고 고정 크기로 문서를 분할하는 것은 금지된다 (MUST NOT) |
| ANTI-CHUNK-002 | 의미 단위를 먼저 식별하고, 그 후에 필요시 청킹해야 한다 (MUST) |

### 7.2 모든 것을 임베딩 (Embed Everything)

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-EMBED-001 | 저장된 모든 텍스트를 무조건 임베딩하는 것은 금지된다 (MUST NOT) |
| ANTI-EMBED-002 | 임베딩 대상은 명시적 규칙에 따라 선별되어야 한다 (MUST) |

### 7.3 View를 엔티티로 혼동 (View-as-Entity Confusion)

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-VIEW-001 | text, code, image를 독립적인 최상위 엔티티로 취급하는 것은 금지된다 (MUST NOT) |
| ANTI-VIEW-002 | View는 Fragment의 속성으로만 취급해야 한다 (MUST) |

### 7.4 Parent를 단순 연결로 취급 (Parent as Mere Concatenation)

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-PARENT-001 | Parent 문서를 Child 텍스트의 단순 이어붙이기로 구현하는 것은 지양해야 한다 (SHOULD NOT) |
| ANTI-PARENT-002 | Parent는 의미적 요약 또는 맥락 정보를 포함해야 한다 (SHOULD) |

### 7.5 메타데이터를 임베딩에 포함 (Metadata in Embedding)

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-META-001 | 파일 경로, 타임스탬프 등 메타데이터를 임베딩 텍스트에 포함하는 것은 금지된다 (MUST NOT) |
| ANTI-META-002 | 메타데이터는 구조화 필터링으로만 사용해야 한다 (MUST) |

### 7.6 계층 구조 무시 (Flat Embedding Space)

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-FLAT-001 | 모든 Fragment를 동등한 수준의 평면적 엔티티로 취급하는 것은 금지된다 (MUST NOT) |
| ANTI-FLAT-002 | 계층 구조(parent_id)를 유지하고 활용해야 한다 (MUST) |

---

## 8. 규칙 집행 용어

이 문서는 RFC 2119 스타일의 키워드를 사용한다:

| 키워드 | 의미 |
|--------|------|
| **MUST** | 절대적 요구사항. 반드시 준수해야 한다 |
| **MUST NOT** | 절대적 금지. 절대로 해서는 안 된다 |
| **SHOULD** | 강력히 권장. 예외적 상황에서만 무시 가능 |
| **SHOULD NOT** | 강력히 지양. 예외적 상황에서만 허용 |
| **MAY** | 선택적. 구현자의 재량에 따름 |
| **FORBIDDEN** | 명시적 금지. MUST NOT과 동의어 |

---

## 부록 A: 규칙 ID 체계

| 접두사 | 카테고리 |
|--------|----------|
| HIER | 엔티티 계층 규칙 |
| ORPHAN | 고아 엔티티 규칙 |
| EMBED | 임베딩 규칙 |
| FRAG | Fragment 규칙 |
| SEARCH | 검색 규칙 |
| INVAL | 무효화 규칙 |
| CASCADE | 연쇄 삭제 규칙 |
| NO-INVAL | 무효화 예외 규칙 |
| ANTI | 안티패턴 금지 규칙 |

---

## 부록 B: 설계 리뷰 트리거

다음 상황에서는 **반드시 설계 리뷰**를 수행해야 한다 (MUST):

1. 새로운 엔티티 유형 추가 시
2. 임베딩 대상 변경 시
3. 소유권 체인 변경 시
4. 검색 파이프라인 구조 변경 시
5. 저장 스키마 변경 시
6. 이 문서의 규칙 변경 시

---

*이 문서는 ARCHITECTURE.md를 기반으로 추출된 도메인 규칙집입니다.*
*규칙 위반 시 아키텍처 리뷰가 필요합니다.*
