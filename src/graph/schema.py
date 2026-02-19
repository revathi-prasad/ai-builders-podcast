"""
Knowledge Graph Schema for Podcast Generator

This module defines the schema for our Kuzu-based Knowledge Graph.
The graph serves multiple purposes:

1. INFORMATION PRESERVATION: Store extracted content so agents don't lose context
2. PROVENANCE TRACKING: Know where every fact came from (for fact-checking)
3. TEMPORAL AWARENESS: Track when facts are valid (Graphiti-style)
4. RL SIGNALS: Query patterns of successful vs failed generations

Why Kuzu?
- MIT license (clean for portfolio)
- 18x faster than Neo4j for ingestion
- Embedded (no server setup)
- Full Cypher support
- Easy migration to Neo4j later if needed

Schema Design Philosophy:
- Every piece of content becomes a node
- Relationships track provenance and semantic connections
- Temporal properties enable "was this fact valid at generation time?"
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EntityType(str, Enum):
    """Types of entities in the Knowledge Graph"""
    TOPIC = "Topic"
    FACT = "Fact"
    SOURCE = "Source"
    SPEAKER = "Speaker"
    SEGMENT = "Segment"
    EPISODE = "Episode"
    USER_INPUT = "UserInput"


class RelationshipType(str, Enum):
    """Types of relationships between entities"""
    # Content relationships
    MENTIONS = "MENTIONS"           # (Segment)-[:MENTIONS]->(Topic)
    ABOUT = "ABOUT"                 # (Fact)-[:ABOUT]->(Topic)
    SUPPORTS = "SUPPORTS"           # (Fact)-[:SUPPORTS]->(Fact)
    CONTRADICTS = "CONTRADICTS"     # (Fact)-[:CONTRADICTS]->(Fact)

    # Provenance relationships
    SOURCED_FROM = "SOURCED_FROM"   # (Fact)-[:SOURCED_FROM]->(Source)
    EXTRACTED_FROM = "EXTRACTED_FROM"  # (Fact)-[:EXTRACTED_FROM]->(UserInput)

    # Script structure relationships
    SPOKEN_BY = "SPOKEN_BY"         # (Segment)-[:SPOKEN_BY]->(Speaker)
    FOLLOWS = "FOLLOWS"             # (Segment)-[:FOLLOWS]->(Segment)
    PART_OF = "PART_OF"             # (Segment)-[:PART_OF]->(Episode)
    CITES = "CITES"                 # (Segment)-[:CITES]->(Fact)


# ============================================================================
# KUZU SCHEMA DEFINITIONS (Cypher DDL)
# ============================================================================

SCHEMA_DDL = """
-- Node Tables (Entities)

