import json
import ast
import os
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Mismatch:
    module: str
    description: str
    severity: Severity
    details: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RepairTicket:
    module: str
    mismatch: Mismatch
    suggested_action: str
    ticket_id: str = field(default_factory=lambda: f"TICKET-{datetime.now().strftime('%Y%m%d%H%M%S%f')}")


class DependencyGraph:
    def __init__(self, graph_path: str = "dependency_graph.json"):
        self.graph_path = graph_path
        self.graph: Dict[str, Dict[str, Any]] = self._load_graph()

    def _load_graph(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.graph_path):
            with open(self.graph_path, 'r') as f:
                return json.load(f)
        return {}

    def save_graph(self):
        with open(self.graph_path, 'w') as f:
            json.dump(self.graph, f, indent=2)

    def update_module(self, module_name: str, data: Dict[str, Any]):
        self.graph[module_name] = data
        self.save_graph()

    def get_module(self, module_name: str) -> Optional[Dict[str, Any]]:
        return self.graph.get(module_name)

    def get_all_modules(self) -> List[str]:
        return list(self.graph.keys())


class InterfaceExtractor:
    @staticmethod
    def extract_imports(tree: ast.AST) -> List[str]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        return imports

    @staticmethod
    def extract_exports(tree: ast.AST) -> Dict[str, Dict[str, Any]]:
        exports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                exports[node.name] = {
                    "type": "function",
                    "args": [arg.arg for arg in node.args.args],
                    "decorators": [ast.dump(d) for d in node.decorator_list]
                }
            elif isinstance(node, ast.ClassDef):
                exports[node.name] = {
                    "type": "class",
                    "bases": [ast.dump(b) for b in node.bases],
                    "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                }
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        exports[target.id] = {
                            "type": "variable",
                            "value": ast.dump(node.value)
                        }
        return exports

    @staticmethod
    def extract_schemas(tree: ast.AST) -> Dict[str, Dict[str, Any]]:
        schemas = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(d, ast.Name) and d.id in ("TypedDict", "BaseModel", "Schema")
                for d in node.bases
            ):
                fields = {}
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        fields[item.target.id] = ast.dump(item.annotation) if item.annotation else "Any"
                schemas[node.name] = {"fields": fields}
        return schemas

    @staticmethod
    def extract_call_sites(tree: ast.AST) -> List[Dict[str, Any]]:
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    calls.append({
                        "module": ast.dump(node.func.value),
                        "function": node.func.attr,
                        "args": [ast.dump(a) for a in node.args]
                    })
                elif isinstance(node.func, ast.Name):
                    calls.append({
                        "module": "",
                        "function": node.func.id,
                        "args": [ast.dump(a) for a in node.args]
                    })
        return calls

    @staticmethod
    def extract_from_file(filepath: str) -> Optional[Dict[str, Any]]:
        try:
            with open(filepath, 'r') as f:
                source = f.read()
            tree = ast.parse(source, filename=filepath)
            return {
                "imports": InterfaceExtractor.extract_imports(tree),
                "exports": InterfaceExtractor.extract_exports(tree),
                "schemas": InterfaceExtractor.extract_schemas(tree),
                "call_sites": InterfaceExtractor.extract_call_sites(tree)
            }
        except (SyntaxError, FileNotFoundError, IOError) as e:
            print(f"Error parsing {filepath}: {e}")
            return None


