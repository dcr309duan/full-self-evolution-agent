from pathlib import Path
import json
import logging
from typing import Optional, Dict, List, Any

from self_model.scanner import Scanner
from self_model.analyzer import Analyzer
from self_model.extractor import Extractor
from self_model.discovery import Discovery
from self_model.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class SelfModelBuilder:
    """Orchestrates the self-modeling pipeline: scan, analyze, extract, discover,
    populate the KnowledgeGraph, and serialize it to JSON."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.scanner = Scanner(self.project_root)
        self.analyzer = Analyzer()
        self.extractor = Extractor()
        self.discovery = Discovery()
        self.knowledge_graph = KnowledgeGraph()
        self.output_path = self.project_root / "self_model_graph.json"

    def run(self) -> Path:
        """Execute the full pipeline and return the path to the serialized graph."""
        logger.info("Starting self-model building pipeline...")

        # Step 1: Scan the project
        logger.info("Step 1: Scanning project structure...")
        scan_results = self.scanner.scan()
        logger.info(f"Scan completed: found {len(scan_results)} items.")

        # Step 2: Analyze scanned items
        logger.info("Step 2: Analyzing scanned items...")
        analysis_results = self.analyzer.analyze(scan_results)
        logger.info(f"Analysis completed: {len(analysis_results)} items analyzed.")

        # Step 3: Extract entities and relationships
        logger.info("Step 3: Extracting entities and relationships...")
        extraction_results = self.extractor.extract(analysis_results)
        logger.info(f"Extraction completed: {len(extraction_results)} extractions.")

        # Step 4: Discover implicit patterns
        logger.info("Step 4: Discovering implicit patterns...")
        discovery_results = self.discovery.discover(extraction_results)
        logger.info(f"Discovery completed: {len(discovery_results)} discoveries.")

        # Step 5: Populate knowledge graph
        logger.info("Step 5: Populating knowledge graph...")
        self.knowledge_graph.populate(discovery_results)
        logger.info(f"Knowledge graph populated with {len(self.knowledge_graph.nodes)} nodes "
                     f"and {len(self.knowledge_graph.edges)} edges.")

        # Step 6: Serialize to JSON
        logger.info(f"Step 6: Serializing knowledge graph to {self.output_path}...")
        self._serialize()
        logger.info("Self-model building pipeline completed successfully.")

        return self.output_path

    def get_dependency_graph(self) -> Dict[str, Any]:
        """Return the current dependency graph in a format consumable by DependencyResolver.
        
        Returns:
            A dictionary containing nodes and edges representing the dependency graph,
            along with a list of critical interfaces that are depended upon by other modules.
            Format: {
                "nodes": [{"id": str, "type": str, "name": str, ...}],
                "edges": [{"source": str, "target": str, "type": str, ...}],
                "critical_interfaces": [
                    {
                        "module": str,
                        "interface_name": str,
                        "interface_type": str,  # "function", "class", "method", "attribute"
                        "signature": str,
                        "depended_by": [str]  # list of module names that depend on this interface
                    }
                ]
            }
        """
        # Build base graph data
        graph_data = {
            "nodes": [node.to_dict() for node in self.knowledge_graph.nodes],
            "edges": [edge.to_dict() for edge in self.knowledge_graph.edges]
        }
        
        # Extract critical interfaces from the knowledge graph
        critical_interfaces = []
        
        # Iterate through edges to find dependency relationships
        for edge in self.knowledge_graph.edges:
            edge_dict = edge.to_dict()
            if edge_dict.get("type") == "depends_on":
                source = edge_dict.get("source")
                target = edge_dict.get("target")
                
                # Find the target node to get its interface details
                target_node = None
                for node in self.knowledge_graph.nodes:
                    node_dict = node.to_dict()
                    if node_dict.get("id") == target:
                        target_node = node_dict
                        break
                
                if target_node:
                    # Extract interface information from the target node
                    interface_info = {
                        "module": target_node.get("module", target_node.get("name", "unknown")),
                        "interface_name": target_node.get("name", "unknown"),
                        "interface_type": target_node.get("type", "unknown"),
                        "signature": target_node.get("signature", ""),
                        "depended_by": [source]
                    }
                    
                    # Check if this interface already exists in critical_interfaces
                    existing = None
                    for ci in critical_interfaces:
                        if (ci["module"] == interface_info["module"] and 
                            ci["interface_name"] == interface_info["interface_name"]):
                            existing = ci
                            break
                    
                    if existing:
                        # Add the source to the depended_by list if not already present
                        if source not in existing["depended_by"]:
                            existing["depended_by"].append(source)
                    else:
                        critical_interfaces.append(interface_info)
        
        # Also check for import relationships that indicate dependency
        for edge in self.knowledge_graph.edges:
            edge_dict = edge.to_dict()
            if edge_dict.get("type") == "imports":
                source = edge_dict.get("source")
                target = edge_dict.get("target")
                
                # Find the target node
                target_node = None
                for node in self.knowledge_graph.nodes:
                    node_dict = node.to_dict()
                    if node_dict.get("id") == target:
                        target_node = node_dict
                        break
                
                if target_node:
                    # For imports, the critical interface is the module itself
                    interface_info = {
                        "module": target_node.get("module", target_node.get("name", "unknown")),
                        "interface_name": target_node.get("name", "unknown"),
                        "interface_type": "module",
                        "signature": "",
                        "depended_by": [source]
                    }
                    
                    # Check if this interface already exists
                    existing = None
                    for ci in critical_interfaces:
                        if (ci["module"] == interface_info["module"] and 
                            ci["interface_name"] == interface_info["interface_name"]):
                            existing = ci
                            break
                    
                    if existing:
                        if source not in existing["depended_by"]:
                            existing["depended_by"].append(source)
                    else:
                        critical_interfaces.append(interface_info)
        
        # Add critical_interfaces to the graph data
        graph_data["critical_interfaces"] = critical_interfaces
        
        return graph_data

    def _serialize(self) -> None:
        """Serialize the knowledge graph to a JSON file."""
        graph_data = {
            "metadata": {
                "project_root": str(self.project_root),
                "version": "1.0"
            },
            "nodes": [node.to_dict() for node in self.knowledge_graph.nodes],
            "edges": [edge.to_dict() for edge in self.knowledge_graph.edges]
        }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Knowledge graph serialized to {self.output_path}")