CREATE NODE TABLE IF NOT EXISTS Topic (
    id STRING PRIMARY KEY,
    name STRING,
    description STRING,
    category STRING,
    importance_score DOUBLE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Fact (
    id STRING PRIMARY KEY,
    claim STRING,
    confidence DOUBLE,
    verified BOOLEAN,
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    created_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Source (
    id STRING PRIMARY KEY,
    source_type STRING,
    url STRING,
    title STRING,
    author STRING,
    publication_date TIMESTAMP,
    copyright_status STRING,
    reliability_score DOUBLE,
    created_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Speaker (
    id STRING PRIMARY KEY,
    name STRING,
    persona STRING,
    voice_id STRING,
    language STRING
);

CREATE NODE TABLE IF NOT EXISTS Segment (
    id STRING PRIMARY KEY,
    text STRING,
    sequence_num INT64,
    emotion STRING,
    duration_seconds DOUBLE,
    word_count INT64,
    created_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Episode (
    id STRING PRIMARY KEY,
    title STRING,
    topic STRING,
    language STRING,
    format STRING,
    duration_minutes INT64,
    quality_score DOUBLE,
    created_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS UserInput (
    id STRING PRIMARY KEY,
    input_type STRING,
    source_path STRING,
    raw_content STRING,
    processed_content STRING,
    created_at TIMESTAMP
);

-- Relationship Tables (Edges)

CREATE REL TABLE IF NOT EXISTS MENTIONS (
    FROM Segment TO Topic,
    strength DOUBLE
);

CREATE REL TABLE IF NOT EXISTS ABOUT (
    FROM Fact TO Topic,
    relevance DOUBLE
);

CREATE REL TABLE IF NOT EXISTS SUPPORTS (
    FROM Fact TO Fact,
    confidence DOUBLE
);

CREATE REL TABLE IF NOT EXISTS CONTRADICTS (
    FROM Fact TO Fact,
    severity STRING
);

CREATE REL TABLE IF NOT EXISTS SOURCED_FROM (
    FROM Fact TO Source,
    page_number INT64,
    quote STRING
);

CREATE REL TABLE IF NOT EXISTS EXTRACTED_FROM (
    FROM Fact TO UserInput,
    extraction_method STRING
);

CREATE REL TABLE IF NOT EXISTS SPOKEN_BY (
    FROM Segment TO Speaker
);

CREATE REL TABLE IF NOT EXISTS FOLLOWS (
    FROM Segment TO Segment,
    transition_type STRING
);

CREATE REL TABLE IF NOT EXISTS PART_OF (
    FROM Segment TO Episode
);

CREATE REL TABLE IF NOT EXISTS CITES (
    FROM Segment TO Fact,
    citation_style STRING
);
"""


# ============================================================================
# PYTHON DATACLASSES FOR GRAPH OPERATIONS
# ============================================================================

@dataclass
class TopicNode:
    """A topic entity in the graph"""
    id: str
    name: str
    description: str = ""
    category: str = "general"
    importance_score: float = 0.5
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class FactNode:
    """A fact/claim entity in the graph"""
    id: str
    claim: str
    confidence: float = 0.8
    verified: bool = False
    valid_from: datetime = None
    valid_until: datetime = None      # None means still valid
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.valid_from is None:
            self.valid_from = datetime.now()


@dataclass
class SourceNode:
    """A source/reference entity in the graph"""
    id: str
    source_type: str                  # "pdf", "url", "audio", "user_input"
    url: str = ""
    title: str = ""
    author: str = ""
    publication_date: datetime = None
    copyright_status: str = "unknown"  # "user_owned", "public_domain", "copyrighted"
    reliability_score: float = 0.5
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class SegmentNode:
    """A podcast segment entity in the graph"""
    id: str
    text: str
    sequence_num: int
    emotion: str = "neutral"
    duration_seconds: float = 0.0
    word_count: int = 0
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.word_count == 0:
            self.word_count = len(self.text.split())


# ============================================================================
# COMMON QUERIES
# ============================================================================

QUERIES = {
    # Find all facts about a topic
    "facts_about_topic": """
        MATCH (f:Fact)-[:ABOUT]->(t:Topic)
        WHERE t.name = $topic_name
        RETURN f.id, f.claim, f.confidence, f.verified
        ORDER BY f.confidence DESC
    """,

    # Find unsupported claims in segments
    "unsupported_claims": """
        MATCH (s:Segment)-[:CITES]->(f:Fact)
        WHERE NOT EXISTS { (f)-[:SOURCED_FROM]->(:Source) }
        RETURN s.id, f.claim AS unsupported_claim
    """,

    # Find contradicting facts
    "contradictions": """
        MATCH (f1:Fact)-[:CONTRADICTS]->(f2:Fact)
        WHERE f1.verified = true AND f2.verified = true
        RETURN f1.claim, f2.claim, "contradiction" AS issue
    """,

    # Get segment flow for an episode
    "episode_flow": """
        MATCH (e:Episode {id: $episode_id})<-[:PART_OF]-(s:Segment)
        OPTIONAL MATCH (s)-[:SPOKEN_BY]->(sp:Speaker)
        RETURN s.sequence_num, s.text, sp.name AS speaker
        ORDER BY s.sequence_num
    """,

    # Find abrupt topic transitions
    "abrupt_transitions": """
        MATCH (s1:Segment)-[:FOLLOWS]->(s2:Segment)
        MATCH (s1)-[:MENTIONS]->(t1:Topic)
        MATCH (s2)-[:MENTIONS]->(t2:Topic)
        WHERE t1 <> t2
        RETURN s1.id, s2.id, t1.name AS from_topic, t2.name AS to_topic
    """,

    # Get provenance chain for a fact
    "fact_provenance": """
        MATCH path = (f:Fact {id: $fact_id})-[:SOURCED_FROM|EXTRACTED_FROM*1..3]->(source)
        RETURN path
    """,

    # Find all facts from a specific source
    "facts_from_source": """
        MATCH (f:Fact)-[:SOURCED_FROM]->(s:Source {id: $source_id})
        RETURN f.id, f.claim, f.confidence
    """
}
