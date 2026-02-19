"""
Knowledge Graph Manager

This module provides the interface to the Kuzu Knowledge Graph.
It handles:
- Database initialization and schema creation
- CRUD operations for entities and relationships
- Query execution
- Transaction management

Usage:
    from src.graph.manager import KnowledgeGraphManager

    # Initialize (creates DB if not exists)
    kg = KnowledgeGraphManager("./data/podcast_kg")

    # Add entities
    topic_id = kg.add_topic("AI Safety", "Research into safe AI systems")
    fact_id = kg.add_fact("Claude is developed by Anthropic", confidence=0.99)

    # Create relationships
    kg.link_fact_to_topic(fact_id, topic_id, relevance=0.9)

    # Query
    facts = kg.get_facts_about_topic("AI Safety")
"""

import os
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

from .schema import (
    SCHEMA_DDL, QUERIES,
    TopicNode, FactNode, SourceNode, SegmentNode,
    EntityType, RelationshipType
)


class KnowledgeGraphManager:
    """
    Manager for the Kuzu Knowledge Graph.

    Kuzu is an embedded graph database - it runs in-process without a server.
    This makes it perfect for local development and testing.
    """

    def __init__(self, db_path: str = "./data/podcast_kg"):
        """
        Initialize the Knowledge Graph.

        Args:
            db_path: Path to the Kuzu database directory
        """
        self.db_path = db_path
        self._db = None
        self._conn = None

        # Lazy import kuzu - it may not be installed yet
        self._kuzu = None

    def _ensure_kuzu(self):
        """Ensure kuzu is imported and available"""
        if self._kuzu is None:
            try:
                import kuzu
                self._kuzu = kuzu
            except ImportError:
                raise ImportError(
                    "Kuzu is not installed. Install with: pip install kuzu"
                )

    def initialize(self) -> None:
        """
        Initialize the database and create schema if needed.

        This is idempotent - safe to call multiple times.
        """
        self._ensure_kuzu()

        # Create parent directory if needed (Kuzu creates the db directory itself)
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        # Open database
        self._db = self._kuzu.Database(self.db_path)
        self._conn = self._kuzu.Connection(self._db)

        # Create schema
        # Split DDL into individual statements and strip comments
        statements = []
        for s in SCHEMA_DDL.split(';'):
            # Remove comment-only lines and strip
            lines = [l for l in s.strip().splitlines() if not l.strip().startswith('--')]
            clean = '\n'.join(lines).strip()
            if clean:
                statements.append(clean)

        for stmt in statements:
            try:
                self._conn.execute(stmt)
            except Exception as e:
                # Schema already exists - that's fine
                if "already exists" not in str(e).lower():
                    logger.warning(f"Schema DDL failed: {e}\n  Statement: {stmt[:80]}...")
                    raise

    def close(self) -> None:
        """Close the database connection"""
        if self._conn:
            self._conn = None
        if self._db:
            self._db = None

    @contextmanager
    def transaction(self):
        """
        Context manager for transactions.

        Usage:
            with kg.transaction():
                kg.add_topic(...)
                kg.add_fact(...)
        """
        # Kuzu auto-commits, but we can use this for future transaction support
        try:
            yield
        except Exception:
            raise

    def _generate_id(self, prefix: str = "") -> str:
        """Generate a unique ID for an entity"""
        return f"{prefix}{uuid.uuid4().hex[:12]}"

    # =========================================================================
    # ENTITY OPERATIONS
    # =========================================================================

    def add_topic(
        self,
        name: str,
        description: str = "",
        category: str = "general",
        importance_score: float = 0.5
    ) -> str:
        """
        Add a topic to the graph.

        Args:
            name: Topic name (e.g., "AI Safety")
            description: Description of the topic
            category: Category for grouping
            importance_score: How central is this topic (0-1)

        Returns:
            The generated topic ID
        """
        topic_id = self._generate_id("topic_")
        now = datetime.now().isoformat()

        query = """
            CREATE (t:Topic {
                id: $id,
                name: $name,
                description: $description,
                category: $category,
                importance_score: $importance_score,
                created_at: timestamp($created_at),
                updated_at: timestamp($updated_at)
            })
        """

        self._conn.execute(query, {
            "id": topic_id,
            "name": name,
            "description": description,
            "category": category,
            "importance_score": importance_score,
            "created_at": now,
            "updated_at": now
        })

        return topic_id

    def add_fact(
        self,
        claim: str,
        confidence: float = 0.8,
        verified: bool = False,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None
    ) -> str:
        """
        Add a fact/claim to the graph.

        Facts are atomic claims that can be verified.
        They have temporal properties (valid_from, valid_until) for
        tracking when information was true.

        Args:
            claim: The factual claim (e.g., "Anthropic was founded in 2021")
            confidence: How confident are we in this fact (0-1)
            verified: Has this been fact-checked?
            valid_from: When did this fact become true?
            valid_until: When did this fact stop being true? (None = still valid)

        Returns:
            The generated fact ID
        """
        fact_id = self._generate_id("fact_")
        now = datetime.now()

        if valid_from is None:
            valid_from = now

        query = """
            CREATE (f:Fact {
                id: $id,
                claim: $claim,
                confidence: $confidence,
                verified: $verified,
                valid_from: timestamp($valid_from),
                valid_until: $valid_until,
                created_at: timestamp($created_at)
            })
        """

        self._conn.execute(query, {
            "id": fact_id,
            "claim": claim,
            "confidence": confidence,
            "verified": verified,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat() if valid_until else None,
            "created_at": now.isoformat()
        })

        return fact_id

    def add_source(
        self,
        source_type: str,
        url: str = "",
        title: str = "",
        author: str = "",
        copyright_status: str = "unknown",
        reliability_score: float = 0.5
    ) -> str:
        """
        Add a source to the graph.

        Sources are where facts come from. Tracking provenance is critical
        for fact-checking and avoiding hallucinations.

        Args:
            source_type: Type of source ("pdf", "url", "audio", "user_input")
            url: URL or file path
            title: Title of the source
            author: Author if known
            copyright_status: "user_owned", "public_domain", "copyrighted", "unknown"
            reliability_score: How reliable is this source? (0-1)

        Returns:
            The generated source ID
        """
        source_id = self._generate_id("src_")
        now = datetime.now().isoformat()

        query = """
            CREATE (s:Source {
                id: $id,
                source_type: $source_type,
                url: $url,
                title: $title,
                author: $author,
                publication_date: NULL,
                copyright_status: $copyright_status,
                reliability_score: $reliability_score,
                created_at: timestamp($created_at)
            })
        """

        self._conn.execute(query, {
            "id": source_id,
            "source_type": source_type,
            "url": url,
            "title": title,
            "author": author,
            "copyright_status": copyright_status,
            "reliability_score": reliability_score,
            "created_at": now
        })

        return source_id

    def add_segment(
        self,
        text: str,
        sequence_num: int,
        speaker_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        emotion: str = "neutral"
    ) -> str:
        """
        Add a script segment to the graph.

        Args:
            text: The segment text
            sequence_num: Order in the episode
            speaker_id: ID of the speaker (if known)
            episode_id: ID of the episode this belongs to
            emotion: Emotional tone for TTS

        Returns:
            The generated segment ID
        """
        segment_id = self._generate_id("seg_")
        now = datetime.now().isoformat()
        word_count = len(text.split())
        # Rough estimate: 150 words per minute
        duration_seconds = (word_count / 150) * 60

        query = """
            CREATE (s:Segment {
                id: $id,
                text: $text,
                sequence_num: $sequence_num,
                emotion: $emotion,
                duration_seconds: $duration_seconds,
                word_count: $word_count,
                created_at: timestamp($created_at)
            })
        """

        self._conn.execute(query, {
            "id": segment_id,
            "text": text,
            "sequence_num": sequence_num,
            "emotion": emotion,
            "duration_seconds": duration_seconds,
            "word_count": word_count,
            "created_at": now
        })

        # Create relationships if IDs provided
        if speaker_id:
            self.link_segment_to_speaker(segment_id, speaker_id)
        if episode_id:
            self.link_segment_to_episode(segment_id, episode_id)

        return segment_id

    # =========================================================================
    # RELATIONSHIP OPERATIONS
    # =========================================================================

    def link_fact_to_topic(
        self,
        fact_id: str,
        topic_id: str,
        relevance: float = 0.8
    ) -> None:
        """Create ABOUT relationship between fact and topic"""
        query = """
            MATCH (f:Fact {id: $fact_id}), (t:Topic {id: $topic_id})
            CREATE (f)-[:ABOUT {relevance: $relevance}]->(t)
        """
        self._conn.execute(query, {
            "fact_id": fact_id,
            "topic_id": topic_id,
            "relevance": relevance
        })

    def link_fact_to_source(
        self,
        fact_id: str,
        source_id: str,
        quote: str = "",
        page_number: int = 0
    ) -> None:
        """Create SOURCED_FROM relationship between fact and source"""
        query = """
            MATCH (f:Fact {id: $fact_id}), (s:Source {id: $source_id})
            CREATE (f)-[:SOURCED_FROM {quote: $quote, page_number: $page_number}]->(s)
        """
        self._conn.execute(query, {
            "fact_id": fact_id,
            "source_id": source_id,
            "quote": quote,
            "page_number": page_number
        })

    def link_segment_to_speaker(self, segment_id: str, speaker_id: str) -> None:
        """Create SPOKEN_BY relationship"""
        query = """
            MATCH (seg:Segment {id: $segment_id}), (sp:Speaker {id: $speaker_id})
            CREATE (seg)-[:SPOKEN_BY]->(sp)
        """
        self._conn.execute(query, {
            "segment_id": segment_id,
            "speaker_id": speaker_id
        })

    def link_segment_to_episode(self, segment_id: str, episode_id: str) -> None:
        """Create PART_OF relationship"""
        query = """
            MATCH (seg:Segment {id: $segment_id}), (ep:Episode {id: $episode_id})
            CREATE (seg)-[:PART_OF]->(ep)
        """
        self._conn.execute(query, {
            "segment_id": segment_id,
            "episode_id": episode_id
        })

    def link_segment_to_fact(
        self,
        segment_id: str,
        fact_id: str,
        citation_style: str = "inline"
    ) -> None:
        """Create CITES relationship - segment cites a fact"""
        query = """
            MATCH (seg:Segment {id: $segment_id}), (f:Fact {id: $fact_id})
            CREATE (seg)-[:CITES {citation_style: $citation_style}]->(f)
        """
        self._conn.execute(query, {
            "segment_id": segment_id,
            "fact_id": fact_id,
            "citation_style": citation_style
        })

    def link_facts_supporting(
        self,
        fact_id: str,
        supports_fact_id: str,
        confidence: float = 0.8
    ) -> None:
        """Create SUPPORTS relationship between facts"""
        query = """
            MATCH (f1:Fact {id: $fact_id}), (f2:Fact {id: $supports_fact_id})
            CREATE (f1)-[:SUPPORTS {confidence: $confidence}]->(f2)
        """
        self._conn.execute(query, {
            "fact_id": fact_id,
            "supports_fact_id": supports_fact_id,
            "confidence": confidence
        })

    def link_facts_contradicting(
        self,
        fact_id: str,
        contradicts_fact_id: str,
        severity: str = "minor"
    ) -> None:
        """Create CONTRADICTS relationship between facts"""
        query = """
            MATCH (f1:Fact {id: $fact_id}), (f2:Fact {id: $contradicts_fact_id})
            CREATE (f1)-[:CONTRADICTS {severity: $severity}]->(f2)
        """
        self._conn.execute(query, {
            "fact_id": fact_id,
            "contradicts_fact_id": contradicts_fact_id,
            "severity": severity
        })

    # =========================================================================
    # QUERY OPERATIONS
    # =========================================================================

    def get_facts_about_topic(self, topic_name: str) -> List[Dict[str, Any]]:
        """Get all facts about a topic"""
        result = self._conn.execute(
            QUERIES["facts_about_topic"],
            {"topic_name": topic_name}
        )
        return [dict(row) for row in result.get_as_df().to_dict('records')]

    def get_unsupported_claims(self) -> List[Dict[str, Any]]:
        """Find claims in segments that have no source"""
        result = self._conn.execute(QUERIES["unsupported_claims"])
        return [dict(row) for row in result.get_as_df().to_dict('records')]

    def get_contradictions(self) -> List[Dict[str, Any]]:
        """Find contradicting facts"""
        result = self._conn.execute(QUERIES["contradictions"])
        return [dict(row) for row in result.get_as_df().to_dict('records')]

    def get_episode_segments(self, episode_id: str) -> List[Dict[str, Any]]:
        """Get all segments for an episode in order"""
        result = self._conn.execute(
            QUERIES["episode_flow"],
            {"episode_id": episode_id}
        )
        return [dict(row) for row in result.get_as_df().to_dict('records')]

    def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a custom Cypher query"""
        result = self._conn.execute(query, params or {})
        return [dict(row) for row in result.get_as_df().to_dict('records')]

    # =========================================================================
    # VERIFICATION HELPERS
    # =========================================================================

    def verify_fact(self, fact_id: str, verified: bool = True) -> None:
        """Mark a fact as verified or not"""
        query = """
            MATCH (f:Fact {id: $fact_id})
            SET f.verified = $verified
        """
        self._conn.execute(query, {"fact_id": fact_id, "verified": verified})

    def get_fact_provenance(self, fact_id: str) -> List[Dict[str, Any]]:
        """Get the full provenance chain for a fact"""
        result = self._conn.execute(
            QUERIES["fact_provenance"],
            {"fact_id": fact_id}
        )
        return [dict(row) for row in result.get_as_df().to_dict('records')]
