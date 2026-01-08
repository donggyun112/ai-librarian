# Package Rules

> 이 문서는 OCR 기반 문서 인텔리전스 & 벡터 검색 시스템의 **패키지 수준 규칙집**입니다.
> `DOMAIN_RULES.md`의 도메인 규칙을 물리적으로 강제하기 위한 구조적 제약을 정의합니다.

---

## 1. 문서 목적

### 1.1 Python에서 패키지 규칙이 필요한 이유

Python은 컴파일 타임에 의존성 방향을 검증하지 않는다. 따라서:

- 순환 의존성이 런타임까지 발견되지 않을 수 있다
- 도메인 레이어가 인프라스트럭처에 의존하는 위반이 쉽게 발생한다
- 코드 리뷰 없이는 아키텍처 드리프트를 감지하기 어렵다

이 문서는 **물리적 경계**를 정의하여 이러한 문제를 사전에 방지한다.

### 1.2 DOMAIN_RULES.md와의 관계

| 문서 | 역할 |
|------|------|
| `DOMAIN_RULES.md` | 도메인 불변식(invariant)을 정의 |
| `PACKAGE_RULES.md` | 도메인 불변식을 물리적 패키지 구조로 강제 |

**관계**: `DOMAIN_RULES.md`의 규칙이 "무엇을 해야 하는가"를 정의한다면, 이 문서는 "어디서 해야 하는가"를 정의한다.

### 1.3 위반 시 조치

이 문서의 규칙을 위반하는 구현은 **아키텍처 리뷰 대상**이다.

위반 유형:
- 금지된 패키지 import
- 잘못된 책임 배치
- 순환 의존성 도입

---

## 2. 최상위 패키지 구조

### 2.1 패키지 개요

```
project_root/
├── domain/       # 순수 도메인 엔티티
├── ingestion/    # 파일 파싱 및 세그먼테이션
├── embedding/    # 임베딩 생성 및 관리
├── retrieval/    # 검색 및 맥락 조립
├── storage/      # 저장소 추상화 및 구현
├── api/          # 외부 인터페이스 (CLI, REST)
└── shared/       # 공통 유틸리티 및 예외
```

### 2.2 패키지별 요약

| 패키지 | 책임 | 도메인 규칙 연관 |
|--------|------|------------------|
| `domain` | 순수 엔티티 정의 | HIER-*, FRAG-* |
| `ingestion` | 파일 → Concept/Fragment 변환 | ANTI-CHUNK-* |
| `embedding` | 벡터 생성, doc_id 계산 | EMBED-*, EMBED-ID-* |
| `retrieval` | 검색 파이프라인, 맥락 조립 | SEARCH-* |
| `storage` | 영속성, 리포지토리 패턴 | CASCADE-*, INVAL-* |
| `api` | CLI/REST 진입점 | - |
| `shared` | 공통 타입, 예외, 유틸리티 | - |

---

## 3. 패키지별 규칙

### 3.1 domain 패키지

#### 책임

| 규칙 ID | 규칙 |
|---------|------|
| PKG-DOM-001 | `domain`은 순수 도메인 엔티티만 정의해야 한다 (MUST) |
| PKG-DOM-002 | `domain`은 Document, Concept, Fragment, Embedding 엔티티를 포함해야 한다 (MUST) |
| PKG-DOM-003 | `domain`은 View 타입 정의를 포함해야 한다 (MUST) |
| PKG-DOM-004 | `domain`은 엔티티 간 관계(parent_id 등)를 정의해야 한다 (MUST) |

#### 금지 사항

| 규칙 ID | 규칙 |
|---------|------|
| PKG-DOM-BAN-001 | `domain`은 데이터베이스 연결 로직을 포함해서는 안 된다 (MUST NOT) |
| PKG-DOM-BAN-002 | `domain`은 외부 API 호출을 포함해서는 안 된다 (MUST NOT) |
| PKG-DOM-BAN-003 | `domain`은 파일 I/O를 수행해서는 안 된다 (MUST NOT) |
| PKG-DOM-BAN-004 | `domain`은 설정(configuration) 로딩을 수행해서는 안 된다 (MUST NOT) |

#### 금지된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-DOM-001 | `domain`은 프로젝트 내 다른 패키지를 import해서는 안 된다 (MUST NOT) |
| DEP-DOM-002 | `domain`은 `shared`만 예외적으로 import할 수 있다 (MAY) |
| DEP-DOM-003 | `domain`은 외부 인프라 라이브러리(sqlalchemy, langchain 등)를 import해서는 안 된다 (MUST NOT) |

