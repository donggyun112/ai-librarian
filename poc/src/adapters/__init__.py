"""LLM Adapters - 프로바이더별 차이점 캡슐화"""
from .base import BaseLLMAdapter, NormalizedChunk, ToolChoiceType
from .openai import OpenAIAdapter
from .gemini import GeminiAdapter

# 프로바이더 이름 → Adapter 클래스 매핑
ADAPTER_REGISTRY: dict[str, type[BaseLLMAdapter]] = {
    "openai": OpenAIAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(provider: str) -> BaseLLMAdapter:
    """프로바이더 이름으로 Adapter 인스턴스 반환

    Args:
        provider: 프로바이더 이름 ("openai", "gemini")

    Returns:
        해당 프로바이더의 Adapter 인스턴스

    Raises:
        ValueError: 지원하지 않는 프로바이더
    """
    adapter_cls = ADAPTER_REGISTRY.get(provider.lower())
    if adapter_cls is None:
        supported = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(f"Unknown provider: {provider}. Supported: {supported}")
    return adapter_cls()


__all__ = [
    "BaseLLMAdapter",
    "NormalizedChunk",
    "ToolChoiceType",
    "OpenAIAdapter",
    "GeminiAdapter",
    "get_adapter",
    "ADAPTER_REGISTRY",
]
