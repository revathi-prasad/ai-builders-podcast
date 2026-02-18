"""Knowledge Graph integration with Kuzu"""
from .schema import (
    EntityType,
    RelationshipType,
    TopicNode,
    FactNode,
    SourceNode,
    SegmentNode,
    SCHEMA_DDL,
    QUERIES
)
from .manager import KnowledgeGraphManager

__all__ = [
    "EntityType",
    "RelationshipType",
    "TopicNode",
    "FactNode",
    "SourceNode",
    "SegmentNode",
    "SCHEMA_DDL",
    "QUERIES",
    "KnowledgeGraphManager"
]
