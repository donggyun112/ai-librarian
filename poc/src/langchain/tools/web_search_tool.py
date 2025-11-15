"""
LangChain tool for web search.
"""

from typing import Dict, List, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class WebSearchInput(BaseModel):
    """Input schema for web search tool."""
    query: str = Field(description="Search query for web search")
    max_results: int = Field(default=5, description="Maximum number of search results")
    focus_recent: bool = Field(default=True, description="Focus on recent/current information")


class WebSearchTool(BaseTool):
    """LangChain tool for web searching."""
    
    name: str = "web_search"
    description: str = """
    Search the web for current, recent, or trending information.
    Use this tool when you need:
    - Latest news or updates
    - Current events and trends
    - Recent developments in technology or industry
    - Time-sensitive information
    
    Input should be a specific query about recent or current topics.
    """
    args_schema: type[BaseModel] = WebSearchInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Note: In a real implementation, you would initialize actual web search API here
        # For now, we'll simulate web search results
        
    def _run(self, query: str, max_results: int = 5, focus_recent: bool = True) -> Dict[str, Any]:
        """Execute web search."""
        try:
            logger.info(f"Executing web search for query: {query[:50]}...")
            
            # Optimize query for web search
            optimized_query = self._optimize_search_query(query, focus_recent)
            
            # Simulate web search (in real implementation, use actual search API)
            search_results = self._simulate_web_search(optimized_query, max_results)
            
            if not search_results:
                return {
                    "success": False,
                    "message": "No web search results found",
                    "results": [],
                    "total_results": 0
                }
            
            logger.info(f"Web search completed: {len(search_results)} results found")
            
            return {
                "success": True,
                "results": search_results,
                "total_results": len(search_results),
                "query": query,
                "optimized_query": optimized_query,
                "search_metadata": {
                    "max_results": max_results,
                    "focus_recent": focus_recent,
                    "search_timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            return {
                "success": False,
                "message": f"Web search error: {str(e)}",
                "results": [],
                "total_results": 0
            }
    
    def _optimize_search_query(self, query: str, focus_recent: bool) -> str:
        """Optimize search query for better web search results."""
        optimized = query.strip()
        
        # Add temporal keywords if focusing on recent info
        if focus_recent:
            temporal_keywords = ['최근', '최신', '2024', '현재', 'latest', 'recent', 'current']
            has_temporal = any(keyword in query.lower() for keyword in temporal_keywords)
            
            if not has_temporal:
                if any(char in query for char in '가-힣'):  # Korean text
                    optimized = f"{optimized} 최신 2024"
                else:  # English text
                    optimized = f"{optimized} latest 2024"
        
        return optimized
    
    def _simulate_web_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Simulate web search results (replace with actual search API in production)."""
        
        # Detect time-sensitive keywords
        time_sensitive_keywords = ['최근', '최신', '2024', '현재', 'latest', 'recent', 'current', '트렌드', 'trend']
        is_time_sensitive = any(keyword in query.lower() for keyword in time_sensitive_keywords)
        
        # Simulate different types of results based on query
        if is_time_sensitive:
            results = [
                {
                    "title": f"최신 {query} 동향 및 트렌드 분석",
                    "url": "https://example-tech-news.com/latest-trends",
                    "snippet": f"{query}에 대한 2024년 최신 동향을 분석한 결과, 주요 발전사항과 향후 전망을 제시합니다.",
                    "date": "2024-12-01",
                    "source": "TechNews",
                    "relevance_score": 0.9
                },
                {
                    "title": f"2024년 {query} 주요 업데이트",
                    "url": "https://example-industry.com/updates-2024",
                    "snippet": f"올해 {query} 분야에서 일어난 주요 변화와 업데이트 사항을 정리했습니다.",
                    "date": "2024-11-28",
                    "source": "Industry Report",
                    "relevance_score": 0.85
                }
            ]
        else:
            results = [
                {
                    "title": f"{query} 완벽 가이드",
                    "url": "https://example-guide.com/complete-guide",
                    "snippet": f"{query}에 대한 포괄적인 설명과 실제 활용 방법을 다룹니다.",
                    "date": "2024-10-15",
                    "source": "Expert Guide",
                    "relevance_score": 0.8
                },
                {
                    "title": f"{query} 심화 분석",
                    "url": "https://example-analysis.com/deep-dive",
                    "snippet": f"{query}의 원리와 메커니즘을 상세히 분석한 전문 자료입니다.",
                    "date": "2024-09-20",
                    "source": "Research Paper",
                    "relevance_score": 0.75
                }
            ]
        
        # Add more generic results
        for i in range(len(results), max_results):
            results.append({
                "title": f"{query} 관련 정보 #{i+1}",
                "url": f"https://example-source{i+1}.com/info",
                "snippet": f"{query}에 대한 추가 정보와 관련 내용을 제공합니다.",
                "date": "2024-11-01",
                "source": f"Source {i+1}",
                "relevance_score": max(0.5, 0.9 - i * 0.1)
            })
        
        return results[:max_results]
    
    async def _arun(self, query: str, max_results: int = 5, focus_recent: bool = True) -> Dict[str, Any]:
        """Async execution (fallback to sync for now)."""
        return self._run(query, max_results, focus_recent)