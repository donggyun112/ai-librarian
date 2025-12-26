"""RAG 워커 - 벡터 검색 기반"""
from typing import List
from langchain_openai import OpenAIEmbeddings
from pymilvus import MilvusClient

from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker
from config import config


class RAGWorker(BaseWorker):
    """벡터 DB 검색을 수행하는 워커"""

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL,
            api_key=config.OPENAI_API_KEY
        )
        self.client = MilvusClient(
            uri=config.MILVUS_HOST,
            token=config.MILVUS_TOKEN
        )
        self.collection_name = config.MILVUS_COLLECTION
        self.top_k = 5
        self.score_threshold = 0.7

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.RAG

    async def execute(self, query: str) -> WorkerResult:
        """벡터 검색 실행"""
        try:
            # 1. 쿼리 임베딩 생성
            query_embedding = await self.embeddings.aembed_query(query)

            # 2. Milvus 검색
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=self.top_k,
                output_fields=["text", "source", "metadata"]
            )

            if not results or not results[0]:
                return self._create_result(
                    query=query,
                    content="관련 문서를 찾지 못했습니다.",
                    confidence=0.0,
                    sources=[]
                )

            # 3. 결과 정리
            documents = []
            sources = []
            total_score = 0.0

            for hit in results[0]:
                score = hit.get("distance", 0)
                if score >= self.score_threshold:
                    text = hit.get("entity", {}).get("text", "")
                    source = hit.get("entity", {}).get("source", "unknown")
                    documents.append(f"- {text}")
                    sources.append(source)
                    total_score += score

            if not documents:
                return self._create_result(
                    query=query,
                    content="신뢰도 높은 문서를 찾지 못했습니다.",
                    confidence=0.3,
                    sources=[]
                )

            avg_score = total_score / len(documents)
            content = "\n".join(documents)

            return self._create_result(
                query=query,
                content=content,
                confidence=min(avg_score, 1.0),
                sources=list(set(sources))
            )

        except Exception as e:
            return self._create_result(
                query=query,
                content="",
                success=False,
                error=f"RAG 검색 실패: {str(e)}"
            )
