"""
Research engine for the AI Builders Podcast System

This module provides a research engine that uses web search to gather information
about topics for podcast episodes.
"""

import hashlib
import json
import logging
import re
import time
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set

import anthropic

from config import ConstellationConfig
from models import ResearchCitation, ResearchResult
from cache import IntelligentCache

class ResearchEngine:
    """Research engine for gathering information about topics
    
    This class provides a research engine that uses web search to gather information
    about topics for podcast episodes.
    
    Attributes:
        cache: Instance of IntelligentCache for caching research results
        claude_client: Anthropic Claude client
    """
    
    def __init__(self, cache: IntelligentCache):
        """Initialize the research engine
        
        Args:
            cache: Instance of IntelligentCache for caching research results
        """
        self.cache = cache
        self.claude_client = anthropic.Anthropic(api_key=ConstellationConfig.CLAUDE_API_KEY)
    
    def research_topic(self, topic: str, depth: str = "standard", 
                     regions: List[str] = None, language: str = "english", 
                     use_cache: bool = True,
                     documents: Optional[List[str]] = None) -> ResearchResult:
        """Research a topic and gather information
        
        Args:
            topic: Topic to research
            depth: Research depth ("quick", "standard", "deep")
            regions: List of regions to focus on
            language: Language for research results
            use_cache: Whether to use cached research results
            documents: List of paths to custom documents for research
            
        Returns:
            ResearchResult object containing research findings
        """
        if regions is None:
            regions = ["global", "india"]
        
        # Create a cache key that includes the document list
        cache_key = f"{topic}_{depth}_{'-'.join(regions)}_{language}"
        if documents:
            doc_hash = hashlib.md5("-".join(sorted(documents)).encode()).hexdigest()
            cache_key += f"_{doc_hash}"
        
        # Check cache first
        if use_cache:
            cached_research = self.cache.get_cached_research(cache_key)
            if cached_research:
                # Convert the cached dictionary back to a ResearchResult object
                return self._dict_to_research_result(cached_research)
        
        # Process custom documents if provided
        custom_document_data = None
        if documents:
            custom_document_data = self.process_documents(documents, topic)
        
        # Generate search queries based on topic and regions
        queries = self._generate_research_queries(topic, regions, language)
        
        # Perform searches and collect results
        search_results = []
        citations = []
        
        for query in queries:
            logging.info(f"Searching for: {query}")
            
            try:
                # Use web_search function directly or as a placeholder
                # In a real implementation, this would call the appropriate search API
                results = self._perform_web_search(query)
                
                if results:
                    # Process and filter the results
                    filtered_results = self._filter_relevant_content(results, topic)
                    search_results.extend(filtered_results)
                    
                    # Create citations for the results
                    for result in filtered_results:
                        citation = ResearchCitation(
                            source=result.get("title", "Unknown Source"),
                            url=result.get("url", ""),
                            access_date=datetime.now(),
                            content_snippet=result.get("snippet", ""),
                            author=result.get("author", None),
                            publication_date=result.get("date", None),
                            source_type=self._determine_source_type(result.get("url", ""))
                        )
                        citations.append(citation)
            
            except Exception as e:
                logging.error(f"Error searching for {query}: {e}")
        
        # Add citations for custom documents
        if custom_document_data:
            for doc_name, doc_info in custom_document_data.items():
                if 'path' in doc_info:
                    citation = ResearchCitation(
                        source=doc_name,
                        url=f"file://{doc_info['path']}",
                        access_date=datetime.now(),
                        content_snippet=doc_info.get('summary', '')[:200] + "...",
                        author="Custom Document",
                        publication_date=datetime.fromtimestamp(os.path.getmtime(doc_info['path'])).strftime("%Y-%m-%d"),
                        source_type="custom_document"
                    )
                    citations.append(citation)
        
        # Use Claude to analyze and synthesize the search results
        analysis_result = self._analyze_research_results(
            search_results, 
            topic, 
            regions, 
            language,
            custom_document_data
        )
        
        # Create the research result
        research_result = ResearchResult(
            topic=topic,
            summary=analysis_result.get("summary", ""),
            key_points=analysis_result.get("key_points", []),
            citations=citations,
            examples=analysis_result.get("examples", []),
            regional_insights=analysis_result.get("regional_insights", {}),
            custom_documents=custom_document_data
        )
        
        # Cache the research result
        self.cache.cache_research_results(topic, self._research_result_to_dict(research_result))
        
        return research_result
    
    def process_documents(self, document_paths: List[str], topic: str) -> Dict[str, Any]:
        """Process custom documents for research
        
        Args:
            document_paths: List of paths to documents
            topic: Topic for context
            
        Returns:
            Dictionary mapping document names to extracted information
        """
        document_data = {}
        
        for path in document_paths:
            if not os.path.exists(path):
                logging.warning(f"Document not found: {path}")
                continue
                
            filename = os.path.basename(path)
            file_extension = os.path.splitext(path)[1].lower()
            
            # Check if file type is supported
            if file_extension not in ConstellationConfig.RESEARCH_CONFIG["supported_document_types"]:
                logging.warning(f"Unsupported document type: {file_extension}")
                continue
            
            try:
                # Read the document content
                content = self._read_document(path, file_extension)
                
                if content:
                    # Analyze the document content
                    analysis = self._analyze_document(content, filename, topic)
                    
                    # Add document data
                    document_data[filename] = {
                        "path": path,
                        "type": file_extension,
                        "size": os.path.getsize(path),
                        "summary": analysis.get("summary", ""),
                        "key_points": analysis.get("key_points", []),
                        "insights_count": len(analysis.get("key_points", [])),
                        "content_length": len(content)
                    }
            except Exception as e:
                logging.error(f"Error processing document {path}: {e}")
        
        return document_data
    
    def _read_document(self, path: str, file_type: str) -> Optional[str]:
        """Read document content based on file type
        
        Args:
            path: Path to document
            file_type: Document file type
            
        Returns:
            Document content as string, or None if reading fails
        """
        try:
            # Simple text-based files
            if file_type in ['.txt', '.md']:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            # JSON files
            elif file_type == '.json':
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert JSON to a readable string representation
                    return json.dumps(data, indent=2)
            
            # PDF files would require a PDF library
            elif file_type == '.pdf':
                # Placeholder for PDF extraction
                logging.info(f"PDF support would require PyPDF2 or similar library")
                return f"[PDF CONTENT: {path}]"
            
            # DOCX files would require python-docx
            elif file_type == '.docx':
                # Placeholder for DOCX extraction
                logging.info(f"DOCX support would require python-docx library")
                return f"[DOCX CONTENT: {path}]"
            
            # CSV files
            elif file_type == '.csv':
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            else:
                logging.warning(f"Unsupported file type for reading: {file_type}")
                return None
                
        except Exception as e:
            logging.error(f"Error reading document {path}: {e}")
            return None
    
    def _analyze_document(self, content: str, filename: str, topic: str) -> Dict[str, Any]:
        """Analyze document content using Claude
        
        Args:
            content: Document content
            filename: Name of the document
            topic: Topic for context
            
        Returns:
            Dictionary containing analysis results
        """
        # For very large documents, truncate to avoid token limits
        max_content_length = 10000  # Adjust based on token limits
        if len(content) > max_content_length:
            truncated_content = content[:max_content_length] + "... [CONTENT TRUNCATED]"
        else:
            truncated_content = content
        
        # Create a prompt for Claude to analyze the document
        prompt = f"""
Please analyze the following document in relation to the topic "{topic}".

DOCUMENT NAME: {filename}

DOCUMENT CONTENT:
{truncated_content}

Provide:
1. A concise summary (3-5 sentences)
2. 5-10 key points or insights from the document
3. Any examples that illustrate important concepts
4. Any regional or cultural insights if present

Focus on extracting information that is most relevant to the topic "{topic}".
"""
        
        try:
            response = self.claude_client.messages.create(
                model=ConstellationConfig.CLAUDE_MODELS["standard"],
                max_tokens=1000,
                temperature=0.0,  # Use deterministic output for analysis
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            # Parse the response to extract structured information
            analysis = {
                "summary": self._extract_section(response_text, "summary"),
                "key_points": self._extract_list_items(response_text, "key points"),
                "examples": self._extract_list_items(response_text, "examples"),
                "regional_insights": self._extract_list_items(response_text, "regional")
            }
            
            return analysis
            
        except Exception as e:
            logging.error(f"Error analyzing document {filename}: {e}")
            return {
                "summary": f"Error analyzing document: {str(e)}",
                "key_points": [],
                "examples": [],
                "regional_insights": []
            }
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from Claude's response
        
        Args:
            text: Response text
            section_name: Name of section to extract
            
        Returns:
            Extracted section text
        """
        # Try to find sections with various heading formats
        patterns = [
            rf"(?i).*?{section_name}:?\s*(.*?)(?:\n\n|\n\d\.|\Z)",
            rf"(?i).*?{section_name}:?\s*(.*?)(?:\n[A-Z]|\Z)",
            rf"(?i).*?{section_name}:?\s*(.*)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_list_items(self, text: str, section_name: str) -> List[str]:
        """Extract list items from Claude's response
        
        Args:
            text: Response text
            section_name: Name of section containing list
            
        Returns:
            List of extracted items
        """
        items = []
        
        # First try to find the section
        section = self._extract_section(text, section_name)
        if not section:
            return items
        
        # Extract numbered list items
        numbered_matches = re.findall(r"(?m)^\s*\d+\.\s*(.*?)$", section)
        if numbered_matches:
            items.extend([item.strip() for item in numbered_matches])
            return items
        
        # Extract bullet list items
        bullet_matches = re.findall(r"(?m)^\s*[\*\-•]\s*(.*?)$", section)
        if bullet_matches:
            items.extend([item.strip() for item in bullet_matches])
            return items
        
        # If no list found, split by newlines as fallback
        if not items and section:
            items = [line.strip() for line in section.split("\n") if line.strip()]
        
        return items
    
    def _generate_research_queries(self, topic: str, regions: List[str], language: str) -> List[str]:
        """Generate search queries based on topic and regions
        
        Args:
            topic: Topic to research
            regions: List of regions to focus on
            language: Language for queries
            
        Returns:
            List of search queries
        """
        queries = []
        
        # Generate basic queries about the topic
        queries.append(f"{topic} explained")
        queries.append(f"{topic} recent developments")
        queries.append(f"{topic} best practices")
        
        # Generate region-specific queries
        for region in regions:
            if region != "global":
                queries.append(f"{topic} in {region}")
                queries.append(f"{topic} applications {region}")
                queries.append(f"{topic} case studies {region}")
        
        # Generate technical queries
        queries.append(f"{topic} technical implementation")
        queries.append(f"{topic} technology stack")
        queries.append(f"{topic} tutorial")
        
        # Generate comparative queries
        queries.append(f"{topic} versus alternatives")
        queries.append(f"{topic} pros and cons")
        
        # Adjust for non-English languages
        if language != "english":
            # For this mock implementation, we'll assume queries need to be translated
            # In a real implementation, this would use a translation service
            # For now, we'll just add a note that the queries would be translated
            logging.info(f"Queries would be translated to {language}")
        
        return queries
    
    def _perform_web_search(self, query: str) -> List[Dict]:
        """Perform a web search using the specified query
        
        This is a placeholder implementation. In a real implementation, this would
        call the appropriate search API (Claude's web_search function).
        
        Args:
            query: Search query
            
        Returns:
            List of search results
        """
        # This is where we would use Claude's web_search function
        # For this example, we'll return mock results
        
        # Simulate a web search with mock results
        mock_results = [
            {
                "title": f"Understanding {query}",
                "url": f"https://example.com/understanding-{query.replace(' ', '-')}",
                "snippet": f"A comprehensive guide to {query} and its applications in modern technology.",
                "author": "Tech Expert",
                "date": "2023-05-15"
            },
            {
                "title": f"Latest Developments in {query}",
                "url": f"https://example.com/latest-{query.replace(' ', '-')}",
                "snippet": f"Recent advancements in {query} are transforming how businesses operate.",
                "author": "Industry Analyst",
                "date": "2023-10-22"
            },
            {
                "title": f"{query} Implementation Guide",
                "url": f"https://example.com/{query.replace(' ', '-')}-guide",
                "snippet": f"Step-by-step guide to implementing {query} in your projects.",
                "author": "Developer Community",
                "date": "2023-08-03"
            }
        ]
        
        # Simulate some delay to mimic a real API call
        time.sleep(0.5)
        
        return mock_results
    
    def _filter_relevant_content(self, results: List[Dict], topic: str) -> List[Dict]:
        """Filter search results for relevant content
        
        Args:
            results: List of search results
            topic: Topic being researched
            
        Returns:
            Filtered list of search results
        """
        # This is a simplified implementation
        # In a real implementation, this would use more sophisticated filtering
        
        filtered_results = []
        topic_keywords = set(topic.lower().split())
        
        for result in results:
            # Check if the title or snippet contains the topic keywords
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            
            title_words = set(title.split())
            snippet_words = set(snippet.split())
            
            # Check for keyword overlap
            if topic_keywords.intersection(title_words) or topic_keywords.intersection(snippet_words):
                filtered_results.append(result)
        
        return filtered_results
    
    def _determine_source_type(self, url: str) -> str:
        """Determine the type of source based on the URL
        
        Args:
            url: URL of the source
            
        Returns:
            Source type (e.g., "academic_paper", "website")
        """
        if ".edu" in url or "arxiv.org" in url or "research" in url:
            return "academic_paper"
        elif ".gov" in url:
            return "government_publication"
        elif "blog" in url or "medium.com" in url:
            return "blog"
        elif "news" in url or "article" in url:
            return "news_article"
        elif "doc" in url or "documentation" in url:
            return "documentation"
        else:
            return "website"
    
    def _analyze_research_results(self, search_results: List[Dict], topic: str, 
                               regions: List[str], language: str,
                               custom_document_data: Optional[Dict[str, Any]] = None) -> Dict:
        """Analyze search results and extract insights
        
        Args:
            search_results: List of search results
            topic: Topic being researched
            regions: List of regions being researched
            language: Language for analysis
            custom_document_data: Data from custom documents
            
        Returns:
            Dictionary containing analysis results
        """
        # This is where we would use Claude to analyze the search results
        # For this example, we'll create a simplified implementation
        
        # Combine all snippets for analysis
        combined_text = ""
        for result in search_results:
            combined_text += result.get("snippet", "") + " "
        
        # Add custom document summaries if available
        custom_doc_insights = []
        if custom_document_data:
            combined_text += "\n\nCUSTOM DOCUMENT INSIGHTS:\n"
            for doc_name, doc_info in custom_document_data.items():
                if 'summary' in doc_info:
                    combined_text += f"\nFrom {doc_name}:\n{doc_info['summary']}\n"
                
                if 'key_points' in doc_info:
                    for point in doc_info['key_points']:
                        custom_doc_insights.append(f"{point} (from {doc_name})")
        
        # Mock analysis results
        analysis = {
            "summary": f"Research on {topic} shows significant advancements in recent years, with applications across various industries. The technology continues to evolve with new methodologies and best practices emerging regularly.",
            "key_points": [
                f"{topic} adoption is growing across industries",
                f"Recent developments in {topic} focus on efficiency and scalability",
                f"Implementation challenges include technical complexity and integration issues",
                f"Best practices emphasize thorough planning and phased deployment"
            ],
            "examples": [
                f"Company X increased productivity by 30% after implementing {topic}",
                f"Project Y used {topic} to solve complex data processing challenges",
                f"Startup Z built their entire business model around {topic} technology"
            ],
            "regional_insights": {}
        }
        
        # Add region-specific insights
        for region in regions:
            if region == "global":
                analysis["regional_insights"]["global"] = [
                    f"Global adoption of {topic} is led by North America and Europe",
                    f"International standards for {topic} are still evolving",
                    f"Multinational corporations are investing heavily in {topic} technology"
                ]
            elif region == "india":
                analysis["regional_insights"]["india"] = [
                    f"Indian IT companies are rapidly adopting {topic} for client projects",
                    f"{topic} startups in India are attracting significant venture capital",
                    f"Government initiatives are promoting {topic} education and research in India"
                ]
        
        # Add insights from custom documents
        if custom_doc_insights:
            analysis["key_points"].extend(custom_doc_insights[:5])  # Add up to 5 insights
        
        return analysis
    
    def _research_result_to_dict(self, research_result: ResearchResult) -> Dict:
        """Convert ResearchResult object to dictionary for caching
        
        Args:
            research_result: ResearchResult object
            
        Returns:
            Dictionary representation of ResearchResult
        """
        citations_dict = []
        for citation in research_result.citations:
            citations_dict.append({
                "source": citation.source,
                "url": citation.url,
                "access_date": citation.access_date.isoformat(),
                "content_snippet": citation.content_snippet,
                "author": citation.author,
                "publication_date": citation.publication_date,
                "source_type": citation.source_type
            })
        
        return {
            "topic": research_result.topic,
            "summary": research_result.summary,
            "key_points": research_result.key_points,
            "citations": citations_dict,
            "examples": research_result.examples,
            "regional_insights": research_result.regional_insights,
            "custom_documents": research_result.custom_documents
        }
    
    def _dict_to_research_result(self, data: Dict) -> ResearchResult:
        """Convert dictionary to ResearchResult object
        
        Args:
            data: Dictionary representation of ResearchResult
            
        Returns:
            ResearchResult object
        """
        citations = []
        for citation_dict in data["citations"]:
            citation = ResearchCitation(
                source=citation_dict["source"],
                url=citation_dict["url"],
                access_date=datetime.fromisoformat(citation_dict["access_date"]),
                content_snippet=citation_dict["content_snippet"],
                author=citation_dict.get("author"),
                publication_date=citation_dict.get("publication_date"),
                source_type=citation_dict.get("source_type")
            )
            citations.append(citation)
        
        return ResearchResult(
            topic=data["topic"],
            summary=data["summary"],
            key_points=data["key_points"],
            citations=citations,
            examples=data["examples"],
            regional_insights=data["regional_insights"],
            custom_documents=data.get("custom_documents")
        )
    
    def generate_citation_document(self, research_result: ResearchResult, format: str = "markdown") -> str:
        """Generate a citation document from research results
        
        Args:
            research_result: ResearchResult object
            format: Output format ("markdown", "html", "text")
            
        Returns:
            Formatted citation document
        """
        if format == "markdown":
            return self._generate_markdown_citations(research_result)
        elif format == "html":
            return self._generate_html_citations(research_result)
        else:
            return self._generate_text_citations(research_result)
    
    def _generate_markdown_citations(self, research_result: ResearchResult) -> str:
        """Generate markdown-formatted citations
        
        Args:
            research_result: ResearchResult object
            
        Returns:
            Markdown-formatted citations
        """
        markdown = f"# References for: {research_result.topic}\n\n"
        
        # Add custom document citations first
        if research_result.custom_documents:
            markdown += "## Custom Documents\n\n"
            for i, (doc_name, doc_info) in enumerate(research_result.custom_documents.items(), 1):
                markdown += f"{i}. **{doc_name}** - {doc_info.get('type', 'Unknown type')}\n"
                if 'summary' in doc_info:
                    summary = doc_info['summary']
                    if len(summary) > 200:
                        summary = summary[:200] + "..."
                    markdown += f"   {summary}\n\n"
        
        # Add web sources
        markdown += "## Web Sources\n\n"
        web_sources = [c for c in research_result.citations if c.source_type != "custom_document"]
        for i, citation in enumerate(web_sources, 1):
            markdown += f"{i}. {citation.format_citation()}\n\n"
        
        return markdown
    
    def _generate_html_citations(self, research_result: ResearchResult) -> str:
        """Generate HTML-formatted citations
        
        Args:
            research_result: ResearchResult object
            
        Returns:
            HTML-formatted citations
        """
        html = f"<h1>References for: {research_result.topic}</h1>\n"
        
        # Add custom document citations first
        if research_result.custom_documents:
            html += "<h2>Custom Documents</h2>\n<ol>\n"
            for doc_name, doc_info in research_result.custom_documents.items():
                html += f"<li><strong>{doc_name}</strong> - {doc_info.get('type', 'Unknown type')}"
                if 'summary' in doc_info:
                    summary = doc_info['summary']
                    if len(summary) > 200:
                        summary = summary[:200] + "..."
                    html += f"<p>{summary}</p>"
                html += "</li>\n"
            html += "</ol>\n"
        
        # Add web sources
        html += "<h2>Web Sources</h2>\n<ol>\n"
        web_sources = [c for c in research_result.citations if c.source_type != "custom_document"]
        for citation in web_sources:
            html += f"<li>{citation.format_citation()}</li>\n"
        html += "</ol>\n"
        
        return html
    
    def _generate_text_citations(self, research_result: ResearchResult) -> str:
        """Generate plain text-formatted citations
        
        Args:
            research_result: ResearchResult object
            
        Returns:
            Plain text-formatted citations
        """
        text = f"References for: {research_result.topic}\n\n"
        
        # Add custom document citations first
        if research_result.custom_documents:
            text += "CUSTOM DOCUMENTS\n" + "="*16 + "\n\n"
            for i, (doc_name, doc_info) in enumerate(research_result.custom_documents.items(), 1):
                text += f"{i}. {doc_name} - {doc_info.get('type', 'Unknown type')}\n"
                if 'summary' in doc_info:
                    summary = doc_info['summary']
                    if len(summary) > 200:
                        summary = summary[:200] + "..."
                    text += f"   {summary}\n\n"
        
        # Add web sources
        text += "WEB SOURCES\n" + "="*11 + "\n\n"
        web_sources = [c for c in research_result.citations if c.source_type != "custom_document"]
        for i, citation in enumerate(web_sources, 1):
            text += f"{i}. {citation.format_citation()}\n\n"
        
        return text

    def extract_llm_content(self, content: str, source: str = "ChatGPT") -> Dict:
        """Extract content from another LLM output
        
        Args:
            content: Content from another LLM
            source: Source LLM (e.g., "ChatGPT", "Gemini")
            
        Returns:
            Dictionary containing extracted content
        """
        # Parse and structure the content from another LLM
        
        # For this mock implementation, we'll return a simple dictionary
        return {
            "source": source,
            "content": content,
            "type": "llm_output",
            "extraction_date": datetime.now().isoformat()
        }
    
    def create_github_resources(self, research_result: ResearchResult, 
                             language: str, episode_number: int) -> Dict:
        """Create resources for GitHub repository
        
        Args:
            research_result: ResearchResult object
            language: Language of the episode
            episode_number: Episode number
            
        Returns:
            Dictionary containing GitHub resource information
        """
        # Generate paths based on configuration
        base_url = ConstellationConfig.RESEARCH_CONFIG["github_repo_structure"]["base_url"]
        dirs = ConstellationConfig.RESEARCH_CONFIG["github_repo_structure"]["directories"]
        
        # Replace placeholders in directory paths
        citation_dir = dirs["citations"].format(language=language, episode_number=episode_number)
        resource_dir = dirs["resources"].format(language=language, topic=research_result.topic.replace(" ", "_").lower())
        
        # Generate citation document
        citation_doc = self.generate_citation_document(research_result, "markdown")
        
        # In a real implementation, this would push to GitHub
        # For this mock implementation, we'll just return the paths and content
        
        return {
            "citation_path": f"{base_url}{citation_dir}/references.md",
            "citation_content": citation_doc,
            "resource_path": f"{base_url}{resource_dir}/research_summary.md",
            "resource_content": research_result.to_markdown()
        }

    def load_documents_from_directory(self, directory: str, recursive: bool = False) -> List[str]:
        """Load all documents from a directory
        
        Args:
            directory: Directory path
            recursive: Whether to search subdirectories
            
        Returns:
            List of document paths
        """
        document_paths = []
        
        if not os.path.exists(directory):
            logging.warning(f"Directory not found: {directory}")
            return document_paths
        
        # Get supported file extensions
        supported_types = ConstellationConfig.RESEARCH_CONFIG["supported_document_types"]
        
        # Walk through the directory
        if recursive:
            for root, _, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in supported_types:
                        document_paths.append(file_path)
        else:
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in supported_types:
                        document_paths.append(file_path)
        
        return document_paths
