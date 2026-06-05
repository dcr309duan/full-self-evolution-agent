"""Module for analyzing test suite coverage gaps.

This module provides tools to analyze the current test suite and identify
coverage gaps including untested modules, unexercised code paths, and
missing edge cases. The analysis results feed into the benchmark generator
to ensure comprehensive environmental pressure testing.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict

try:
    import coverage
    COVERAGE_AVAILABLE = True
except ImportError:
    COVERAGE_AVAILABLE = False


@dataclass
class CoverageGap:
    """Represents a single coverage gap found in the test suite."""
    module: str
    gap_type: str  # 'untested_module', 'unexercised_path', 'missing_edge_case'
    description: str
    location: Optional[str] = None
    severity: str = 'medium'  # 'low', 'medium', 'high'


@dataclass
class CoverageAnalysis:
    """Complete analysis results for a test suite."""
    total_modules: int = 0
    tested_modules: int = 0
    untested_modules: List[str] = field(default_factory=list)
    gaps: List[CoverageGap] = field(default_factory=list)
    missing_edge_cases: List[str] = field(default_factory=list)
    unexercised_paths: List[str] = field(default_factory=list)
    coverage_percentage: float = 0.0


class CoverageAnalyzer:
    """Analyzes test suite coverage to identify gaps and missing tests."""

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.source_modules: Dict[str, str] = {}
        self.test_modules: Dict[str, str] = {}
        self._discover_modules()

    def _discover_modules(self) -> None:
        """Discover all Python modules in the project."""
        for path in self.project_root.rglob('*.py'):
            if path.name.startswith('__'):
                continue
            rel_path = path.relative_to(self.project_root)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
            
            if 'test' in path.name.lower() or 'test' in str(path.parent).lower():
                self.test_modules[module_name] = str(path)
            else:
                self.source_modules[module_name] = str(path)

    def analyze_module_coverage(self) -> CoverageAnalysis:
        """Analyze which modules have corresponding test files."""
        analysis = CoverageAnalysis()
        analysis.total_modules = len(self.source_modules)
        
        for module_name in self.source_modules:
            # Check for direct test file
            test_name = f"test_{module_name.split('.')[-1]}"
            test_path = module_name.rsplit('.', 1)[0] if '.' in module_name else ''
            test_full = f"{test_path}.{test_name}" if test_path else test_name
            
            if test_full not in self.test_modules:
                analysis.untested_modules.append(module_name)
                analysis.gaps.append(CoverageGap(
                    module=module_name,
                    gap_type='untested_module',
                    description=f"Module '{module_name}' has no corresponding test file",
                    location=self.source_modules[module_name],
                    severity='high'
                ))
            else:
                analysis.tested_modules += 1
        
        analysis.coverage_percentage = (
            (analysis.tested_modules / analysis.total_modules * 100)
            if analysis.total_modules > 0 else 0.0
        )
        
        return analysis

    def analyze_code_paths(self, module_name: str) -> List[CoverageGap]:
        """Analyze code paths in a specific module for potential gaps."""
        gaps = []
        if module_name not in self.source_modules:
            return gaps
        
        try:
            with open(self.source_modules[module_name], 'r') as f:
                tree = ast.parse(f.read())
        except SyntaxError:
            return gaps
        
        for node in ast.walk(tree):
            # Check for conditional branches
            if isinstance(node, ast.If):
                self._analyze_conditional(node, module_name, gaps)
            # Check for try-except blocks
            elif isinstance(node, ast.Try):
                self._analyze_try_block(node, module_name, gaps)
            # Check for loops
            elif isinstance(node, (ast.For, ast.While)):
                self._analyze_loop(node, module_name, gaps)
        
        return gaps

    def _analyze_conditional(self, node: ast.If, module: str, gaps: List[CoverageGap]) -> None:
        """Analyze if/elif/else branches for coverage gaps."""
        has_else = node.orelse and not any(
            isinstance(n, ast.If) for n in node.orelse
        )
        
        if not has_else:
            gaps.append(CoverageGap(
                module=module,
                gap_type='missing_edge_case',
                description=f"Missing else branch at line {node.lineno}",
                location=f"{self.source_modules[module]}:{node.lineno}",
                severity='medium'
            ))

    def _analyze_try_block(self, node: ast.Try, module: str, gaps: List[CoverageGap]) -> None:
        """Analyze try-except blocks for missing exception handlers."""
        handled_exceptions = set()
        for handler in node.handlers:
            if handler.type:
                handled_exceptions.add(
                    handler.type.id if isinstance(handler.type, ast.Name)
                    else handler.type.attr if isinstance(handler.type, ast.Attribute)
                    else str(handler.type)
                )
        
        # Check for bare except
        if any(handler.type is None for handler in node.handlers):
            gaps.append(CoverageGap(
                module=module,
                gap_type='unexercised_path',
                description=f"Bare except clause at line {node.lineno} - may hide unexpected exceptions",
                location=f"{self.source_modules[module]}:{node.lineno}",
                severity='high'
            ))

    def _analyze_loop(self, node: ast.AST, module: str, gaps: List[CoverageGap]) -> None:
        """Analyze loops for missing edge cases."""
        if isinstance(node, (ast.For, ast.While)):
            if not node.orelse:
                gaps.append(CoverageGap(
                    module=module,
                    gap_type='missing_edge_case',
                    description=f"Loop without else clause at line {node.lineno} - no-break case untested",
                    location=f"{self.source_modules[module]}:{node.lineno}",
                    severity='low'
                ))

    def analyze_edge_cases(self, module_name: str) -> List[CoverageGap]:
        """Identify potential missing edge cases in a module."""
        gaps = []
        if module_name not in self.source_modules:
            return gaps
        
        try:
            with open(self.source_modules[module_name], 'r') as f:
                tree = ast.parse(f.read())
        except SyntaxError:
            return gaps
        
        for node in ast.walk(tree):
            # Check for function definitions
            if isinstance(node, ast.FunctionDef):
                self._analyze_function_edge_cases(node, module_name, gaps)
            # Check for class definitions
            elif isinstance(node, ast.ClassDef):
                self._analyze_class_edge_cases(node, module_name, gaps)
        
        return gaps

    def _analyze_function_edge_cases(self, node: ast.FunctionDef, module: str, gaps: List[CoverageGap]) -> None:
        """Analyze function for missing edge cases."""
        # Check for missing type hints
        has_type_hints = any(
            arg.annotation for arg in node.args.args
        )
        if not has_type_hints and node.name != '__init__':
            gaps.append(CoverageGap(
                module=module,
                gap_type='missing_edge_case',
                description=f"Function '{node.name}' lacks type hints - edge cases with unexpected types untested",
                location=f"{self.source_modules[module]}:{node.lineno}",
                severity='low'
            ))
        
        # Check for missing default parameter edge cases
        defaults_count = len(node.args.defaults)
        if defaults_count > 0:
            gaps.append(CoverageGap(
                module=module,
                gap_type='missing_edge_case',
                description=f"Function '{node.name}' has {defaults_count} default parameter(s) - edge cases with custom defaults untested",
                location=f"{self.source_modules[module]}:{node.lineno}",
                severity='medium'
            ))

    def _analyze_class_edge_cases(self, node: ast.ClassDef, module: str, gaps: List[CoverageGap]) -> None:
        """Analyze class for missing edge cases."""
        # Check for inheritance edge cases
        bases = [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases]
        if bases:
            gaps.append(CoverageGap(
                module=module,
                gap_type='missing_edge_case',
                description=f"Class '{node.name}' inherits from {bases} - inheritance edge cases untested",
                location=f"{self.source_modules[module]}:{node.lineno}",
                severity='medium'
            ))

    def run_complete_analysis(self) -> CoverageAnalysis:
        """Run complete coverage analysis on the entire project."""
        analysis = self.analyze_module_coverage()
        
        # Analyze code paths and edge cases for all modules
        for module_name in self.source_modules:
            path_gaps = self.analyze_code_paths(module_name)
            edge_gaps = self.analyze_edge_cases(module_name)
            
            analysis.gaps.extend(path_gaps)
            analysis.gaps.extend(edge_gaps)
            
            for gap in path_gaps:
                if gap.gap_type == 'unexercised_path':
                    analysis.unexercised_paths.append(gap.description)
            
            for gap in edge_gaps:
                if gap.gap_type == 'missing_edge_case':
                    analysis.missing_edge_cases.append(gap.description)
        
        # Use coverage.py if available for more detailed analysis
        if COVERAGE_AVAILABLE:
            self._run_coverage_analysis(analysis)
        
        return analysis

    def _run_coverage_analysis(self, analysis: CoverageAnalysis) -> None:
        """Run coverage.py analysis for detailed line coverage."""
        try:
            cov = coverage.Coverage()
            cov.start()
            # Run tests
            import unittest
            loader = unittest.TestLoader()
            suite = loader.discover(str(self.project_root))
            runner = unittest.TextTestRunner(verbosity=0)
            runner.run(suite)
            cov.stop()
            cov.save()
            
            # Analyze coverage data
            data = cov.get_data()
            for module_name in self.source_modules:
                if data.has_line_data(module_name):
                    lines = data.lines(module_name)
                    if lines:
                        executed = len(lines)
                        total = max(lines) - min(lines) + 1
                        if executed / total < 0.8:  # Less than 80% coverage
                            analysis.gaps.append(CoverageGap(
                                module=module_name,
                                gap_type='unexercised_path',
                                description=f"Module '{module_name}' has low line coverage ({executed}/{total} lines)",
                                location=self.source_modules[module_name],
                                severity='high'
                            ))
        except Exception:
            pass  # coverage.py analysis is optional

    def generate_report(self, analysis: CoverageAnalysis) -> str:
        """Generate a human-readable coverage analysis report."""
        report_parts = []
        report_parts.append("=" * 60)
        report_parts.append("TEST SUITE COVERAGE ANALYSIS REPORT")
        report_parts.append("=" * 60)
        report_parts.append("")
        
        # Summary
        report_parts.append("SUMMARY")
        report_parts.append("-" * 40)
        report_parts.append(f"Total modules: {analysis.total_modules}")
        report_parts.append(f"Tested modules: {analysis.tested_modules}")
        report_parts.append(f"Coverage: {analysis.coverage_percentage:.1f}%")
        report_parts.append(f"Total gaps found: {len(analysis.gaps)}")
        report_parts.append("")
        
        # Untested modules
        if analysis.untested_modules:
            report_parts.append("UNTESTED MODULES")
            report_parts.append("-" * 40)
            for module in analysis.untested_modules:
                report_parts.append(f"  - {module}")
            report_parts.append("")
        
        # Coverage gaps by severity
        for severity in ['high', 'medium', 'low']:
            severity_gaps = [g for g in analysis.gaps if g.severity == severity]
            if severity_gaps:
                report_parts.append(f"{severity.upper()} SEVERITY GAPS")
                report_parts.append("-" * 40)
                for gap in severity_gaps:
                    report_parts.append(f"  [{gap.gap_type}] {gap.description}")
                    if gap.location:
                        report_parts.append(f"    Location: {gap.location}")
                report_parts.append("")
        
        # Missing edge cases
        if analysis.missing_edge_cases:
            report_parts.append("MISSING EDGE CASES")
            report_parts.append("-" * 40)
            for case in analysis.missing_edge_cases[:10]:  # Show top 10
                report_parts.append(f"  - {case}")
            if len(analysis.missing_edge_cases) > 10:
                report_parts.append(f"  ... and {len(analysis.missing_edge_cases) - 10} more")
            report_parts.append("")
        
        # Recommendations
        report_parts.append("RECOMMENDATIONS")
        report_parts.append("-" * 40)
        if analysis.untested_modules:
            report_parts.append("1. Add test files for untested modules")
        if analysis.gaps:
            report_parts.append("2. Address high-severity gaps first")
        if analysis.missing_edge_cases:
            report_parts.append("3. Add edge case tests for functions with defaults")
        report_parts.append("4. Consider adding property-based testing for complex logic")
        report_parts.append("")
        
        return "\n".join(report_parts)


def analyze_project(project_root: Optional[str] = None) -> CoverageAnalysis:
    """Convenience function to analyze a project's test coverage."""
    analyzer = CoverageAnalyzer(project_root)
    return analyzer.run_complete_analysis()


