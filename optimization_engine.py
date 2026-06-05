from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import heapq
from performance_monitor import PerformanceMonitor, PerformanceData

class OptimizationPriority(Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3

@dataclass
class OptimizationGoal:
    module_name: str
    description: str
    target_metric: str
    current_value: float
    target_value: float
    potential_gain: float  # Expected performance improvement (0-1 scale)
    implementation_cost: float  # Estimated effort/cost (0-1 scale)
    priority: OptimizationPriority = OptimizationPriority.MEDIUM

    def score(self) -> float:
        """Calculate priority score based on gain/cost ratio."""
        if self.implementation_cost == 0:
            return float('inf')
        return self.potential_gain / self.implementation_cost

class OptimizationEngine:
    """Engine that analyzes performance data and generates prioritized optimization goals."""

    def __init__(self, performance_monitor: PerformanceMonitor):
        self.monitor = performance_monitor
        self.goals: List[OptimizationGoal] = []
        self.thresholds = {
            'mutation_failure_rate': 0.15,  # 15% failure rate threshold
            'execution_time': 2.0,  # seconds
            'memory_usage': 500,  # MB
            'cpu_usage': 0.8,  # 80% CPU usage
        }

    def analyze_performance(self) -> List[OptimizationGoal]:
        """Main analysis method that processes performance data and generates goals."""
        performance_data = self.monitor.get_all_performance_data()
        
        # Clear previous goals
        self.goals.clear()
        
        # Analyze each module
        for module_name, data in performance_data.items():
            self._analyze_module(module_name, data)
        
        # Prioritize goals
        self._prioritize_goals()
        
        return self.goals

    def _analyze_module(self, module_name: str, data: PerformanceData) -> None:
        """Analyze a single module's performance data."""
        # Check mutation failure rate
        if hasattr(data, 'mutation_failure_rate') and data.mutation_failure_rate > self.thresholds['mutation_failure_rate']:
            target = data.mutation_failure_rate * 0.8  # 20% reduction
            goal = OptimizationGoal(
                module_name=module_name,
                description=f"Reduce mutation failure rate in {module_name} by 20%",
                target_metric='mutation_failure_rate',
                current_value=data.mutation_failure_rate,
                target_value=target,
                potential_gain=self._calculate_gain(data.mutation_failure_rate, 'mutation_failure_rate'),
                implementation_cost=self._estimate_cost(module_name, 'mutation_failure_rate')
            )
            self.goals.append(goal)

        # Check execution time
        if hasattr(data, 'execution_time') and data.execution_time > self.thresholds['execution_time']:
            target = data.execution_time * 0.75  # 25% reduction
            goal = OptimizationGoal(
                module_name=module_name,
                description=f"Reduce execution time in {module_name} by 25%",
                target_metric='execution_time',
                current_value=data.execution_time,
                target_value=target,
                potential_gain=self._calculate_gain(data.execution_time, 'execution_time'),
                implementation_cost=self._estimate_cost(module_name, 'execution_time')
            )
            self.goals.append(goal)

        # Check memory usage
        if hasattr(data, 'memory_usage') and data.memory_usage > self.thresholds['memory_usage']:
            target = data.memory_usage * 0.8  # 20% reduction
            goal = OptimizationGoal(
                module_name=module_name,
                description=f"Reduce memory usage in {module_name} by 20%",
                target_metric='memory_usage',
                current_value=data.memory_usage,
                target_value=target,
                potential_gain=self._calculate_gain(data.memory_usage, 'memory_usage'),
                implementation_cost=self._estimate_cost(module_name, 'memory_usage')
            )
            self.goals.append(goal)

        # Check CPU usage
        if hasattr(data, 'cpu_usage') and data.cpu_usage > self.thresholds['cpu_usage']:
            target = self.thresholds['cpu_usage'] * 0.9  # Reduce to 90% of threshold
            goal = OptimizationGoal(
                module_name=module_name,
                description=f"Reduce CPU usage in {module_name} to {target:.0%}",
                target_metric='cpu_usage',
                current_value=data.cpu_usage,
                target_value=target,
                potential_gain=self._calculate_gain(data.cpu_usage, 'cpu_usage'),
                implementation_cost=self._estimate_cost(module_name, 'cpu_usage')
            )
            self.goals.append(goal)

    def _calculate_gain(self, current_value: float, metric_type: str) -> float:
        """Calculate potential performance gain based on how far from threshold."""
        threshold = self.thresholds.get(metric_type, 1.0)
        if threshold == 0:
            return 0.0
        deviation = (current_value - threshold) / threshold
        # Normalize gain to 0-1 scale, with diminishing returns for large deviations
        return min(1.0, deviation / 2.0)

    def _estimate_cost(self, module_name: str, metric_type: str) -> float:
        """Estimate implementation cost based on module complexity and metric type."""
        # In a real system, this would use historical data or complexity analysis
        # For now, use a heuristic based on module name and metric type
        base_cost = 0.3  # Base cost for any optimization
        
        # Add complexity based on metric type
        metric_costs = {
            'mutation_failure_rate': 0.4,  # Complex - requires test analysis
            'execution_time': 0.3,  # Moderate - algorithm optimization
            'memory_usage': 0.2,  # Simpler - memory management
            'cpu_usage': 0.25,  # Moderate - resource optimization
        }
        
        # Add module-specific complexity (simulated)
        module_complexity = hash(module_name) % 100 / 100.0 * 0.2
        
        total_cost = base_cost + metric_costs.get(metric_type, 0.3) + module_complexity
        return min(1.0, total_cost)

    def _prioritize_goals(self) -> None:
        """Prioritize goals based on gain/cost ratio using a max-heap."""
        # Create a max-heap based on negative score (since heapq is min-heap)
        heap = []
        for goal in self.goals:
            score = goal.score()
            heapq.heappush(heap, (-score, goal))
        
        # Rebuild goals list in priority order
        self.goals.clear()
        while heap:
            _, goal = heapq.heappop(heap)
            # Assign priority based on position
            if len(self.goals) < len(heap) * 0.2:  # Top 20%
                goal.priority = OptimizationPriority.HIGH
            elif len(self.goals) < len(heap) * 0.5:  # Next 30%
                goal.priority = OptimizationPriority.MEDIUM
            else:
                goal.priority = OptimizationPriority.LOW
            self.goals.append(goal)

    def get_high_priority_goals(self) -> List[OptimizationGoal]:
        """Return only high-priority optimization goals."""
        return [g for g in self.goals if g.priority == OptimizationPriority.HIGH]

    def get_goals_by_module(self, module_name: str) -> List[OptimizationGoal]:
        """Get all optimization goals for a specific module."""
        return [g for g in self.goals if g.module_name == module_name]

    def generate_report(self) -> str:
        """Generate a human-readable report of optimization goals."""
        if not self.goals:
            return "No optimization goals identified."
        
        report_lines = ["=== Optimization Engine Report ==="]
        report_lines.append(f"Total goals identified: {len(self.goals)}")
        report_lines.append("")
        
        for i, goal in enumerate(self.goals, 1):
            report_lines.append(f"Goal #{i} [{goal.priority.name} PRIORITY]")
            report_lines.append(f"  Module: {goal.module_name}")
            report_lines.append(f"  Description: {goal.description}")
            report_lines.append(f"  Metric: {goal.target_metric}")
            report_lines.append(f"  Current: {goal.current_value:.2f} -> Target: {goal.target_value:.2f}")
            report_lines.append(f"  Potential Gain: {goal.potential_gain:.1%}")
            report_lines.append(f"  Implementation Cost: {goal.implementation_cost:.1%}")
            report_lines.append(f"  Score (Gain/Cost): {goal.score():.2f}")
            report_lines.append("")
        
        return "\n".join(report_lines)

    def update_thresholds(self, new_thresholds: Dict[str, float]) -> None:
        """Update performance thresholds for analysis."""
        self.thresholds.update(new_thresholds)