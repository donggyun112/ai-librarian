# 클라우드 기반 MultiVectorRetriever 전환 가이드

본 문서는 현재 `embedding.py` 파이프라인을 LangChain의 `MultiVectorRetriever`로 전환하고, 클라우드 문서 저장소(DocStore)와 함께 사용하는 방법을 정리합니다. 목표는 개발자 친화적인 표준 리트리버를 사용하면서도, 기존 `PGVector`/메타데이터/인덱스 설계를 최대한 재활용하는 것입니다.

## 변경 사항 요약

- 자식 청크 저장: 그대로 `PGVector` 사용(텍스트 `view="text"`, 코드 `view="code"`, `lang`, `parent_id` 유지)
- 부모 문서 저장: 유닛(`unit_id`=`parent_id`)별 대표 콘텐츠를 생성해 “클라우드 DocStore”에 저장
- 리트리버: `MultiVectorRetriever(vectorstore=PGVector, docstore=<cloud>, id_key="parent_id")`

## 환경 변수 제안

- 공통
  - `RETRIEVER_MODE=multivector`
  - `DOCSTORE_BACKEND=redis|upstash|s3`
- Redis(표준)
  - `REDIS_URL`, 필요 시 `REDIS_PASSWORD`
- Upstash Redis
  - `UPSTASH_REDIS_URL`, `UPSTASH_REDIS_TOKEN`
- S3
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
  - `S3_BUCKET`, `S3_PREFIX=parent-docs/`

## 인제스트 단계: 부모 문서 생성/저장

`embedding.py`에서 청크(`build_document_from_unitized`)를 만든 뒤, `parent_id`(= `unit_id`) 기준으로 그룹핑하여 “부모 문서”를 한 개씩 생성합니다.

```python
from collections import defaultdict
from langchain_core.documents import Document

# docs: build_document_from_unitized() 결과(List[Document])
groups = defaultdict(list)
for d in docs:
    pid = d.metadata.get("parent_id") or d.metadata.get("unit_id")
    if not pid:
        continue
    groups[pid].append(d)

parent_entries = []  # list[(key, bytes)]
for pid, childs in groups.items():
    # 대표 텍스트 구성: pre_text 우선, 없으면 text 뷰 상위 1~2개 사용
    pre_texts = [c.page_content for c in childs if c.metadata.get("unit_role") == "pre_text"]
    if not pre_texts:
        pre_texts = [c.page_content for c in childs if c.metadata.get("view") == "text"]
    parent_text = "\n\n".join(pre_texts[:2])[:2000] or f"unit {pid}"
    parent_entries.append((pid, parent_text.encode("utf-8")))

# 이후: parent_entries를 선택한 클라우드 DocStore에 저장(mset)
```

권장: 부모 문서는 1~2KB 내로 간결하게 만들어 검색/표시 성능을 확보합니다.

## 클라우드 DocStore 선택지

아래 저장소는 모두 바이트 기반 mset/get을 지원합니다. 간단히 UTF-8 바이트로 저장/복원하거나, 필요 시 JSON 직렬화를 사용하세요.

### Upstash Redis

```python
import os
from langchain_community.storage import UpstashRedisByteStore

docstore = UpstashRedisByteStore(
    url=os.environ["UPSTASH_REDIS_URL"],
    token=os.environ["UPSTASH_REDIS_TOKEN"],
    ttl=None,  # 필요 시 TTL 적용
)
docstore.mset(parent_entries)  # [(key, bytes), ...]
```

### 표준 Redis

```python
import os
from langchain_community.storage import RedisStore

# namespace로 키 충돌을 방지
docstore = RedisStore.from_url(os.environ["REDIS_URL"], namespace="parent_docs")
# RedisStore는 값에 bytes를 지원(버전별 차이가 있으면 ByteStore를 사용)
docstore.mset(parent_entries)
```

### S3

```python
import os
from langchain_community.storage import S3Store

prefix = os.getenv("S3_PREFIX", "parent-docs/")
docstore = S3Store(bucket=os.environ["S3_BUCKET"], prefix=prefix)
# S3Store는 키에 prefix를 포함해 저장
s3_entries = [(f"{prefix}{k}", v) for (k, v) in parent_entries]
docstore.mset(s3_entries)
```

## MultiVectorRetriever 구성

```python
import os
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_voyageai import VoyageAIEmbeddings
from langchain_postgres import PGVector

emb = VoyageAIEmbeddings(model=os.getenv("VOYAGE_MODEL", "voyage-3"))
vectorstore = PGVector(
    connection=os.environ["PG_CONN"],
    collection_name=os.environ["COLLECTION_NAME"],
    embeddings=emb,
    distance_strategy="COSINE",
    use_jsonb=True,
    embedding_length=int(os.getenv("EMBEDDING_DIM", "1024")),
)

retriever = MultiVectorRetriever(
    vectorstore=vectorstore,
    docstore=docstore,     # 위에서 생성한 클라우드 DocStore
    id_key="parent_id",   # 메타 키: 이미 청크 메타에 존재
    search_kwargs={"k": 8},
)
```

## 사용 예시

- 텍스트 중심 검색

```python
retriever.search_kwargs = {"k": 5, "filter": {"view": "text"}}
parents = retriever.get_relevant_documents("쿼리")
```

- 파이썬 코드 중심 검색

```python
retriever.search_kwargs = {"k": 8, "filter": {"view": "code", "lang": "python"}}
parents = retriever.get_relevant_documents("비동기 파일 처리 예시")
```

- 멀티뷰(기본): 자식(텍스트/코드) 검색 후 `parent_id`로 중복 제거된 부모 문서 반환

```python
parents = retriever.get_relevant_documents("파일 업로드 처리 흐름")
```

## 기존 파이프라인과의 정합성/이행 전략

- 유지: `PGVector` 저장, 메타(`parent_id`, `unit_id`, `view`, `lang`, `order`) 및 인덱스(`ensure_indexes`)는 그대로 유지
- 추가: 인제스트 시 부모 문서 생성/클라우드 저장 단계만 추가
- 점진 전환: 기존 질의 코드에서 `store.similarity_search`를 사용하던 부분을 `retriever.get_relevant_documents`로 치환

## 주의사항(보안/운영)

- 보안: 자격증명은 환경 변수/시크릿 매니저로 주입, 코드에 하드코딩 금지. Redis TLS/S3 SSE 등 전송·저장 암호화 적용
- 지속성: InMemoryStore는 운영용이 아님. Redis/S3 같은 지속 저장소 사용
- 직렬화: 나중에 부모 문서에 메타데이터를 포함하려면 `Document`를 JSON으로 직렬화해 바이트로 저장/복원
- 품질: 부모 문서 콘텐츠 전략(요약/헤더/대표 문단)을 팀 기준으로 정해 재현성/일관성을 확보

---

필요 시 `retriever`/`docstore` 빌더 유틸과 인제스트 훅(부모 생성)을 코드에 추가하는 패치를 제공할 수 있습니다.
