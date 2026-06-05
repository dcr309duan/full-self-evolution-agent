import json
import sys
import os
import traceback
from typing import Dict, Any, Optional

# Import project modules
from goal_generator import GoalGenerator
from mutation_engine import MutationEngine
from ast_rewriter import ASTRewriter
from test_runner import TestRunner
from failure_analyzer import FailureAnalyzer
from reflection_system import ReflectionSystem

# Import dummy module for testing
from dummy_utility_module import add

class IntegrationTestSuite:
    """
    Main integration test suite that orchestrates the full pipeline:
    goal generation -> mutation engine -> AST rewriter -> test execution -> failure analysis -> reflection
    """
    
    def __init__(self):
        self.goal_generator = GoalGenerator()
        self.mutation_engine = MutationEngine()
        self.ast_rewriter = ASTRewriter()
        self.test_runner = TestRunner()
        self.failure_analyzer = FailureAnalyzer()
        self.reflection_system = ReflectionSystem()
        
        # Define the controlled test goal
        self.test_goal = "add a docstring to dummy_utility_module.add()"
        
    def run_integration_test(self) -> Dict[str, Any]:
        """
        Execute the full integration test pipeline.
        
        Returns:
            Dict containing structured JSON results for the reflection system
        """
        results = {
            "test_goal": self.test_goal,
            "pipeline_steps": [],
            "overall_status": "PASS",
            "error_traces": []
        }
        
        try:
            # Step 1: Generate goal
            print("Step 1: Generating goal...")
            goal = self.goal_generator.generate_goal(self.test_goal)
            results["pipeline_steps"].append({
                "step": "goal_generation",
                "status": "PASS",
                "goal": goal
            })
            
            # Step 2: Apply mutation engine
            print("Step 2: Applying mutation engine...")
            mutation_result = self.mutation_engine.apply_mutation(goal)
            results["pipeline_steps"].append({
                "step": "mutation_engine",
                "status": "PASS",
                "mutation": mutation_result
            })
            
            # Step 3: Rewrite AST
            print("Step 3: Rewriting AST...")
            ast_result = self.ast_rewriter.rewrite_ast(mutation_result)
            results["pipeline_steps"].append({
                "step": "ast_rewriter",
                "status": "PASS",
                "ast_result": ast_result
            })
            
            # Step 4: Run test suite for dummy module
            print("Step 4: Running test suite...")
            test_results = self.test_runner.run_tests("dummy_utility_module")
            results["pipeline_steps"].append({
                "step": "test_execution",
                "status": "PASS",
                "test_results": test_results
            })
            
            # Step 5: Analyze failures
            print("Step 5: Analyzing failures...")
            failure_analysis = self.failure_analyzer.analyze(test_results)
            results["pipeline_steps"].append({
                "step": "failure_analysis",
                "status": "PASS",
                "analysis": failure_analysis
            })
            
            # Check if there are any failures
            if failure_analysis.get("has_failures", False):
                results["overall_status"] = "FAIL"
                results["error_traces"].extend(failure_analysis.get("error_traces", []))
            
        except Exception as e:
            results["overall_status"] = "FAIL"
            error_trace = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            results["error_traces"].append(error_trace)
            
            # Add failed step if not already recorded
            if not results["pipeline_steps"] or results["pipeline_steps"][-1]["status"] == "PASS":
                results["pipeline_steps"].append({
                    "step": "unknown",
                    "status": "FAIL",
                    "error": error_trace
                })
        
        # Step 6: Send results to reflection system
        print("Step 6: Sending results to reflection system...")
        try:
            reflection_result = self.reflection_system.process_results(results)
            results["reflection_result"] = reflection_result
        except Exception as e:
            results["reflection_result"] = {
                "status": "FAIL",
                "error": str(e)
            }
        
        return results
    
    def format_results_as_json(self, results: Dict[str, Any]) -> str:
        """
        Format the results as structured JSON for the reflection system.
        
        Args:
            results: Dictionary containing test results
            
        Returns:
            JSON string formatted for reflection system
        """
        return json.dumps(results, indent=2, default=str)
    
    def print_summary(self, results: Dict[str, Any]) -> None:
        """
        Print a human-readable summary of the test results.
        
        Args:
            results: Dictionary containing test results
        """
        print("\n" + "="*60)
        print("INTEGRATION TEST SUMMARY")
        print("="*60)
        print(f"Test Goal: {results['test_goal']}")
        print(f"Overall Status: {results['overall_status']}")
        print(f"Pipeline Steps: {len(results['pipeline_steps'])}")
        
        for step in results['pipeline_steps']:
            status_icon = "✓" if step['status'] == "PASS" else "✗"
            print(f"  {status_icon} {step['step']}: {step['status']}")
        
        if results['error_traces']:
            print(f"\nErrors ({len(results['error_traces'])}):")
            for i, error in enumerate(results['error_traces'], 1):
                print(f"  {i}. {error.get('error_type', 'Unknown')}: {error.get('error_message', 'No message')}")
        
        print("="*60)

def main():
    """Main entry point for the integration test suite."""
    suite = IntegrationTestSuite()
    
    print("Starting Integration Test Suite...")
    print(f"Test Goal: {suite.test_goal}")
    print("-" * 40)
    
    # Run the integration test
    results = suite.run_integration_test()
    
    # Print summary
    suite.print_summary(results)
    
    # Format and output JSON for reflection system
    json_output = suite.format_results_as_json(results)
    print("\nStructured JSON Output for Reflection System:")
    print(json_output)
    
    # Return appropriate exit code
    return 0 if results["overall_status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())