---

### 3.2 ingestion 패키지

#### 책임

| 규칙 ID | 규칙 |
|---------|------|
| PKG-ING-001 | `ingestion`은 파일 파싱 로직을 담당해야 한다 (MUST) |
| PKG-ING-002 | `ingestion`은 RawSegment → UnitizedSegment 변환을 수행해야 한다 (MUST) |
| PKG-ING-003 | `ingestion`은 View 감지(text, code, image)를 수행해야 한다 (MUST) |
| PKG-ING-004 | `ingestion`은 Concept 경계 결정 로직을 포함해야 한다 (MUST) |

#### 금지 사항

| 규칙 ID | 규칙 |
|---------|------|
| PKG-ING-BAN-001 | `ingestion`은 임베딩 생성을 수행해서는 안 된다 (MUST NOT) |
| PKG-ING-BAN-002 | `ingestion`은 데이터베이스 저장을 직접 수행해서는 안 된다 (MUST NOT) |
| PKG-ING-BAN-003 | `ingestion`은 검색 로직을 포함해서는 안 된다 (MUST NOT) |

#### 금지된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-ING-001 | `ingestion`은 `embedding`을 import해서는 안 된다 (MUST NOT) |
| DEP-ING-002 | `ingestion`은 `retrieval`을 import해서는 안 된다 (MUST NOT) |
| DEP-ING-003 | `ingestion`은 `storage`를 import해서는 안 된다 (MUST NOT) |
| DEP-ING-004 | `ingestion`은 `api`를 import해서는 안 된다 (MUST NOT) |

#### 허용된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-ING-ALLOW-001 | `ingestion`은 `domain`을 import할 수 있다 (MAY) |
| DEP-ING-ALLOW-002 | `ingestion`은 `shared`를 import할 수 있다 (MAY) |

---

### 3.3 embedding 패키지

#### 책임

| 규칙 ID | 규칙 |
|---------|------|
| PKG-EMB-001 | `embedding`은 벡터 임베딩 생성을 담당해야 한다 (MUST) |
| PKG-EMB-002 | `embedding`은 결정적 doc_id 생성 로직을 포함해야 한다 (MUST) |
| PKG-EMB-003 | `embedding`은 임베딩 프로바이더 추상화를 제공해야 한다 (MUST) |
| PKG-EMB-004 | `embedding`은 최소 길이 검증을 수행해야 한다 (MUST) |
| PKG-EMB-005 | `embedding`은 중복 임베딩 검사를 수행해야 한다 (SHOULD) |

#### 금지 사항

| 규칙 ID | 규칙 |
|---------|------|
| PKG-EMB-BAN-001 | `embedding`은 파일 파싱을 수행해서는 안 된다 (MUST NOT) |
| PKG-EMB-BAN-002 | `embedding`은 검색 로직을 포함해서는 안 된다 (MUST NOT) |
| PKG-EMB-BAN-003 | `embedding`은 데이터베이스 스키마 관리를 수행해서는 안 된다 (MUST NOT) |

#### 금지된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-EMB-001 | `embedding`은 `ingestion`을 import해서는 안 된다 (MUST NOT) |
| DEP-EMB-002 | `embedding`은 `retrieval`을 import해서는 안 된다 (MUST NOT) |
| DEP-EMB-003 | `embedding`은 `api`를 import해서는 안 된다 (MUST NOT) |

#### 허용된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-EMB-ALLOW-001 | `embedding`은 `domain`을 import할 수 있다 (MAY) |
| DEP-EMB-ALLOW-002 | `embedding`은 `shared`를 import할 수 있다 (MAY) |
| DEP-EMB-ALLOW-003 | `embedding`은 `storage`의 리포지토리 인터페이스를 import할 수 있다 (MAY) |

---

### 3.4 retrieval 패키지

#### 책임

| 규칙 ID | 규칙 |
|---------|------|
| PKG-RET-001 | `retrieval`은 검색 파이프라인을 담당해야 한다 (MUST) |
| PKG-RET-002 | `retrieval`은 쿼리 해석 로직을 포함해야 한다 (MUST) |
| PKG-RET-003 | `retrieval`은 맥락 확장(Context Expansion) 로직을 포함해야 한다 (MUST) |
| PKG-RET-004 | `retrieval`은 검색 결과 그룹화를 수행해야 한다 (SHOULD) |
| PKG-RET-005 | `retrieval`은 리랭킹 로직을 포함할 수 있다 (MAY) |

