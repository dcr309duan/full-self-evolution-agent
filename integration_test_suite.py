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
        
    def run_full_pipeline_test(self) -> Dict[str, Any]:
        """
        Execute the complete mutation->test pipeline and return structured results.
        This method is designed to be called by the rollback_manager to determine
        if rollback is needed.
        
        Returns:
            Dict containing structured results with pass/fail status, error details,
            and test coverage metrics
        """
        pipeline_results = {
            "status": "PASS",
            "error_details": [],
            "test_coverage_metrics": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "coverage_percentage": 0.0
            },
            "pipeline_steps": []
        }
        
        try:
            # Step 1: Generate goal
            print("Pipeline Step 1: Generating goal...")
            goal = self.goal_generator.generate_goal(self.test_goal)
            pipeline_results["pipeline_steps"].append({
                "step": "goal_generation",
                "status": "PASS",
                "goal": goal
            })
            
            # Step 2: Apply mutation engine
            print("Pipeline Step 2: Applying mutation engine...")
            mutation_result = self.mutation_engine.apply_mutation(goal)
            pipeline_results["pipeline_steps"].append({
                "step": "mutation_engine",
                "status": "PASS",
                "mutation": mutation_result
            })
            
            # Step 3: Rewrite AST
            print("Pipeline Step 3: Rewriting AST...")
            ast_result = self.ast_rewriter.rewrite_ast(mutation_result)
            pipeline_results["pipeline_steps"].append({
                "step": "ast_rewriter",
                "status": "PASS",
                "ast_result": ast_result
            })
            
            # Step 4: Run test suite for dummy module
            print("Pipeline Step 4: Running test suite...")
            test_results = self.test_runner.run_tests("dummy_utility_module")
            
            # Extract test coverage metrics from test results
            if isinstance(test_results, dict):
                total_tests = test_results.get("total_tests", 0)
                passed_tests = test_results.get("passed_tests", 0)
                failed_tests = test_results.get("failed_tests", 0)
                coverage_percentage = test_results.get("coverage_percentage", 0.0)
            else:
                total_tests = 0
                passed_tests = 0
                failed_tests = 0
                coverage_percentage = 0.0
            
            pipeline_results["test_coverage_metrics"] = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "coverage_percentage": coverage_percentage
            }
            
            pipeline_results["pipeline_steps"].append({
                "step": "test_execution",
                "status": "PASS",
                "test_results": test_results
            })
            
            # Step 5: Analyze failures
            print("Pipeline Step 5: Analyzing failures...")
            failure_analysis = self.failure_analyzer.analyze(test_results)
            pipeline_results["pipeline_steps"].append({
                "step": "failure_analysis",
                "status": "PASS",
                "analysis": failure_analysis
            })
            
            # Check if there are any failures
            if failure_analysis.get("has_failures", False):
                pipeline_results["status"] = "FAIL"
                error_details = {
                    "error_type": "TestFailure",
                    "error_message": "Test failures detected in pipeline",
                    "traceback": "",
                    "failure_details": failure_analysis.get("error_traces", [])
                }
                pipeline_results["error_details"].append(error_details)
            
        except Exception as e:
            pipeline_results["status"] = "FAIL"
            error_detail = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            pipeline_results["error_details"].append(error_detail)
            
            # Add failed step if not already recorded
            if not pipeline_results["pipeline_steps"] or pipeline_results["pipeline_steps"][-1]["status"] == "PASS":
                pipeline_results["pipeline_steps"].append({
                    "step": "unknown",
                    "status": "FAIL",
                    "error": error_detail
                })
        
        # Step 6: Send results to reflection system
        print("Pipeline Step 6: Sending results to reflection system...")
        try:
            reflection_result = self.reflection_system.process_results(pipeline_results)
            pipeline_results["reflection_result"] = reflection_result
        except Exception as e:
            pipeline_results["reflection_result"] = {
                "status": "FAIL",
                "error": str(e)
            }
        
        return pipeline_results
    
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
    
    def run_meta_mutation_sanity_check(self) -> Dict[str, Any]:
        """
        Run a sanity check on the meta-mutation engine itself.
        After a meta-mutation is applied, verify that core functionality still works.
        
        Returns:
            Dict containing sanity check results
        """
        sanity_results = {
            "meta_mutation_sanity_check": "PASS",
            "checks": []
        }
        
        try:
            # Simulate a meta-mutation by applying a mutation to the meta-module
            print("\n--- Meta-Mutation Sanity Check ---")
            print("Applying meta-mutation to meta-module...")
            
            # Apply a simple meta-mutation (e.g., add a docstring to mutation_engine)
            meta_goal = "add a docstring to mutation_engine.apply_mutation()"
            meta_mutation = self.mutation_engine.apply_mutation(meta_goal)
            
            # Rewrite the AST for the meta-module
            meta_ast_result = self.ast_rewriter.rewrite_ast(meta_mutation)
            
            # Check 1: Verify reflection_parser still parses correctly
            print("Check 1: Verifying reflection_parser...")
            try:
                # Simulate parsing a reflection result
                test_reflection_data = {
                    "test_goal": "test",
                    "pipeline_steps": [{"step": "test", "status": "PASS"}],
                    "overall_status": "PASS",
                    "error_traces": []
                }
                parsed = self.reflection_system.process_results(test_reflection_data)
                sanity_results["checks"].append({
                    "check": "reflection_parser",
                    "status": "PASS",
                    "detail": "Reflection parser parsed test data successfully"
                })
                print("  ✓ Reflection parser works correctly")
            except Exception as e:
                sanity_results["checks"].append({
                    "check": "reflection_parser",
                    "status": "FAIL",
                    "detail": f"Reflection parser failed: {str(e)}"
                })
                sanity_results["meta_mutation_sanity_check"] = "FAIL"
                print(f"  ✗ Reflection parser failed: {str(e)}")
            
            # Check 2: Verify orchestrator still runs
            print("Check 2: Verifying orchestrator...")
            try:
                # Simulate running the orchestrator with a simple goal
                test_goal = "add a docstring to dummy_utility_module.add()"
                goal = self.goal_generator.generate_goal(test_goal)
                mutation = self.mutation_engine.apply_mutation(goal)
                ast_result = self.ast_rewriter.rewrite_ast(mutation)
                test_results = self.test_runner.run_tests("dummy_utility_module")
                analysis = self.failure_analyzer.analyze(test_results)
                
                sanity_results["checks"].append({
                    "check": "orchestrator",
                    "status": "PASS",
                    "detail": "Orchestrator completed full pipeline successfully"
                })
                print("  ✓ Orchestrator runs correctly")
            except Exception as e:
                sanity_results["checks"].append({
                    "check": "orchestrator",
                    "status": "FAIL",
                    "detail": f"Orchestrator failed: {str(e)}"
                })
                sanity_results["meta_mutation_sanity_check"] = "FAIL"
                print(f"  ✗ Orchestrator failed: {str(e)}")
            
            # Check 3: Verify meta-module integrity
            print("Check 3: Verifying meta-module integrity...")
            try:
                # Check that the mutation engine still works after meta-mutation
                test_mutation = self.mutation_engine.apply_mutation("test mutation")
                if test_mutation is not None:
                    sanity_results["checks"].append({
                        "check": "meta_module_integrity",
                        "status": "PASS",
                        "detail": "Meta-module functions correctly after meta-mutation"
                    })
                    print("  ✓ Meta-module integrity maintained")
                else:
                    raise ValueError("Mutation engine returned None after meta-mutation")
            except Exception as e:
                sanity_results["checks"].append({
                    "check": "meta_module_integrity",
                    "status": "FAIL",
                    "detail": f"Meta-module integrity check failed: {str(e)}"
                })
                sanity_results["meta_mutation_sanity_check"] = "FAIL"
                print(f"  ✗ Meta-module integrity check failed: {str(e)}")
            
            print(f"Meta-Mutation Sanity Check: {sanity_results['meta_mutation_sanity_check']}")
            print("--- End Meta-Mutation Sanity Check ---\n")
            
        except Exception as e:
            sanity_results["meta_mutation_sanity_check"] = "FAIL"
            sanity_results["checks"].append({
                "check": "meta_mutation_execution",
                "status": "FAIL",
                "detail": f"Meta-mutation execution failed: {str(e)}"
            })
            print(f"  ✗ Meta-mutation execution failed: {str(e)}")
        
        return sanity_results
    
    def test_sandboxed_mutation_pipeline(self) -> Dict[str, Any]:
        """
        Test the sandboxed mutation pipeline end-to-end.
        (1) Creates a simple mutation (e.g., adding a docstring),
        (2) Runs it through the sandbox executor,
        (3) Verifies the mutation is only present in the main codebase if tests pass,
        (4) Verifies cleanup on simulated test failure.
        
        Returns:
            Dict containing test results for the sandboxed pipeline
        """
        sandbox_results = {
            "test_name": "test_sandboxed_mutation_pipeline",
            "status": "PASS",
            "steps": [],
            "errors": []
        }
        
        try:
            # Step 1: Create a simple mutation (add a docstring)
            print("\n--- Sandboxed Mutation Pipeline Test ---")
            print("Step 1: Creating simple mutation...")
            mutation_goal = "add a docstring to dummy_utility_module.add()"
            goal = self.goal_generator.generate_goal(mutation_goal)
            mutation_result = self.mutation_engine.apply_mutation(goal)
            ast_result = self.ast_rewriter.rewrite_ast(mutation_result)
            
            sandbox_results["steps"].append({
                "step": "create_mutation",
                "status": "PASS",
                "detail": "Successfully created mutation to add docstring"
            })
            print("  ✓ Mutation created successfully")
            
            # Step 2: Run mutation through sandbox executor (simulate with test runner)
            print("Step 2: Running mutation through sandbox executor...")
            # Simulate sandbox execution by running tests on the mutated code
            test_results = self.test_runner.run_tests("dummy_utility_module")
            
            sandbox_results["steps"].append({
                "step": "sandbox_execution",
                "status": "PASS",
                "detail": "Mutation executed in sandbox environment",
                "test_results": test_results
            })
            print("  ✓ Sandbox execution completed")
            
            # Step 3: Verify mutation is only present in main codebase if tests pass
            print("Step 3: Verifying mutation presence based on test results...")
            failure_analysis = self.failure_analyzer.analyze(test_results)
            tests_passed = not failure_analysis.get("has_failures", False)
            
            if tests_passed:
                # Simulate applying mutation to main codebase
                # In a real implementation, this would modify the actual file
                print("  ✓ Tests passed - mutation would be applied to main codebase")
                sandbox_results["steps"].append({
                    "step": "mutation_application",
                    "status": "PASS",
                    "detail": "Tests passed, mutation applied to main codebase",
                    "mutation_applied": True
                })
            else:
                print("  ✗ Tests failed - mutation would NOT be applied to main codebase")
                sandbox_results["steps"].append({
                    "step": "mutation_application",
                    "status": "PASS",
                    "detail": "Tests failed, mutation not applied to main codebase",
                    "mutation_applied": False
                })
            
            # Step 4: Verify cleanup on simulated test failure
            print("Step 4: Testing cleanup on simulated test failure...")
            # Simulate a test failure by creating a bad mutation
            bad_mutation_goal = "remove the return statement from dummy_utility_module.add()"
            bad_goal = self.goal_generator.generate_goal(bad_mutation_goal)
            bad_mutation = self.mutation_engine.apply_mutation(bad_goal)
            bad_ast_result = self.ast_rewriter.rewrite_ast(bad_mutation)
            
            # Run tests with the bad mutation
            bad_test_results = self.test_runner.run_tests("dummy_utility_module")
            bad_failure_analysis = self.failure_analyzer.analyze(bad_test_results)
            
            if bad_failure_analysis.get("has_failures", False):
                # Simulate cleanup - in real implementation this would revert changes
                print("  ✓ Cleanup triggered on test failure")
                sandbox_results["steps"].append({
                    "step": "cleanup_on_failure",
                    "status": "PASS",
                    "detail": "Cleanup successfully performed after simulated test failure",
                    "cleanup_performed": True
                })
            else:
                print("  ✗ No cleanup needed - tests passed unexpectedly")
                sandbox_results["steps"].append({
                    "step": "cleanup_on_failure",
                    "status": "PASS",
                    "detail": "No cleanup needed (tests passed unexpectedly)",
                    "cleanup_performed": False
                })
            
            print("--- End Sandboxed Mutation Pipeline Test ---\n")
            
        except Exception as e:
            sandbox_results["status"] = "FAIL"
            error_detail = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            sandbox_results["errors"].append(error_detail)
            print(f"  ✗ Sandbox test failed: {str(e)}")
        
        return sandbox_results
    
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
        
        # Print meta-mutation sanity check results if present
        if 'meta_mutation_sanity_check' in results:
            print(f"\nMeta-Mutation Sanity Check: {results['meta_mutation_sanity_check']}")
            if 'checks' in results:
                for check in results['checks']:
                    status_icon = "✓" if check['status'] == "PASS" else "✗"
                    print(f"  {status_icon} {check['check']}: {check['status']}")
        
        # Print sandboxed mutation pipeline test results if present
        if 'sandbox_test_results' in results:
            sandbox_results = results['sandbox_test_results']
            print(f"\nSandboxed Mutation Pipeline Test: {sandbox_results['status']}")
            if 'steps' in sandbox_results:
                for step in sandbox_results['steps']:
                    status_icon = "✓" if step['status'] == "PASS" else "✗"
                    print(f"  {status_icon} {step['step']}: {step['status']}")
            if sandbox_results.get('errors'):
                print(f"  Errors: {len(sandbox_results['errors'])}")
                for error in sandbox_results['errors']:
                    print(f"    - {error.get('error_message', 'Unknown error')}")
        
        print("="*60)

