"""
Web Search Tool

Provides real web search capabilities for the Gatherer agent.
Supports multiple search API backends with graceful fallback:
1. Serper (SERPER_API_KEY) — Google search results
2. Tavily (TAVILY_API_KEY) — AI-optimized search
3. Empty fallback with warning

Usage:
    from src.tools.web_search import WebSearchTool

    search = WebSearchTool()
    results = await search.search("AI Safety research 2025", num_results=5)
    # Returns: [{"title": ..., "url": ..., "snippet": ...}, ...]
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str
    source: str = ""  # Which search API returned this


class WebSearchTool:
    """
    Web search tool with multi-provider support.

    Checks for API keys in order: Serper → Tavily → empty fallback.
    """

    def __init__(self):
        self.serper_key = os.environ.get("SERPER_API_KEY")
        self.tavily_key = os.environ.get("TAVILY_API_KEY")

        if self.serper_key:
            self._provider = "serper"
        elif self.tavily_key:
            self._provider = "tavily"
        else:
            self._provider = "none"
            logger.warning(
                "[WebSearch] No search API key found. Set SERPER_API_KEY or TAVILY_API_KEY "
                "for real web search. Falling back to empty results."
            )

    @property
    def available(self) -> bool:
        return self._provider != "none"

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the web for a query.

        Args:
            query: Search query string
            num_results: Number of results to return (default 5)

        Returns:
            List of dicts with keys: title, url, snippet
        """
        if self._provider == "serper":
            return await self._search_serper(query, num_results)
        elif self._provider == "tavily":
            return await self._search_tavily(query, num_results)
        else:
            logger.warning(f"[WebSearch] No search provider available for query: {query[:50]}")
            return []

    async def _search_serper(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Search using Serper.dev (Google Search API)."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": self.serper_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "q": query,
                        "num": num_results
                    }
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("organic", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "serper"
                })

            logger.info(f"[WebSearch/Serper] Got {len(results)} results for: {query[:50]}")
            return results

        except Exception as e:
            logger.error(f"[WebSearch/Serper] Failed: {e}")
            # Try Tavily as fallback if available
            if self.tavily_key:
                logger.info("[WebSearch] Falling back to Tavily")
                return await self._search_tavily(query, num_results)
            return []

    async def _search_tavily(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Search using Tavily AI search API."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_key,
                        "query": query,
                        "max_results": num_results,
                        "search_depth": "basic"
                    }
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:300],
                    "source": "tavily"
                })

            logger.info(f"[WebSearch/Tavily] Got {len(results)} results for: {query[:50]}")
            return results

        except Exception as e:
            logger.error(f"[WebSearch/Tavily] Failed: {e}")
            return []