#### 금지 사항

| 규칙 ID | 규칙 |
|---------|------|
| PKG-RET-BAN-001 | `retrieval`은 임베딩 생성을 수행해서는 안 된다 (MUST NOT) |
| PKG-RET-BAN-002 | `retrieval`은 파일 파싱을 수행해서는 안 된다 (MUST NOT) |
| PKG-RET-BAN-003 | `retrieval`은 데이터베이스 스키마를 직접 조작해서는 안 된다 (MUST NOT) |

#### 금지된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-RET-001 | `retrieval`은 `ingestion`을 import해서는 안 된다 (MUST NOT) |
| DEP-RET-002 | `retrieval`은 `api`를 import해서는 안 된다 (MUST NOT) |

#### 허용된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-RET-ALLOW-001 | `retrieval`은 `domain`을 import할 수 있다 (MAY) |
| DEP-RET-ALLOW-002 | `retrieval`은 `storage`를 import할 수 있다 (MAY) |
| DEP-RET-ALLOW-003 | `retrieval`은 `embedding`의 임베딩 클라이언트를 import할 수 있다 (MAY) |
| DEP-RET-ALLOW-004 | `retrieval`은 `shared`를 import할 수 있다 (MAY) |

---

### 3.5 storage 패키지

#### 책임

| 규칙 ID | 규칙 |
|---------|------|
| PKG-STO-001 | `storage`는 리포지토리 인터페이스를 정의해야 한다 (MUST) |
| PKG-STO-002 | `storage`는 데이터베이스 스키마 관리를 담당해야 한다 (MUST) |
| PKG-STO-003 | `storage`는 연쇄 삭제(CASCADE) 로직을 구현해야 한다 (MUST) |
| PKG-STO-004 | `storage`는 트랜잭션 관리를 담당해야 한다 (MUST) |

#### 금지 사항

| 규칙 ID | 규칙 |
|---------|------|
| PKG-STO-BAN-001 | `storage`는 도메인 규칙을 강제해서는 안 된다 (MUST NOT) |
| PKG-STO-BAN-002 | `storage`는 임베딩 생성을 수행해서는 안 된다 (MUST NOT) |
| PKG-STO-BAN-003 | `storage`는 검색 로직을 포함해서는 안 된다 (MUST NOT) |
| PKG-STO-BAN-004 | `storage`는 파일 파싱을 수행해서는 안 된다 (MUST NOT) |

#### 금지된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-STO-001 | `storage`는 `ingestion`을 import해서는 안 된다 (MUST NOT) |
| DEP-STO-002 | `storage`는 `embedding`을 import해서는 안 된다 (MUST NOT) |
| DEP-STO-003 | `storage`는 `retrieval`을 import해서는 안 된다 (MUST NOT) |
| DEP-STO-004 | `storage`는 `api`를 import해서는 안 된다 (MUST NOT) |

#### 허용된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-STO-ALLOW-001 | `storage`는 `domain`을 import할 수 있다 (MAY) |
| DEP-STO-ALLOW-002 | `storage`는 `shared`를 import할 수 있다 (MAY) |

---

### 3.6 api 패키지

#### 책임

| 규칙 ID | 규칙 |
|---------|------|
| PKG-API-001 | `api`는 외부 인터페이스(CLI, REST)를 제공해야 한다 (MUST) |
| PKG-API-002 | `api`는 요청 검증을 수행해야 한다 (MUST) |
| PKG-API-003 | `api`는 응답 포맷팅을 담당해야 한다 (MUST) |
| PKG-API-004 | `api`는 다른 패키지를 조합(orchestrate)하여 유스케이스를 구현해야 한다 (MUST) |

#### 금지 사항

| 규칙 ID | 규칙 |
|---------|------|
| PKG-API-BAN-001 | `api`는 비즈니스 로직을 직접 구현해서는 안 된다 (MUST NOT) |
| PKG-API-BAN-002 | `api`는 데이터베이스에 직접 접근해서는 안 된다 (MUST NOT) |
| PKG-API-BAN-003 | `api`는 도메인 엔티티를 정의해서는 안 된다 (MUST NOT) |

#### 금지된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-API-001 | `api`는 `shared`의 내부 구현을 직접 import해서는 안 된다 (SHOULD NOT) |