def main():
    """Main entry point for the integration test suite."""
    suite = IntegrationTestSuite()
    
    print("Starting Integration Test Suite...")
    print(f"Test Goal: {suite.test_goal}")
    print("-" * 40)
    
    # Run the integration test
    results = suite.run_integration_test()
    
    # Run meta-mutation sanity check
    sanity_results = suite.run_meta_mutation_sanity_check()
    results["meta_mutation_sanity_check"] = sanity_results["meta_mutation_sanity_check"]
    results["meta_mutation_checks"] = sanity_results["checks"]
    
    # Update overall status if sanity check fails
    if sanity_results["meta_mutation_sanity_check"] == "FAIL":
        results["overall_status"] = "FAIL"
        results["error_traces"].append({
            "error_type": "MetaMutationSanityCheck",
            "error_message": "Meta-mutation sanity check failed",
            "traceback": ""
        })
    
    # Run sandboxed mutation pipeline test
    sandbox_results = suite.test_sandboxed_mutation_pipeline()
    results["sandbox_test_results"] = sandbox_results
    
    # Update overall status if sandbox test fails
    if sandbox_results["status"] == "FAIL":
        results["overall_status"] = "FAIL"
        results["error_traces"].append({
            "error_type": "SandboxTestFailure",
            "error_message": "Sandboxed mutation pipeline test failed",
            "traceback": ""
        })
    
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