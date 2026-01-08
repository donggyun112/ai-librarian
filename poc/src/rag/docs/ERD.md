# OCR Vector DB - Entity Relationship Diagram

> 마지막 갱신: 2026-01-04

---

## 1. 도메인 엔티티 관계도 (Domain Model)

```mermaid
erDiagram
    Document ||--o{ Concept : "contains (1:N)"
    Concept ||--o{ Fragment : "contains (1:N)"
    Fragment ||--o| Embedding : "has (1:0..1)"

    Document {
        string id PK "MD5(source_path)"
        string source_path "파일 경로"
        datetime created_at "생성 시각"
        json metadata "추가 메타데이터"
    }

    Concept {
        string id PK "MD5(document_id + unit_id)"
        string document_id FK "Document 참조 (HIER-002)"
        int order "문서 내 순서"
        string content "부모 맥락 텍스트"
        json metadata "추가 메타데이터"
    }

    Fragment {
        string id PK "MD5 기반"
        string concept_id FK "Concept 참조 (HIER-003)"
        string content "실제 텍스트"
        enum view "text|code|image|table|figure|caption"
        string language "python|javascript|null"
        int order "Concept 내 순서"
        json metadata "추가 메타데이터"
    }

    Embedding {
        string doc_id PK "hash(parent_id+view+lang+content)"
        string fragment_id FK "Fragment 참조 (EMBED-OWN-001)"
        vector vector "768/1024 차원"
        json metadata "검색용 메타데이터"
    }
```

---

## 2. 데이터베이스 물리 스키마 (Physical Schema)

```mermaid
erDiagram
    langchain_pg_collection ||--o{ langchain_pg_embedding : "contains"
    docstore_parent ||--o{ langchain_pg_embedding : "provides context"

    langchain_pg_collection {
        uuid uuid PK
        string name UK "컬렉션 이름"
        json cmetadata "컬렉션 메타데이터"
    }

    langchain_pg_embedding {
        uuid id PK
        uuid collection_id FK
        vector embedding "768/1024 dim, HNSW indexed"
        string document "Fragment 콘텐츠"
        json cmetadata "검색/필터용 메타데이터"
        datetime created_at
    }

    docstore_parent {
        string id PK "Concept ID"
        string content "부모 맥락 텍스트"
        json metadata "document_id, order 등"
        datetime created_at
        datetime updated_at
    }
```

---

## 3. 메타데이터 구조 (cmetadata JSONB)

```mermaid
erDiagram
    langchain_pg_embedding ||--|| cmetadata : "contains"

    cmetadata {
        string fragment_id "Fragment 식별자"
        string parent_id "Concept ID (맥락 확장 키)"
        string doc_id "결정적 ID (중복 방지)"
        string view "text|code|image|..."
        string lang "python|javascript|kor|..."
        string source "원본 파일명"
        int order "Fragment 순서"
        string unit_id "의미 단위 ID"
        string unit_role "pre_text|python|javascript|..."
    }
```

---

## 4. 검색 파이프라인 데이터 흐름

```mermaid
flowchart LR
    subgraph Ingestion["입수 (Ingestion)"]
        A[파일] --> B[RawSegment]
        B --> C[UnitizedSegment]
        C --> D[Concept + Fragment]
    end

    subgraph Storage["저장 (Storage)"]
        D --> E[langchain_pg_embedding]
        D --> F[docstore_parent]
    end

    subgraph Retrieval["검색 (Retrieval)"]
        G[쿼리] --> H[QueryPlan]
        H --> I[VectorSearch]
        I --> J[SearchResult]
        J --> K[ContextExpander]
        K --> L[ExpandedResult]
    end

    E --> I
    F --> K
```

---

## 5. 계층 구조 및 CASCADE 삭제

```mermaid
flowchart TD
    subgraph Hierarchy["엔티티 계층"]
        DOC[Document] --> CON[Concept]
        CON --> FRAG[Fragment]
        FRAG --> EMB[Embedding]
    end

    subgraph Cascade["CASCADE 삭제 규칙"]
        DOC -.->|CASCADE-001| CON
        CON -.->|CASCADE-002| FRAG
        FRAG -.->|CASCADE-003| EMB
    end

    subgraph Rules["도메인 규칙"]
        R1[HIER-002: Concept → Document]
        R2[HIER-003: Fragment → Concept]
        R3[EMBED-OWN-001: Embedding → Fragment]
    end
```

---

## 6. Multi-View 관계

```mermaid
erDiagram
    Concept ||--o{ Fragment_Text : "has"
    Concept ||--o{ Fragment_Code : "has"
    Concept ||--o{ Fragment_Image : "has"

    Concept {
        string id PK
        string content "합성된 부모 맥락"
    }

    Fragment_Text {
        string id PK
        string view "text"
        string content "자연어 설명"
    }

    Fragment_Code {
        string id PK
        string view "code"
        string language "python|javascript"
        string content "코드 블록"
    }

    Fragment_Image {
        string id PK
        string view "image"
        string content "alt 텍스트 + URL"
    }
```

---

## 7. 인덱스 구조

```mermaid
flowchart LR
    subgraph Indexes["langchain_pg_embedding 인덱스"]
        HNSW[HNSW Vector Index<br/>vector_cosine_ops]
        GIN[GIN Index<br/>cmetadata JSONB]
        BTREE1[BTREE<br/>parent_id]
        BTREE2[BTREE<br/>view]
        BTREE3[BTREE<br/>lang]
    end

    subgraph Query["쿼리 최적화"]
        Q1[유사도 검색] --> HNSW
        Q2[메타데이터 필터] --> GIN
        Q3[컨텍스트 확장] --> BTREE1
        Q4[뷰 필터링] --> BTREE2
        Q5[언어 필터링] --> BTREE3
    end
```

---

## 8. 규칙 ID 매핑

| 엔티티 관계 | 규칙 ID | 설명 |
|------------|---------|------|
| Document ← Concept | HIER-002 | 모든 Concept은 정확히 하나의 Document에 귀속 |
| Concept ← Fragment | HIER-003 | 모든 Fragment는 유효한 concept_id 필수 |
| Fragment ← Embedding | EMBED-OWN-001 | 모든 Embedding은 정확히 하나의 Fragment에 귀속 |
| Fragment.view | FRAG-VIEW-001 | View는 속성이지 독립 엔티티가 아님 |
| Embedding.doc_id | EMBED-ID-002 | doc_id = hash(parent_id + view + lang + content) |
| Fragment.content | FRAG-LEN-001 | 10자 미만은 임베딩 불가 |

---

## 부록: Mermaid 렌더링 방법

이 문서의 다이어그램은 [Mermaid](https://mermaid.js.org/) 문법으로 작성되었습니다.

**렌더링 방법:**
- GitHub: 자동 렌더링 지원
- VS Code: [Markdown Preview Mermaid Support](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid) 확장
- 온라인: [Mermaid Live Editor](https://mermaid.live/)
- Obsidian: 기본 지원
