"""
self-model: A machine-readable knowledge graph of the codebase architecture.

This package provides tools and data structures to represent the architecture
of a software codebase as a machine-readable knowledge graph. It enables
automated analysis, querying, and reasoning about the structure, dependencies,
and relationships within the code.
"""

from .knowledge_graph import KnowledgeGraph
from .component_scanner import ComponentScanner, Component
from .dependency_analyzer import DependencyAnalyzer, DependencyRecord
from .interface_discovery import InterfaceDiscovery
from .builder import SelfModelBuilder

__all__ = [
    "KnowledgeGraph",
    "ComponentScanner",
    "Component",
    "DependencyAnalyzer",
    "DependencyRecord",
    "InterfaceDiscovery",
    "SelfModelBuilder",
]