#### 허용된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-API-ALLOW-001 | `api`는 `domain`을 import할 수 있다 (MAY) |
| DEP-API-ALLOW-002 | `api`는 `ingestion`을 import할 수 있다 (MAY) |
| DEP-API-ALLOW-003 | `api`는 `embedding`을 import할 수 있다 (MAY) |
| DEP-API-ALLOW-004 | `api`는 `retrieval`을 import할 수 있다 (MAY) |
| DEP-API-ALLOW-005 | `api`는 `storage`를 import할 수 있다 (MAY) |
| DEP-API-ALLOW-006 | `api`는 `shared`의 공개 인터페이스를 import할 수 있다 (MAY) |

---

### 3.7 shared 패키지

#### 책임

| 규칙 ID | 규칙 |
|---------|------|
| PKG-SHA-001 | `shared`는 공통 예외 클래스를 정의해야 한다 (MUST) |
| PKG-SHA-002 | `shared`는 공통 타입 힌트를 정의할 수 있다 (MAY) |
| PKG-SHA-003 | `shared`는 순수 유틸리티 함수를 포함할 수 있다 (MAY) |
| PKG-SHA-004 | `shared`는 설정(configuration) 로딩을 담당할 수 있다 (MAY) |

#### 금지 사항

| 규칙 ID | 규칙 |
|---------|------|
| PKG-SHA-BAN-001 | `shared`는 도메인 엔티티를 정의해서는 안 된다 (MUST NOT) |
| PKG-SHA-BAN-002 | `shared`는 비즈니스 로직을 포함해서는 안 된다 (MUST NOT) |
| PKG-SHA-BAN-003 | `shared`는 데이터베이스 접근을 수행해서는 안 된다 (MUST NOT) |

#### 금지된 Import

| 규칙 ID | 규칙 |
|---------|------|
| DEP-SHA-001 | `shared`는 프로젝트 내 다른 패키지를 import해서는 안 된다 (MUST NOT) |
| DEP-SHA-002 | `shared`는 `domain`을 import해서는 안 된다 (MUST NOT) |

---

## 4. 의존성 방향 규칙

### 4.1 허용된 의존성 흐름

```
                    ┌─────────┐
                    │   api   │
                    └────┬────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────┐    ┌──────────┐    ┌───────────┐
    │ingestion│    │embedding │    │ retrieval │
    └────┬────┘    └────┬─────┘    └─────┬─────┘
         │              │                │
         │              │                │
         │              ▼                │
         │         ┌─────────┐           │
         │         │ storage │◄──────────┘
         │         └────┬────┘
         │              │
         ▼              ▼
    ┌─────────────────────────┐
    │         domain          │
    └───────────┬─────────────┘
                │
                ▼
    ┌─────────────────────────┐
    │         shared          │
    └─────────────────────────┘
```

### 4.2 의존성 방향 규칙 요약

| 규칙 ID | 규칙 |
|---------|------|
| DEP-DIR-001 | 의존성은 항상 상위 레이어에서 하위 레이어로만 흘러야 한다 (MUST) |
| DEP-DIR-002 | `domain`은 최하위 레이어로, 다른 패키지에 의존해서는 안 된다 (MUST NOT) |
| DEP-DIR-003 | `shared`는 `domain`보다 더 하위 레이어다 (MUST) |
| DEP-DIR-004 | `api`는 최상위 레이어로, 모든 패키지를 조합할 수 있다 (MAY) |

### 4.3 금지된 역방향 의존성

| 규칙 ID | 규칙 |
|---------|------|
| DEP-REV-001 | `domain` → 다른 패키지: 금지 (FORBIDDEN) |
| DEP-REV-002 | `shared` → 다른 패키지: 금지 (FORBIDDEN) |
| DEP-REV-003 | `storage` → `api`: 금지 (FORBIDDEN) |
| DEP-REV-004 | `storage` → `retrieval`: 금지 (FORBIDDEN) |
| DEP-REV-005 | `ingestion` → `embedding`: 금지 (FORBIDDEN) |
| DEP-REV-006 | `ingestion` → `retrieval`: 금지 (FORBIDDEN) |

### 4.4 순환 의존성 금지

| 규칙 ID | 규칙 |
|---------|------|
| DEP-CYC-001 | 패키지 간 순환 의존성은 금지된다 (FORBIDDEN) |
| DEP-CYC-002 | 모듈 간 순환 의존성은 금지된다 (FORBIDDEN) |
| DEP-CYC-003 | 순환 의존성이 발견되면 즉시 수정해야 한다 (MUST) |

---

## 5. 금지된 구조적 안티패턴

