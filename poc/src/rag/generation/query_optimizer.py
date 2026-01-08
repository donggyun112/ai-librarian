"""Query optimization using LLM for better retrieval.

Extracts keywords and hints from user queries to improve search relevance.
Uses keyword-based approach instead of HyDE for better term matching.

.. deprecated::
    QueryOptimizer is deprecated. Use ``retrieval.SelfQueryRetrieverWrapper`` instead,
    which provides automatic metadata filter extraction from natural language queries.
"""

import json
import re
import warnings
from typing import Optional

from .client import LLMClientProtocol
from .models import OptimizedQuery
from .prompts import PromptTemplate

# Emit deprecation warning on import
warnings.warn(
    "QueryOptimizer is deprecated. Use retrieval.SelfQueryRetrieverWrapper instead "
    "for automatic metadata filter extraction.",
    DeprecationWarning,
    stacklevel=2,
)




class QueryOptimizer:
    """LLM-based query optimizer for improved retrieval.

    Extracts keywords and view/language hints from user queries
    to improve search relevance. Uses keyword-based approach
    instead of HyDE (Hypothetical Document Embeddings).

    Benefits over HyDE:
    - Exact term matching (API names, function names)
    - Automatic view/language filtering
    - Single LLM call (faster)
    - Better for technical documentation

    Example:
        >>> optimizer = QueryOptimizer(llm_client)
        >>> result = optimizer.optimize("How do I use Python decorators?")
        >>> print(result.keywords)  # ["Python", "decorators", "function"]
        >>> print(result.view_hint)  # "code"
        >>> print(result.language_hint)  # "python"
    """

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        *,
        temperature: float = 0.1,  # Low temperature for consistent extraction
        fallback_on_error: bool = True,
    ):
        """Initialize QueryOptimizer.

        Args:
            llm_client: LLM client for keyword extraction
            temperature: Generation temperature (low for consistency)
            fallback_on_error: Use fallback parsing on LLM errors
        """
        self.llm_client = llm_client
        self.temperature = temperature
        self.fallback_on_error = fallback_on_error

    def optimize(self, query: str) -> OptimizedQuery:
        """Optimize query for retrieval.

        Extracts keywords, view hints, and language hints from the query.

        Args:
            query: User's natural language query

        Returns:
            OptimizedQuery with extracted information
        """
        # Try LLM-based extraction
        try:
            prompt = PromptTemplate.format_keyword_prompt(query)
            response = self.llm_client.generate(
                prompt=prompt,
                temperature=self.temperature,
                max_tokens=256,
            )

            # Parse JSON response
            parsed = self._parse_response(response.content)
            if parsed:
                keywords = parsed.get("keywords", [])
                view_hint = parsed.get("view")
                language_hint = parsed.get("language")

                # Validate view hint
                if view_hint not in ("code", "text", None):
                    view_hint = None

                return OptimizedQuery(
                    original=query,
                    keywords=keywords,
                    rewritten=self._build_search_query(query, keywords),
                    view_hint=view_hint,
                    language_hint=language_hint,
                )

        except Exception as e:
            print(f"[optimizer] LLM extraction failed: {e}")

        # Fallback to simple keyword extraction
        if self.fallback_on_error:
            return self._fallback_optimize(query)

        # Return original query as-is
        return OptimizedQuery(
            original=query,
            keywords=[],
            rewritten=query,
        )

    def _parse_response(self, content: str) -> Optional[dict]:
        """Parse LLM response as JSON.

        Args:
            content: LLM response text

        Returns:
            Parsed dict or None if parsing fails
        """
        # Try to extract JSON from response
        content = content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        # Try direct JSON parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in text
        match = re.search(r"\{[^}]+\}", content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _build_search_query(self, original: str, keywords: list) -> str:
        """Build optimized search query from keywords.

        Args:
            original: Original query
            keywords: Extracted keywords

        Returns:
            Search-optimized query string (keywords only for better embedding match)
        """
        if not keywords:
            return original

        # Use keywords ONLY for embedding (shorter = better similarity)
        # Original query was too long and hurt similarity scores
        return " ".join(keywords)

    def _fallback_optimize(self, query: str) -> OptimizedQuery:
        """Simple keyword extraction fallback.

        Uses basic heuristics when LLM extraction fails.

        Args:
            query: User query

        Returns:
            OptimizedQuery with basic extraction
        """
        # Simple stopword removal for Korean and English
        stopwords = {
            # English
            "what", "how", "why", "when", "where", "which",
            "is", "are", "was", "were", "be", "been",
            "do", "does", "did", "can", "could", "should", "would",
            "the", "a", "an", "to", "of", "in", "for", "on", "with",
            "i", "you", "me", "my", "we", "our",
            # Korean
            "??, "媛", "??, "瑜?, "?", "??, "??, "?먯꽌", "濡?, "?쇰줈",
            "?", "怨?, "??, "??, "留?, "源뚯?", "遺??,
            "臾댁뾿", "?대뼸寃?, "??, "?몄젣", "?대뵒",
        }

        # Extract words
        words = re.findall(r"[a-zA-Z媛-??+", query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 1]

        # Detect view hint
        view_hint = None
        code_indicators = ["code", "function", "class", "method", "implement",
                          "肄붾뱶", "?⑥닔", "?대옒??, "硫붿꽌??, "援ы쁽"]
        text_indicators = ["explain", "what", "concept", "mean",
                          "?ㅻ챸", "媛쒕뀗", "??, "?섎?"]

        query_lower = query.lower()
        if any(ind in query_lower for ind in code_indicators):
            view_hint = "code"
        elif any(ind in query_lower for ind in text_indicators):
            view_hint = "text"

        # Detect language hint
        language_hint = None
        language_patterns = {
            "python": ["python", "?뚯씠??, "py"],
            "javascript": ["javascript", "?먮컮?ㅽ겕由쏀듃", "js", "node"],
            "java": ["java", "?먮컮"],
            "typescript": ["typescript", "??낆뒪?щ┰??, "ts"],
            "go": ["golang", "go?몄뼱"],
            "rust": ["rust", "?ъ뒪??],
        }
        for lang, patterns in language_patterns.items():
            if any(p in query_lower for p in patterns):
                language_hint = lang
                break

        return OptimizedQuery(
            original=query,
            keywords=keywords[:5],  # Top 5 keywords
            rewritten=query,
            view_hint=view_hint,
            language_hint=language_hint,
        )


__all__ = ["QueryOptimizer"]
