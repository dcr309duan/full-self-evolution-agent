"""
self-model: A machine-readable knowledge graph of the codebase architecture.

This package provides tools and data structures to represent the architecture
of a software codebase as a machine-readable knowledge graph. It enables
automated analysis, querying, and reasoning about the structure, dependencies,
and relationships within the code.

The knowledge graph captures entities such as modules, classes, functions,
and their interconnections, allowing for introspection and self-modeling of
the system's design.
"""

from .graph import KnowledgeGraph, Node, Edge
from .parser import CodebaseParser
from .query import QueryEngine
from .serializer import GraphSerializer
from .component_scanner import ComponentScanner
from .dependency_analyzer import DependencyAnalyzer
from .schema_extractor import SchemaExtractor
from .interface_discovery import InterfaceDiscovery
from .self_model_builder import SelfModelBuilder

__all__ = [
    "KnowledgeGraph",
    "Node",
    "Edge",
    "CodebaseParser",
    "QueryEngine",
    "GraphSerializer",
    "ComponentScanner",
    "DependencyAnalyzer",
    "SchemaExtractor",
    "InterfaceDiscovery",
    "SelfModelBuilder",
]