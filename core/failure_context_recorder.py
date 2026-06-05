import ast
import json
import traceback
import datetime
import sys
import os
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

class FailureContextRecorder:
    """
    A dedicated recorder for capturing comprehensive failure context during mutation testing.
    
    Captures:
    - AST of modified files before and after mutation
    - Full error tracebacks with line numbers
    - Dependency graph state snapshots
    - Current goal queue state
    - Mutation diffs
    - System health metrics (module test pass rates, dependency satisfaction levels)
    
    All context is serialized to JSON with timestamps for later analysis.
    """

    def __init__(self, output_dir: str = "failure_context"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.contexts: List[Dict[str, Any]] = []

    def capture_ast(self, file_path: str, label: str = "current") -> Optional[str]:
        """
        Capture the AST of a file as a string representation.
        
        Args:
            file_path: Path to the source file
            label: Label for this AST capture (e.g., 'before_mutation', 'after_mutation')
            
        Returns:
            AST dump string or None if file cannot be read/parsed
        """
        try:
            with open(file_path, 'r') as f:
                source = f.read()
            tree = ast.parse(source)
            return ast.dump(tree, indent=2)
        except (FileNotFoundError, SyntaxError, Exception) as e:
            return f"Error capturing AST: {str(e)}"

    def capture_traceback(self, exc_info: Optional[Tuple] = None) -> Dict[str, Any]:
        """
        Capture full error traceback with line numbers.
        
        Args:
            exc_info: Optional exception info tuple from sys.exc_info()
            
        Returns:
            Dictionary with traceback details
        """
        if exc_info is None:
            exc_info = sys.exc_info()
        
        if exc_info[0] is None:
            return {"error": "No active exception", "traceback": None}
        
        tb = traceback.extract_tb(exc_info[2])
        frames = []
        for frame in tb:
            frames.append({
                "filename": frame.filename,
                "lineno": frame.lineno,
                "name": frame.name,
                "line": frame.line
            })
        
        return {
            "exception_type": exc_info[0].__name__ if exc_info[0] else None,
            "exception_message": str(exc_info[1]) if exc_info[1] else None,
            "frames": frames,
            "formatted_traceback": traceback.format_exc()
        }

    def snapshot_dependency_graph(self, dependency_graph: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Snapshot the current state of the dependency graph.
        
        Args:
            dependency_graph: Dictionary mapping module names to their dependencies
            
        Returns:
            Dictionary with dependency graph state
        """
        return {
            "total_modules": len(dependency_graph),
            "dependencies": dependency_graph,
            "dependency_counts": {
                module: len(deps) for module, deps in dependency_graph.items()
            }
        }

    def log_goal_queue_state(self, goal_queue: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Log the current state of the goal queue.
        
        Args:
            goal_queue: List of goal dictionaries
            
        Returns:
            Dictionary with goal queue state
        """
        return {
            "queue_length": len(goal_queue),
            "goals": goal_queue,
            "priorities": [goal.get("priority", "unknown") for goal in goal_queue]
        }

    def store_mutation_diff(self, original_source: str, mutated_source: str) -> Dict[str, Any]:
        """
        Store the mutation diff between original and mutated source.
        
        Args:
            original_source: Original source code
            mutated_source: Mutated source code
            
        Returns:
            Dictionary with mutation diff details
        """
        import difflib
        diff = list(difflib.unified_diff(
            original_source.splitlines(keepends=True),
            mutated_source.splitlines(keepends=True),
            fromfile='original',
            tofile='mutated'
        ))
        return {
            "diff": ''.join(diff),
            "original_length": len(original_source),
            "mutated_length": len(mutated_source),
            "has_changes": original_source != mutated_source
        }

    def record_system_health(self, 
                           module_test_pass_rates: Dict[str, float],
                           dependency_satisfaction_levels: Dict[str, float]) -> Dict[str, Any]:
        """
        Record system health metrics.
        
        Args:
            module_test_pass_rates: Dictionary mapping module names to their test pass rates (0.0-1.0)
            dependency_satisfaction_levels: Dictionary mapping module names to their dependency satisfaction levels (0.0-1.0)
            
        Returns:
            Dictionary with system health metrics
        """
        return {
            "module_test_pass_rates": module_test_pass_rates,
            "dependency_satisfaction_levels": dependency_satisfaction_levels,
            "average_test_pass_rate": sum(module_test_pass_rates.values()) / len(module_test_pass_rates) if module_test_pass_rates else 0.0,
            "average_dependency_satisfaction": sum(dependency_satisfaction_levels.values()) / len(dependency_satisfaction_levels) if dependency_satisfaction_levels else 0.0
        }

    def record_failure_context(self,
                              file_path: str,
                              original_ast: Optional[str] = None,
                              mutated_ast: Optional[str] = None,
                              traceback_info: Optional[Dict] = None,
                              dependency_graph: Optional[Dict] = None,
                              goal_queue: Optional[List] = None,
                              mutation_diff: Optional[Dict] = None,
                              system_health: Optional[Dict] = None,
                              metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Record a complete failure context snapshot.
        
        Args:
            file_path: Path to the file being mutated
            original_ast: AST dump of original file
            mutated_ast: AST dump of mutated file
            traceback_info: Traceback information dictionary
            dependency_graph: Dependency graph state
            goal_queue: Goal queue state
            mutation_diff: Mutation diff details
            system_health: System health metrics
            metadata: Additional metadata
            
        Returns:
            Dictionary with complete failure context
        """
        context = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "file_path": str(file_path),
            "original_ast": original_ast,
            "mutated_ast": mutated_ast,
            "traceback": traceback_info,
            "dependency_graph": dependency_graph,
            "goal_queue": goal_queue,
            "mutation_diff": mutation_diff,
            "system_health": system_health,
            "metadata": metadata or {}
        }
        
        self.contexts.append(context)
        return context

    def save_context(self, context: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Save a failure context to a JSON file.
        
        Args:
            context: Failure context dictionary
            filename: Optional filename (default: timestamp-based)
            
        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"failure_context_{timestamp}.json"
        
        filepath = self.output_dir / filename
        with open(filepath, 'w') as f:
            json.dump(context, f, indent=2, default=str)
        
        return str(filepath)

    def save_all_contexts(self) -> List[str]:
        """
        Save all recorded failure contexts to JSON files.
        
        Returns:
            List of paths to saved files
        """
        saved_paths = []
        for i, context in enumerate(self.contexts):
            filename = f"failure_context_{i}_{context['timestamp'].replace(':', '-')}.json"
            saved_paths.append(self.save_context(context, filename))
        return saved_paths

    def load_context(self, filepath: str) -> Dict[str, Any]:
        """
        Load a failure context from a JSON file.
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            Failure context dictionary
        """
        with open(filepath, 'r') as f:
            return json.load(f)

    def clear_contexts(self) -> None:
        """Clear all recorded contexts from memory."""
        self.contexts.clear()

    def get_context_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a summary of a failure context.
        
        Args:
            context: Failure context dictionary
            
        Returns:
            Summary dictionary with key metrics
        """
        summary = {
            "timestamp": context.get("timestamp"),
            "file_path": context.get("file_path"),
            "has_original_ast": context.get("original_ast") is not None,
            "has_mutated_ast": context.get("mutated_ast") is not None,
            "has_traceback": context.get("traceback") is not None,
            "has_dependency_graph": context.get("dependency_graph") is not None,
            "has_goal_queue": context.get("goal_queue") is not None,
            "has_mutation_diff": context.get("mutation_diff") is not None,
            "has_system_health": context.get("system_health") is not None,
        }
        
        if context.get("traceback"):
            summary["traceback_exception"] = context["traceback"].get("exception_type")
        
        if context.get("system_health"):
            summary["avg_test_pass_rate"] = context["system_health"].get("average_test_pass_rate")
            summary["avg_dep_satisfaction"] = context["system_health"].get("average_dependency_satisfaction")
        
        return summary


# Convenience functions for quick use
def create_recorder(output_dir: str = "failure_context") -> FailureContextRecorder:
    """Create a new FailureContextRecorder instance."""
    return FailureContextRecorder(output_dir)

def record_and_save(file_path: str,
                   original_source: str,
                   mutated_source: str,
                   dependency_graph: Optional[Dict] = None,
                   goal_queue: Optional[List] = None,
                   module_test_pass_rates: Optional[Dict] = None,
                   dependency_satisfaction_levels: Optional[Dict] = None,
                   output_dir: str = "failure_context") -> str:
    """
    Convenience function to record a failure context and save it immediately.
    
    Args:
        file_path: Path to the file being mutated
        original_source: Original source code
        mutated_source: Mutated source code
        dependency_graph: Optional dependency graph state
        goal_queue: Optional goal queue state
        module_test_pass_rates: Optional module test pass rates
        dependency_satisfaction_levels: Optional dependency satisfaction levels
        output_dir: Output directory for saved contexts
        
    Returns:
        Path to saved file
    """
    recorder = create_recorder(output_dir)
    
    # Capture ASTs
    original_ast = recorder.capture_ast(file_path, "original")
    mutated_ast = recorder.capture_ast(file_path, "mutated")
    
    # Capture traceback if there's an active exception
    traceback_info = recorder.capture_traceback()
    
    # Capture mutation diff
    mutation_diff = recorder.store_mutation_diff(original_source, mutated_source)
    
    # Capture system health if metrics provided
    system_health = None
    if module_test_pass_rates and dependency_satisfaction_levels:
        system_health = recorder.record_system_health(
            module_test_pass_rates,
            dependency_satisfaction_levels
        )
    
    # Record the context
    context = recorder.record_failure_context(
        file_path=file_path,
        original_ast=original_ast,
        mutated_ast=mutated_ast,
        traceback_info=traceback_info,
        dependency_graph=dependency_graph,
        goal_queue=goal_queue,
        mutation_diff=mutation_diff,
        system_health=system_health
    )
    
    return recorder.save_context(context)