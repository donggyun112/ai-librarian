"""Tests for QueryOptimizerProtocol and implementations.

Tests:
- NoOpQueryOptimizer basic functionality
- SelfQueryRetrieverWrapper.optimize() method
- Protocol compliance
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from src.rag.retrieval import (
    NoOpQueryOptimizer,
    OptimizedQueryResult,
    QueryOptimizerProtocol,
    SelfQueryRetrieverWrapper,
)


class TestNoOpQueryOptimizer:
    """Test NoOpQueryOptimizer (fallback implementation)."""

    def test_optimize_returns_original_query(self) -> None:
        """Test that NoOpQueryOptimizer returns original query unchanged."""
        optimizer = NoOpQueryOptimizer()
        query = "test query"

        result = optimizer.optimize(query)

        assert isinstance(result, OptimizedQueryResult)
        assert result.original_query == query
        assert result.rewritten_query is None
        assert result.view_filter is None
        assert result.language_filter is None
        assert result.metadata_filters is None

    def test_effective_query_returns_original(self) -> None:
        """Test that effective_query returns original when no rewrite."""
        optimizer = NoOpQueryOptimizer()
        query = "python decorators"

        result = optimizer.optimize(query)

        assert result.effective_query == query

    def test_protocol_compliance(self) -> None:
        """Test that NoOpQueryOptimizer implements QueryOptimizerProtocol."""
        optimizer = NoOpQueryOptimizer()

        # Should have optimize method
        assert hasattr(optimizer, "optimize")
        assert callable(optimizer.optimize)

        # Should match protocol signature
        result = optimizer.optimize("test")
        assert isinstance(result, OptimizedQueryResult)


class TestSelfQueryRetrieverWrapperOptimize:
    """Test SelfQueryRetrieverWrapper.optimize() method."""

    @pytest.fixture
    def mock_wrapper(self):
        """Create a mock SelfQueryRetrieverWrapper for testing."""
        with patch('src.rag.retrieval.self_query.SelfQueryRetriever'):
            mock_vectorstore = MagicMock()
            mock_llm = MagicMock()

            wrapper = SelfQueryRetrieverWrapper(
                vectorstore=mock_vectorstore,
                llm=mock_llm,
                verbose=False,
            )
            return wrapper

    def test_optimize_with_no_filters(self, mock_wrapper) -> None:
        """Test optimize when no filters are extracted."""
        # Mock query constructor to return no filters
        mock_structured_query = MagicMock()
        mock_structured_query.query = "rewritten query"
        mock_structured_query.filter = None

        mock_wrapper.retriever.query_constructor.invoke = MagicMock(return_value=mock_structured_query)

        result = mock_wrapper.optimize("test query")

        assert isinstance(result, OptimizedQueryResult)
        assert result.original_query == "test query"
        assert result.rewritten_query == "rewritten query"
        assert result.view_filter is None
        assert result.language_filter is None
        assert result.metadata_filters is None

    def test_optimize_with_view_filter(self, mock_wrapper) -> None:
        """Test optimize when view filter is extracted."""
        # Mock query constructor to return view filter
        mock_filter = MagicMock()
        mock_filter.attribute = "view"
        mock_filter.value = "code"

        mock_structured_query = MagicMock()
        mock_structured_query.query = "code examples"
        mock_structured_query.filter = mock_filter

        mock_wrapper.retriever.query_constructor.invoke = MagicMock(return_value=mock_structured_query)

        result = mock_wrapper.optimize("show me code")

        assert result.original_query == "show me code"
        assert result.rewritten_query == "code examples"
        assert result.view_filter == "code"

    def test_optimize_with_language_filter(self, mock_wrapper) -> None:
        """Test optimize when language filter is extracted."""
        # Mock query constructor to return lang filter
        mock_filter = MagicMock()
        mock_filter.attribute = "lang"
        mock_filter.value = "python"

        mock_structured_query = MagicMock()
        mock_structured_query.query = "python examples"
        mock_structured_query.filter = mock_filter

        mock_wrapper.retriever.query_constructor.invoke = MagicMock(return_value=mock_structured_query)

        result = mock_wrapper.optimize("python code")

        assert result.language_filter == "python"

    def test_optimize_with_multiple_filters(self, mock_wrapper) -> None:
        """Test optimize when multiple filters are extracted."""
        # Create simple object mocks that only have the necessary attributes
        class SimpleFilter:
            def __init__(self, attribute, value):
                self.attribute = attribute
                self.value = value

        class SimpleOperation:
            def __init__(self, operator, arguments):
                self.operator = operator
                self.arguments = arguments

        # Mock query constructor to return multiple filters
        mock_view_filter = SimpleFilter("view", "code")
        mock_lang_filter = SimpleFilter("lang", "python")

        mock_operation = SimpleOperation("and", [mock_view_filter, mock_lang_filter])

        mock_structured_query = MagicMock()
        mock_structured_query.query = "python code"
        mock_structured_query.filter = mock_operation

        mock_wrapper.retriever.query_constructor.invoke = MagicMock(return_value=mock_structured_query)

        result = mock_wrapper.optimize("show python code")

        assert result.view_filter == "code"
        assert result.language_filter == "python"

    def test_optimize_handles_exception(self, mock_wrapper) -> None:
        """Test optimize handles exceptions gracefully."""
        # Mock query constructor to raise exception
        mock_wrapper.retriever.query_constructor.invoke = MagicMock(
            side_effect=Exception("LLM error")
        )

        result = mock_wrapper.optimize("test query")

        # Should return result with no optimization
        assert result.original_query == "test query"
        assert result.rewritten_query is None
        assert result.view_filter is None

    def test_effective_query_uses_rewritten(self, mock_wrapper) -> None:
        """Test that effective_query uses rewritten query when available."""
        mock_structured_query = MagicMock()
        mock_structured_query.query = "rewritten"
        mock_structured_query.filter = None

        mock_wrapper.retriever.query_constructor.invoke = MagicMock(return_value=mock_structured_query)

        result = mock_wrapper.optimize("original")

        assert result.effective_query == "rewritten"


class TestProtocolCompliance:
    """Test protocol compliance for query optimizers."""

    def test_noop_implements_protocol(self) -> None:
        """Test NoOpQueryOptimizer implements QueryOptimizerProtocol."""
        optimizer = NoOpQueryOptimizer()

        # Check protocol compliance
        assert isinstance(optimizer, object)  # All Python objects
        assert hasattr(optimizer, "optimize")
        assert callable(optimizer.optimize)

        # Test signature
        result = optimizer.optimize("test")
        assert isinstance(result, OptimizedQueryResult)

    def test_self_query_wrapper_implements_protocol(self) -> None:
        """Test SelfQueryRetrieverWrapper implements QueryOptimizerProtocol."""
        with patch('src.rag.retrieval.self_query.SelfQueryRetriever'):
            mock_vectorstore = MagicMock()
            mock_llm = MagicMock()

            wrapper = SelfQueryRetrieverWrapper(
                vectorstore=mock_vectorstore,
                llm=mock_llm,
                verbose=False,
            )

            # Check protocol compliance
            assert hasattr(wrapper, "optimize")
            assert callable(wrapper.optimize)

            # Mock query constructor
            mock_structured_query = MagicMock()
            mock_structured_query.query = None
            mock_structured_query.filter = None
            wrapper.retriever.query_constructor.invoke = MagicMock(return_value=mock_structured_query)

            # Test signature
            result = wrapper.optimize("test")
            assert isinstance(result, OptimizedQueryResult)


class TestOptimizedQueryResult:
    """Test OptimizedQueryResult DTO."""

    def test_effective_query_with_rewrite(self) -> None:
        """Test effective_query returns rewritten when available."""
        result = OptimizedQueryResult(
            original_query="original",
            rewritten_query="rewritten",
        )

        assert result.effective_query == "rewritten"

    def test_effective_query_without_rewrite(self) -> None:
        """Test effective_query returns original when no rewrite."""
        result = OptimizedQueryResult(
            original_query="original",
        )

        assert result.effective_query == "original"

    def test_all_fields_populated(self) -> None:
        """Test OptimizedQueryResult with all fields."""
        result = OptimizedQueryResult(
            original_query="original",
            rewritten_query="rewritten",
            view_filter="code",
            language_filter="python",
            metadata_filters={"custom": "value"},
        )

        assert result.original_query == "original"
        assert result.rewritten_query == "rewritten"
        assert result.view_filter == "code"
        assert result.language_filter == "python"
        assert result.metadata_filters == {"custom": "value"}
