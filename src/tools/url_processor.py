"""
URL/Web Article Processor using trafilatura

This module extracts clean article content from web URLs.
trafilatura is excellent for:
- News articles
- Blog posts
- Documentation pages
- General web content

Why trafilatura over alternatives?
- newspaper3k: Unmaintained, often fails on modern sites
- readability-lxml: Good but less features
- beautifulsoup: Requires manual parsing
- trafilatura: Best extraction quality, actively maintained
"""

import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import hashlib


@dataclass
class WebContent:
    """Extracted content from a web URL"""
    text: str
    title: str
    author: Optional[str]
    date: Optional[str]
    url: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_hash: str = ""
    extraction_timestamp: datetime = field(default_factory=datetime.now)


class URLProcessor:
    """
    Process URLs and extract article content.

    Usage:
        processor = URLProcessor()
        content = processor.process("https://example.com/article")
        print(content.title)
        print(content.text)
    """

    def __init__(
        self,
        include_comments: bool = False,
        include_tables: bool = True,
        output_format: str = "markdown",  # "markdown", "txt", "xml"
        target_language: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize the URL processor.

        Args:
            include_comments: Include user comments from the page
            include_tables: Include table content
            output_format: Output format (markdown recommended for LLMs)
            target_language: Filter for specific language content
            timeout: Request timeout in seconds
        """
        self.include_comments = include_comments
        self.include_tables = include_tables
        self.output_format = output_format
        self.target_language = target_language
        self.timeout = timeout
        self._trafilatura = None

    def _ensure_trafilatura(self):
        """Lazy import trafilatura"""
        if self._trafilatura is None:
            try:
                import trafilatura
                self._trafilatura = trafilatura
            except ImportError:
                raise ImportError(
                    "trafilatura is not installed. "
                    "Install with: pip install trafilatura"
                )

    def process(self, url: str) -> WebContent:
        """
        Extract content from a URL.

        Args:
            url: The web URL to process

        Returns:
            WebContent with extracted text and metadata
        """
        self._ensure_trafilatura()

        # Download the page
        try:
            downloaded = self._trafilatura.fetch_url(url)
            if downloaded is None:
                raise RuntimeError(f"Failed to fetch URL: {url}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch URL: {e}")

        # Calculate hash of downloaded content
        content_hash = hashlib.md5(downloaded.encode()).hexdigest()

        # Extract content
        try:
            # Extract with metadata
            result = self._trafilatura.extract(
                downloaded,
                include_comments=self.include_comments,
                include_tables=self.include_tables,
                output_format=self.output_format,
                target_language=self.target_language,
                include_links=True,
                include_images=False,  # We don't handle images from URLs
                with_metadata=True
            )

            if result is None:
                raise RuntimeError(f"Failed to extract content from: {url}")

            # Extract metadata separately
            metadata = self._trafilatura.extract_metadata(downloaded)

            # Build metadata dict
            meta_dict = {}
            if metadata:
                meta_dict = {
                    "sitename": metadata.sitename,
                    "categories": metadata.categories,
                    "tags": metadata.tags,
                    "license": metadata.license,
                    "description": metadata.description,
                }

            return WebContent(
                text=result,
                title=metadata.title if metadata else "",
                author=metadata.author if metadata else None,
                date=metadata.date if metadata else None,
                url=url,
                metadata=meta_dict,
                source_hash=content_hash
            )

        except Exception as e:
            raise RuntimeError(f"Failed to extract content: {e}")

    def process_multiple(self, urls: List[str]) -> List[WebContent]:
        """
        Process multiple URLs.

        Args:
            urls: List of URLs to process

        Returns:
            List of WebContent objects (failed URLs are skipped)
        """
        results = []
        for url in urls:
            try:
                content = self.process(url)
                results.append(content)
            except Exception as e:
                print(f"[Warning] Failed to process {url}: {e}")
                continue
        return results

    def is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid and accessible"""
        try:
            from urllib.parse import urlparse
            result = urlparse(url)
            return all([result.scheme in ('http', 'https'), result.netloc])
        except Exception:
            return False

    def detect_content_type(self, url: str) -> str:
        """
        Detect the type of content at a URL.

        Returns:
            Content type: "article", "video", "audio", "pdf", "unknown"
        """
        url_lower = url.lower()

        # Video platforms
        if any(domain in url_lower for domain in ['youtube.com', 'youtu.be', 'vimeo.com']):
            return "video"

        # Podcast/audio platforms
        if any(domain in url_lower for domain in ['spotify.com/episode', 'anchor.fm', 'soundcloud.com']):
            return "audio"

        # File extensions
        if url_lower.endswith('.pdf'):
            return "pdf"
        if url_lower.endswith(('.mp3', '.wav', '.m4a')):
            return "audio"
        if url_lower.endswith(('.mp4', '.webm', '.mov')):
            return "video"

        # Default to article
        return "article"


class YouTubeProcessor:
    """
    Process YouTube URLs to extract video metadata and transcripts.

    Note: This uses youtube-transcript-api for transcripts,
    not the official YouTube API (which requires auth).
    """

    def __init__(self):
        self._transcript_api = None

    def _ensure_api(self):
        """Lazy import youtube-transcript-api"""
        if self._transcript_api is None:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                self._transcript_api = YouTubeTranscriptApi
            except ImportError:
                raise ImportError(
                    "youtube-transcript-api is not installed. "
                    "Install with: pip install youtube-transcript-api"
                )

    def extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL"""
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(url)

        if 'youtu.be' in parsed.netloc:
            return parsed.path[1:]

        if 'youtube.com' in parsed.netloc:
            if parsed.path == '/watch':
                return parse_qs(parsed.query).get('v', [None])[0]
            if parsed.path.startswith('/embed/'):
                return parsed.path.split('/')[2]
            if parsed.path.startswith('/v/'):
                return parsed.path.split('/')[2]

        raise ValueError(f"Could not extract video ID from: {url}")

    def get_transcript(
        self,
        url: str,
        languages: List[str] = ['en']
    ) -> Dict[str, Any]:
        """
        Get transcript from a YouTube video.

        Args:
            url: YouTube video URL
            languages: Preferred languages for transcript

        Returns:
            Dict with transcript text and metadata
        """
        self._ensure_api()

        video_id = self.extract_video_id(url)

        try:
            # Try to get transcript in preferred languages
            transcript_list = self._transcript_api.list_transcripts(video_id)

            # Try manual transcripts first, then auto-generated
            transcript = None
            for lang in languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except Exception:
                    continue

            if transcript is None:
                # Fall back to any available transcript
                transcript = transcript_list.find_generated_transcript(languages)

            # Fetch the transcript
            transcript_data = transcript.fetch()

            # Combine into full text
            full_text = ' '.join([entry['text'] for entry in transcript_data])

            return {
                "text": full_text,
                "segments": transcript_data,
                "language": transcript.language,
                "is_generated": transcript.is_generated,
                "video_id": video_id,
                "url": url
            }

        except Exception as e:
            raise RuntimeError(f"Failed to get YouTube transcript: {e}")
