"""LLM Adapter 베이스 클래스"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel


@dataclass
class NormalizedChunk:
    """정규화된 스트리밍 청크

    모든 LLM 프로바이더의 청크를 통일된 형식으로 변환
    """
    text: str


class BaseLLMAdapter(ABC):
    """LLM Adapter 추상 베이스 클래스

    각 LLM 프로바이더별 차이점을 캡슐화:
    - LLM 인스턴스 생성 방식
    - 스트리밍 청크 형식 정규화
    - 인스턴스 재사용 전략 (캐싱 vs 매번 생성)
    """

    @abstractmethod
    def create_llm(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> BaseChatModel:
        """LLM 인스턴스 생성

        Args:
            model: 모델명
            temperature: 샘플링 온도
            max_tokens: 최대 토큰 수

        Returns:
            LangChain BaseChatModel 인스턴스
        """
        pass

    @abstractmethod
    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """스트리밍 청크를 정규화된 형식으로 변환

        Args:
            chunk: LLM에서 받은 원본 청크 (AIMessageChunk)

        Returns:
            정규화된 청크
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """프로바이더 이름 (로깅/디버깅용)"""
        pass
