from pathlib import Path
import json
import logging
from typing import Optional, Dict, List, Any
import ast
import importlib.util

from self_model.component_scanner import ComponentScanner as Scanner
from self_model.dependency_analyzer import DependencyAnalyzer as Analyzer
from self_model.interface_discovery import InterfaceDiscovery as Discovery
from self_model.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class SelfModelBuilder:
    """Orchestrates the self-modeling pipeline: scan, analyze, extract, discover,
    populate the KnowledgeGraph, and serialize it to JSON."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.scanner = Scanner(self.project_root)
        self.analyzer = Analyzer()
        self.discovery = Discovery()
        self.knowledge_graph = KnowledgeGraph()
        self.output_path = self.project_root / "self_model_graph.json"
        self.interface_usage_path = self.project_root / "interface_usage_map.json"
        self.interface_usage_map = {}

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

        # Step 3: Discover implicit patterns
        logger.info("Step 3: Discovering implicit patterns...")
        discovery_results = self.discovery.discover(analysis_results)
        logger.info(f"Discovery completed: {len(discovery_results)} discoveries.")

        # Step 5: Populate knowledge graph
        logger.info("Step 5: Populating knowledge graph...")
        self.knowledge_graph.populate(discovery_results)
        logger.info(f"Knowledge graph populated with {len(self.knowledge_graph.nodes)} nodes "
                     f"and {len(self.knowledge_graph.edges)} edges.")

        # Step 6: Update interface usage map
        logger.info("Step 6: Updating interface usage map...")
        self.update_interface_usage()

        # Step 7: Serialize to JSON
        logger.info(f"Step 7: Serializing knowledge graph to {self.output_path}...")
        self._serialize()
        logger.info("Self-model building pipeline completed successfully.")

        return self.output_path

    def update_interface_usage(self) -> None:
        """Re-scan all modules and update the interface_usage_map.
        This should be called after each successful mutation to keep the self-model current."""
        logger.info("Updating interface usage map...")
        self.interface_usage_map = self._analyze_interface_usage()
        self._save_interface_usage_map(self.interface_usage_map)
        logger.info(f"Interface usage map updated with {len(self.interface_usage_map)} entries.")

    def get_impact_analysis(self, mutation: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structured impact report for a given mutation.
        
        Args:
            mutation: A dictionary describing the mutation. Expected keys:
                - "type": str (e.g., "modify", "add", "delete")
                - "module": str (module path relative to project root)
                - "interface": str (name of the interface being mutated)
                - "details": dict (optional, additional mutation details)
        
        Returns:
            A dictionary with the following structure:
            {
                "mutation": { ... },  # The original mutation
                "direct_consumers": [str],  # Modules that directly use the mutated interface
                "indirect_consumers": [str],  # Modules that indirectly depend on the interface
                "affected_interfaces": [str],  # Other interfaces that may be affected
                "risk_level": str,  # "low", "medium", "high"
                "recommendations": [str]  # Suggested actions
            }
        """
        mutation_type = mutation.get("type", "unknown")
        module = mutation.get("module", "")
        interface_name = mutation.get("interface", "")
        details = mutation.get("details", {})
        
        # Build the interface key
        interface_key = f"{module}:{interface_name}"
        
        # Find direct consumers from the interface usage map
        direct_consumers = self.interface_usage_map.get(interface_key, [])
        
        # Find indirect consumers by checking which modules use the direct consumers
        indirect_consumers = set()
        for consumer in direct_consumers:
            # Check if the consumer module has its own interfaces that are used elsewhere
            for key, users in self.interface_usage_map.items():
                if key.startswith(f"{consumer}:"):
                    for user in users:
                        if user not in direct_consumers and user != module:
                            indirect_consumers.add(user)
        
        # Find affected interfaces (other interfaces in the same module or related modules)
        affected_interfaces = []
        for key in self.interface_usage_map:
            if key.startswith(f"{module}:") and key != interface_key:
                affected_interfaces.append(key)
        
        # Determine risk level based on the number of consumers and mutation type
        total_consumers = len(direct_consumers) + len(indirect_consumers)
        if mutation_type == "delete":
            if total_consumers > 5:
                risk_level = "high"
            elif total_consumers > 0:
                risk_level = "medium"
            else:
                risk_level = "low"
        elif mutation_type == "modify":
            if total_consumers > 10:
                risk_level = "high"
            elif total_consumers > 3:
                risk_level = "medium"
            else:
                risk_level = "low"
        else:  # add or other types
            risk_level = "low"
        
        # Generate recommendations
        recommendations = []
        if risk_level == "high":
            recommendations.append(f"Consider creating a deprecation plan for {interface_key}")
            recommendations.append("Notify all dependent module maintainers")
            recommendations.append("Run comprehensive tests before deploying the mutation")
        elif risk_level == "medium":
            recommendations.append(f"Review all {len(direct_consumers)} direct consumers of {interface_key}")
            recommendations.append("Update documentation for the changed interface")
        else:
            recommendations.append("Low impact mutation - standard review process applies")
        
        if mutation_type == "delete":
            recommendations.append(f"Ensure no critical functionality depends on {interface_key}")
        
        # Build the impact report
        impact_report = {
            "mutation": mutation,
            "direct_consumers": direct_consumers,
            "indirect_consumers": list(indirect_consumers),
            "affected_interfaces": affected_interfaces,
            "risk_level": risk_level,
            "recommendations": recommendations
        }
        
        return impact_report

    def _get_public_interfaces(self) -> Dict[str, List[Dict[str, Any]]]:
        """Extract public functions and classes from all Python files in the project.
        
        Returns:
            A dictionary mapping module paths to lists of public interfaces.
            Each interface has: name, type (function/class), and line number.
        """
        public_interfaces = {}
        
        for py_file in self.project_root.rglob("*.py"):
            if "venv" in str(py_file) or ".env" in str(py_file):
                continue
                
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue
                
            module_path = str(py_file.relative_to(self.project_root))
            interfaces = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        interfaces.append({
                            "name": node.name,
                            "type": "function",
                            "line": node.lineno
                        })
                elif isinstance(node, ast.ClassDef):
                    if not node.name.startswith("_"):
                        methods = []
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if not item.name.startswith("_"):
                                    methods.append({
                                        "name": item.name,
                                        "type": "method",
                                        "line": item.lineno
                                    })
                        interfaces.append({
                            "name": node.name,
                            "type": "class",
                            "line": node.lineno,
                            "methods": methods
                        })
            
            if interfaces:
                public_interfaces[module_path] = interfaces
                
        return public_interfaces

    def _analyze_interface_usage(self) -> Dict[str, List[str]]:
        """Analyze all Python files to find which modules call/use public interfaces.
        
        Returns:
            A dictionary mapping each public interface (as 'module:name') to a list
            of modules that use it.
        """
        public_interfaces = self._get_public_interfaces()
        interface_usage = {}
        
        # Build a lookup of interface names to their defining modules
        interface_to_module = {}
        for module, interfaces in public_interfaces.items():
            for interface in interfaces:
                key = f"{module}:{interface['name']}"
                interface_to_module[interface['name']] = key
                if interface['type'] == 'class':
                    for method in interface.get('methods', []):
                        method_key = f"{module}:{interface['name']}.{method['name']}"
                        interface_to_module[f"{interface['name']}.{method['name']}"] = method_key
        
        # Scan all Python files for usage
        for py_file in self.project_root.rglob("*.py"):
            if "venv" in str(py_file) or ".env" in str(py_file):
                continue
                
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue
                
            module_path = str(py_file.relative_to(self.project_root))
            used_interfaces = set()
            
            for node in ast.walk(tree):
                # Function calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        if func_name in interface_to_module:
                            used_interfaces.add(interface_to_module[func_name])
                    elif isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name):
                            obj_name = node.func.value.id
                            attr_name = node.func.attr
                            # Check for class instantiation or method call
                            if obj_name in interface_to_module:
                                used_interfaces.add(interface_to_module[obj_name])
                            full_name = f"{obj_name}.{attr_name}"
                            if full_name in interface_to_module:
                                used_interfaces.add(interface_to_module[full_name])
                
                # Class instantiations (handled by Call with Name)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    class_name = node.func.id
                    if class_name in interface_to_module:
                        used_interfaces.add(interface_to_module[class_name])
                
                # Attribute accesses
                if isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        obj_name = node.value.id
                        attr_name = node.attr
                        full_name = f"{obj_name}.{attr_name}"
                        if full_name in interface_to_module:
                            used_interfaces.add(interface_to_module[full_name])
            
            # Record usage for this module
            for interface_key in used_interfaces:
                if interface_key not in interface_usage:
                    interface_usage[interface_key] = []
                if module_path not in interface_usage[interface_key]:
                    interface_usage[interface_key].append(module_path)
        
        return interface_usage

    def get_dependency_graph(self) -> Dict[str, Any]:
        """Return the current dependency graph in a format consumable by DependencyResolver.
        
        Returns:
            A dictionary containing nodes and edges representing the dependency graph,
            along with a list of critical interfaces that are depended upon by other modules,
            and an interface_usage_map showing which modules use each public interface.
            Format: {
                "nodes": [{"id": str, "type": str, "name": str, ...}],
                "edges": [{"source": str, "target": str, "type": str, ...}],
                "critical_interfaces": [...],
                "interface_usage_map": {
                    "module:interface_name": ["module1", "module2", ...]
                }
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
        
        # Generate and add interface_usage_map
        logger.info("Analyzing interface usage across the project...")
        interface_usage_map = self._analyze_interface_usage()
        graph_data["interface_usage_map"] = interface_usage_map
        self.interface_usage_map = interface_usage_map
        
        # Persist interface_usage_map to JSON file
        self._save_interface_usage_map(interface_usage_map)
        
        return graph_data

    def _save_interface_usage_map(self, interface_usage_map: Dict[str, List[str]]) -> None:
        """Save the interface usage map to a persistent JSON file."""
        try:
            with open(self.interface_usage_path, "w", encoding="utf-8") as f:
                json.dump(interface_usage_map, f, indent=2, ensure_ascii=False)
            logger.debug(f"Interface usage map saved to {self.interface_usage_path}")
        except Exception as e:
            logger.error(f"Failed to save interface usage map: {e}")

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

    def map_failure_pattern_to_component(self, pattern: str) -> List[Dict[str, Any]]:
        """Identify which components are most likely causing a given failure pattern
        using the self-model's dependency graph.
        
        Args:
            pattern: A string describing the failure pattern (e.g., "import error",
                    "attribute error", "type mismatch", "circular dependency")
        
        Returns:
            A list of dictionaries, each containing:
                - "component": str (the component/module name)
                - "confidence": float (0.0 to 1.0, how likely this component is the cause)
                - "reason": str (explanation of why this component is suspected)
                - "related_interfaces": list[str] (interfaces involved in the pattern)
        """
        logger.info(f"Mapping failure pattern '{pattern}' to components...")
        
        # Normalize the pattern for matching
        pattern_lower = pattern.lower()
        
        # Get the dependency graph data
        graph_data = self.get_dependency_graph()
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        interface_usage = graph_data.get("interface_usage_map", {})
        critical_interfaces = graph_data.get("critical_interfaces", [])
        
        # Build a map of node IDs to node data for quick lookup
        node_map = {}
        for node in nodes:
            node_map[node.get("id")] = node
        
        # Build a map of which nodes depend on which (source -> targets)
        dependency_map = {}
        for edge in edges:
            edge_type = edge.get("type", "")
            source = edge.get("source")
            target = edge.get("target")
            
            if edge_type in ("depends_on", "imports", "uses"):
                if source not in dependency_map:
                    dependency_map[source] = []
                dependency_map[source].append(target)
        
        # Initialize results
        results = []
        
        # Analyze based on pattern type
        if "import" in pattern_lower or "module" in pattern_lower:
            # Import-related failures: check for missing or broken imports
            for node in nodes:
                node_id = node.get("id")
                node_name = node.get("name", "")
                node_type = node.get("type", "")
                
                # Check if this node is imported by others
                imported_by = []
                for edge in edges:
                    if edge.get("type") == "imports" and edge.get("target") == node_id:
                        imported_by.append(edge.get("source"))
                
                if imported_by:
                    # This module is imported by others - could be the source of import errors
                    confidence = min(0.7, 0.3 + 0.1 * len(imported_by))
                    results.append({
                        "component": node_name,
                        "confidence": confidence,
                        "reason": f"Module '{node_name}' is imported by {len(imported_by)} other modules. "
                                  f"An import error in this module would affect all dependents.",
                        "related_interfaces": [f"{node.get('module', '')}:{node_name}" 
                                              for node in [node] if node.get('module')]
                    })
        
        elif "attribute" in pattern_lower or "method" in pattern_lower or "missing" in pattern_lower:
            # Attribute/method missing errors: check interfaces that are heavily used
            for interface_key, users in interface_usage.items():
                if len(users) > 0:
                    module_name, interface_name = interface_key.split(":", 1)
                    confidence = min(0.8, 0.2 + 0.15 * len(users))
                    results.append({
                        "component": module_name,
                        "confidence": confidence,
                        "reason": f"Interface '{interface_name}' in module '{module_name}' is used by "
                                  f"{len(users)} other modules. Missing or changed attributes here "
                                  f"would cause attribute errors in dependents.",
                        "related_interfaces": [interface_key]
                    })
        
        elif "type" in pattern_lower or "mismatch" in pattern_lower:
            # Type mismatch errors: check interfaces with complex signatures
            for ci in critical_interfaces:
                if ci.get("signature"):
                    module_name = ci.get("module", "")
                    interface_name = ci.get("interface_name", "")
                    depended_by = ci.get("depended_by", [])
                    
                    if len(depended_by) > 0:
                        confidence = min(0.75, 0.25 + 0.1 * len(depended_by))
                        results.append({
                            "component": module_name,
                            "confidence": confidence,
                            "reason": f"Interface '{interface_name}' in module '{module_name}' has a "
                                      f"defined signature and is depended upon by {len(depended_by)} "
                                      f"other modules. Type mismatches in this interface would "
                                      f"propagate to all dependents.",
                            "related_interfaces": [f"{module_name}:{interface_name}"]
                        })
        
        elif "circular" in pattern_lower or "cycle" in pattern_lower:
            # Circular dependency: find cycles in the dependency graph
            # Simple cycle detection using DFS
            visited = set()
            path = []
            
            def dfs(node_id, path_set):
                if node_id in path_set:
                    # Found a cycle
                    cycle_start = path.index(node_id)
                    cycle = path[cycle_start:]
                    return cycle
                if node_id in visited:
                    return None
                
                visited.add(node_id)
                path.append(node_id)
                path_set.add(node_id)
                
                for neighbor in dependency_map.get(node_id, []):
                    result = dfs(neighbor, path_set)
                    if result:
                        return result
                
                path.pop()
                path_set.remove(node_id)
                return None
            
            for node in nodes:
                node_id = node.get("id")
                if node_id not in visited:
                    cycle = dfs(node_id, set())
                    if cycle:
                        for node_id_in_cycle in cycle:
                            node_data = node_map.get(node_id_in_cycle, {})
                            results.append({
                                "component": node_data.get("name", node_id_in_cycle),
                                "confidence": 0.9,
                                "reason": f"Component is part of a circular dependency chain: "
                                          f"{' -> '.join([node_map.get(n, {}).get('name', n) for n in cycle])}",
                                "related_interfaces": [f"{node_data.get('module', '')}:{node_data.get('name', '')}" 
                                                      for node_data in [node_data] if node_data.get('module')]
                            })
        
        else:
            # Generic pattern: look for highly connected components
            for node in nodes:
                node_id = node.get("id")
                node_name = node.get("name", "")
                
                # Count incoming and outgoing edges
                incoming = sum(1 for edge in edges if edge.get("target") == node_id)
                outgoing = sum(1 for edge in edges if edge.get("source") == node_id)
                
                # Components with high connectivity are more likely to cause failures
                total_connections = incoming + outgoing
                if total_connections > 2:
                    confidence = min(0.6, 0.1 + 0.1 * total_connections)
                    results.append({
                        "component": node_name,
                        "confidence": confidence,
                        "reason": f"Component has {total_connections} connections in the dependency graph "
                                  f"({incoming} incoming, {outgoing} outgoing). Highly connected components "
                                  f"are more likely to be the source of failures.",
                        "related_interfaces": [f"{node.get('module', '')}:{node_name}" 
                                              for node in [node] if node.get('module')]
                    })
        
        # Sort results by confidence (highest first)
        results.sort(key=lambda x: x["confidence"], reverse=True)
        
        # Limit to top 10 results to avoid overwhelming output
        results = results[:10]
        
        logger.info(f"Found {len(results)} potential components for failure pattern '{pattern}'")
        return results