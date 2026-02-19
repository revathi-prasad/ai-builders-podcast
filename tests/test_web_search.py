"""Tests for the web search tool."""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.tools.web_search import WebSearchTool


class TestWebSearchTool:
    def test_no_api_key_unavailable(self):
        """Without API keys, search should not be available."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove any existing keys
            env = {k: v for k, v in os.environ.items()
                   if k not in ("SERPER_API_KEY", "TAVILY_API_KEY")}
            with patch.dict(os.environ, env, clear=True):
                tool = WebSearchTool()
                assert not tool.available

    def test_serper_key_detected(self):
        """With SERPER_API_KEY, search should be available."""
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tool = WebSearchTool()
            assert tool.available
            assert tool._provider == "serper"

    def test_tavily_key_detected(self):
        """With TAVILY_API_KEY only, Tavily should be used."""
        env = {k: v for k, v in os.environ.items() if k != "SERPER_API_KEY"}
        env["TAVILY_API_KEY"] = "test_key"
        with patch.dict(os.environ, env, clear=True):
            tool = WebSearchTool()
            assert tool.available
            assert tool._provider == "tavily"

    @pytest.mark.asyncio
    async def test_search_without_key_returns_empty(self):
        """Search without API key should return empty results."""
        with patch.dict(os.environ, {}, clear=True):
            env = {k: v for k, v in os.environ.items()
                   if k not in ("SERPER_API_KEY", "TAVILY_API_KEY")}
            with patch.dict(os.environ, env, clear=True):
                tool = WebSearchTool()
                results = await tool.search("test query")
                assert results == []

    @pytest.mark.asyncio
    async def test_serper_search_mocked(self):
        """Test Serper search with mocked HTTP response."""
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tool = WebSearchTool()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "organic": [
                    {"title": "Test Result", "link": "https://example.com", "snippet": "Test snippet"},
                    {"title": "Result 2", "link": "https://example2.com", "snippet": "Another snippet"},
                ]
            }

            with patch("httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.__aenter__ = AsyncMock(return_value=instance)
                instance.__aexit__ = AsyncMock(return_value=False)
                instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value = instance

                results = await tool.search("AI Safety", num_results=2)

            assert len(results) == 2
            assert results[0]["title"] == "Test Result"
            assert results[0]["url"] == "https://example.com"
            assert results[0]["source"] == "serper"