def main():
    """Main entry point for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze test suite coverage gaps"
    )
    parser.add_argument(
        'project_root',
        nargs='?',
        default='.',
        help="Root directory of the project to analyze"
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help="Generate a detailed coverage report"
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help="Output results in JSON format"
    )
    
    args = parser.parse_args()
    
    analysis = analyze_project(args.project_root)
    
    if args.json:
        import json
        output = {
            'total_modules': analysis.total_modules,
            'tested_modules': analysis.tested_modules,
            'untested_modules': analysis.untested_modules,
            'coverage_percentage': analysis.coverage_percentage,
            'gaps': [
                {
                    'module': g.module,
                    'type': g.gap_type,
                    'description': g.description,
                    'location': g.location,
                    'severity': g.severity
                }
                for g in analysis.gaps
            ],
            'missing_edge_cases': analysis.missing_edge_cases,
            'unexercised_paths': analysis.unexercised_paths
        }
        print(json.dumps(output, indent=2))
    elif args.report:
        analyzer = CoverageAnalyzer(args.project_root)
        print(analyzer.generate_report(analysis))
    else:
        print(f"Coverage Analysis Results:")
        print(f"  Total modules: {analysis.total_modules}")
        print(f"  Tested modules: {analysis.tested_modules}")
        print(f"  Coverage: {analysis.coverage_percentage:.1f}%")
        print(f"  Untested modules: {len(analysis.untested_modules)}")
        print(f"  Total gaps: {len(analysis.gaps)}")
        print(f"  Missing edge cases: {len(analysis.missing_edge_cases)}")
        print(f"  Unexercised paths: {len(analysis.unexercised_paths)}")


if __name__ == '__main__':
    main()