### 5.1 domain이 인프라를 import

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-STRUCT-001 | `domain`에서 SQLAlchemy, LangChain 등 인프라 라이브러리를 import하는 것은 금지된다 (FORBIDDEN) |
| ANTI-STRUCT-002 | `domain`에서 `storage`, `embedding`, `ingestion`을 import하는 것은 금지된다 (FORBIDDEN) |

**위반 예시**: `domain/models.py`에서 `from sqlalchemy import Column` 사용

### 5.2 api에 비즈니스 로직 포함

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-STRUCT-003 | `api`에서 임베딩 생성, 검색 알고리즘, 파싱 로직을 직접 구현하는 것은 금지된다 (FORBIDDEN) |
| ANTI-STRUCT-004 | `api`는 다른 패키지의 함수를 호출하여 유스케이스를 조합해야 한다 (MUST) |

**위반 예시**: `api/endpoints.py`에서 직접 벡터 유사도 계산 수행

### 5.3 storage가 도메인 규칙을 강제

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-STRUCT-005 | `storage`에서 도메인 불변식(예: 최소 길이 검증)을 검사하는 것은 금지된다 (FORBIDDEN) |
| ANTI-STRUCT-006 | 도메인 규칙 검증은 `domain` 또는 해당 책임 패키지에서 수행해야 한다 (MUST) |

**위반 예시**: `storage/repository.py`에서 `if len(content) < 10: raise` 검사

### 5.4 ingestion이 임베딩을 생성

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-STRUCT-007 | `ingestion`에서 임베딩 API를 호출하는 것은 금지된다 (FORBIDDEN) |
| ANTI-STRUCT-008 | 파싱 → 임베딩은 별도 단계로 분리되어야 한다 (MUST) |

**위반 예시**: `ingestion/parsers.py`에서 `embeddings.embed()` 호출

### 5.5 retrieval이 파일을 직접 읽음

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-STRUCT-009 | `retrieval`에서 파일 I/O를 수행하는 것은 금지된다 (FORBIDDEN) |
| ANTI-STRUCT-010 | 검색 대상은 이미 저장된 Fragment이어야 한다 (MUST) |

**위반 예시**: `retrieval/search.py`에서 `open('file.pdf')` 호출

---

## 6. 규칙 집행 용어

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
| PKG-DOM | domain 패키지 책임 규칙 |
| PKG-ING | ingestion 패키지 책임 규칙 |
| PKG-EMB | embedding 패키지 책임 규칙 |
| PKG-RET | retrieval 패키지 책임 규칙 |
| PKG-STO | storage 패키지 책임 규칙 |
| PKG-API | api 패키지 책임 규칙 |
| PKG-SHA | shared 패키지 책임 규칙 |
| PKG-*-BAN | 패키지별 금지 규칙 |
| DEP-* | 의존성 규칙 |
| DEP-*-ALLOW | 허용된 의존성 |
| DEP-DIR | 의존성 방향 규칙 |
| DEP-REV | 역방향 의존성 금지 규칙 |
| DEP-CYC | 순환 의존성 규칙 |
| ANTI-STRUCT | 구조적 안티패턴 규칙 |

---

## 부록 B: 도메인 규칙 매핑

이 문서의 패키지 규칙이 `DOMAIN_RULES.md`의 어떤 규칙을 물리적으로 강제하는지 매핑한다.

| 도메인 규칙 | 패키지 규칙 | 강제 방법 |
|-------------|-------------|-----------|
| HIER-001~004 | PKG-DOM-001~004 | `domain`에 엔티티 정의 격리 |
| EMBED-ID-001~004 | PKG-EMB-002 | `embedding`에 doc_id 로직 격리 |
| FRAG-LEN-001~003 | PKG-EMB-004 | `embedding`에서 최소 길이 검증 |
| SEARCH-SEP-001~004 | PKG-RET-001~003 | `retrieval`에 검색 로직 격리 |
| CASCADE-001~004 | PKG-STO-003 | `storage`에 연쇄 삭제 구현 |
| ANTI-CHUNK-001~002 | PKG-ING-001~004 | `ingestion`에 의미 단위 파싱 격리 |

---

## 부록 C: 설계 리뷰 트리거

다음 상황에서는 **반드시 설계 리뷰**를 수행해야 한다 (MUST):

1. 새로운 패키지 추가 시
2. 패키지 간 의존성 추가/변경 시
3. 패키지 책임 변경 시
4. 이 문서의 규칙 변경 시

---

*이 문서는 DOMAIN_RULES.md를 물리적으로 강제하기 위한 패키지 수준 규칙집입니다.*
*규칙 위반 시 아키텍처 리뷰가 필요합니다.*