class SelfModelConsistencyValidator:
    def __init__(self, graph_path: str = "dependency_graph.json"):
        self.graph = DependencyGraph(graph_path)
        self.extractor = InterfaceExtractor()
        self.mismatches: List[Mismatch] = []
        self.repair_tickets: List[RepairTicket] = []

    def validate_modified_files(self, modified_files: List[str]) -> List[Mismatch]:
        self.mismatches.clear()
        self.repair_tickets.clear()

        for filepath in modified_files:
            module_name = os.path.splitext(os.path.basename(filepath))[0]
            current_data = self.extractor.extract_from_file(filepath)
            if current_data is None:
                continue

            stored_data = self.graph.get_module(module_name)
            if stored_data is None:
                self.graph.update_module(module_name, current_data)
                continue

            # Compare imports
            self._compare_imports(module_name, stored_data.get("imports", []), current_data["imports"])
            # Compare exports
            self._compare_exports(module_name, stored_data.get("exports", {}), current_data["exports"])
            # Compare schemas
            self._compare_schemas(module_name, stored_data.get("schemas", {}), current_data["schemas"])
            # Compare call sites
            self._compare_call_sites(module_name, stored_data.get("call_sites", []), current_data["call_sites"])

            # Update graph with current data
            self.graph.update_module(module_name, current_data)

        return self.mismatches

    def _compare_imports(self, module: str, stored: List[str], current: List[str]):
        removed = set(stored) - set(current)
        added = set(current) - set(stored)
        for imp in removed:
            mismatch = Mismatch(
                module=module,
                description=f"Import removed: {imp}",
                severity=Severity.CRITICAL,
                details={"removed_import": imp}
            )
            self.mismatches.append(mismatch)
            self.repair_tickets.append(RepairTicket(
                module=module,
                mismatch=mismatch,
                suggested_action=f"Restore import '{imp}' or update dependent modules"
            ))

    def _compare_exports(self, module: str, stored: Dict[str, Any], current: Dict[str, Any]):
        stored_names = set(stored.keys())
        current_names = set(current.keys())
        removed = stored_names - current_names
        for name in removed:
            mismatch = Mismatch(
                module=module,
                description=f"Export removed: {name}",
                severity=Severity.CRITICAL,
                details={"removed_export": name, "stored_type": stored[name].get("type")}
            )
            self.mismatches.append(mismatch)
            self.repair_tickets.append(RepairTicket(
                module=module,
                mismatch=mismatch,
                suggested_action=f"Restore export '{name}' or update all callers"
            ))

        common = stored_names & current_names
        for name in common:
            stored_item = stored[name]
            current_item = current[name]
            if stored_item.get("type") != current_item.get("type"):
                mismatch = Mismatch(
                    module=module,
                    description=f"Export type changed for '{name}': {stored_item.get('type')} -> {current_item.get('type')}",
                    severity=Severity.CRITICAL,
                    details={"export": name, "old_type": stored_item.get("type"), "new_type": current_item.get("type")}
                )
                self.mismatches.append(mismatch)
                self.repair_tickets.append(RepairTicket(
                    module=module,
                    mismatch=mismatch,
                    suggested_action=f"Update all callers of '{name}' to match new type"
                ))
            elif stored_item.get("type") == "function":
                if stored_item.get("args") != current_item.get("args"):
                    mismatch = Mismatch(
                        module=module,
                        description=f"Function signature changed for '{name}'",
                        severity=Severity.CRITICAL,
                        details={"function": name, "old_args": stored_item.get("args"), "new_args": current_item.get("args")}
                    )
                    self.mismatches.append(mismatch)
                    self.repair_tickets.append(RepairTicket(
                        module=module,
                        mismatch=mismatch,
                        suggested_action=f"Update all callers of '{name}' to match new signature"
                    ))

    def _compare_schemas(self, module: str, stored: Dict[str, Any], current: Dict[str, Any]):
        stored_schemas = set(stored.keys())
        current_schemas = set(current.keys())
        removed = stored_schemas - current_schemas
        for schema in removed:
            mismatch = Mismatch(
                module=module,
                description=f"Schema removed: {schema}",
                severity=Severity.CRITICAL,
                details={"removed_schema": schema}
            )
            self.mismatches.append(mismatch)
            self.repair_tickets.append(RepairTicket(
                module=module,
                mismatch=mismatch,
                suggested_action=f"Restore schema '{schema}' or update all consumers"
            ))

        common = stored_schemas & current_schemas
        for schema in common:
            stored_fields = set(stored[schema].get("fields", {}).keys())
            current_fields = set(current[schema].get("fields", {}).keys())
            removed_fields = stored_fields - current_fields
            for field in removed_fields:
                mismatch = Mismatch(
                    module=module,
                    description=f"Schema field removed: '{schema}.{field}'",
                    severity=Severity.CRITICAL,
                    details={"schema": schema, "removed_field": field}
                )
                self.mismatches.append(mismatch)
                self.repair_tickets.append(RepairTicket(
                    module=module,
                    mismatch=mismatch,
                    suggested_action=f"Restore field '{field}' in schema '{schema}' or update all consumers"
                ))

    def _compare_call_sites(self, module: str, stored: List[Dict[str, Any]], current: List[Dict[str, Any]]):
        # Simple comparison: check if any call sites changed significantly
        stored_calls = {(c.get("module", ""), c.get("function", "")) for c in stored}
        current_calls = {(c.get("module", ""), c.get("function", "")) for c in current}
        removed = stored_calls - current_calls
        for call in removed:
            mismatch = Mismatch(
                module=module,
                description=f"Call site removed: {call[0]}.{call[1]}",
                severity=Severity.WARNING,
                details={"removed_call": {"module": call[0], "function": call[1]}}
            )
            self.mismatches.append(mismatch)

    def get_repair_tickets(self) -> List[RepairTicket]:
        return self.repair_tickets

    def get_mismatches_by_severity(self, severity: Severity) -> List[Mismatch]:
        return [m for m in self.mismatches if m.severity == severity]

    def output_report(self, output_path: str = "consistency_report.json"):
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_mismatches": len(self.mismatches),
            "mismatches": [asdict(m) for m in self.mismatches],
            "repair_tickets": [asdict(t) for t in self.repair_tickets]
        }
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Consistency report saved to {output_path}")


# Example usage (commented out)
if __name__ == "__main__":
    validator = SelfModelConsistencyValidator()
    # Simulate modified files
    modified = ["example_module.py"]
    mismatches = validator.validate_modified_files(modified)
    for m in mismatches:
        print(f"[{m.severity.value}] {m.module}: {m.description}")
    tickets = validator.get_repair_tickets()
    for t in tickets:
        print(f"Ticket {t.ticket_id}: {t.suggested_action}")
    validator.output_report()