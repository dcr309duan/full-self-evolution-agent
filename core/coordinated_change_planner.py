from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import networkx as nx
from collections import defaultdict

@dataclass
class CoordinatedMutation:
    """Represents a coordinated mutation across multiple modules."""
    module_ids: List[str]
    mutation_types: List[str]
    description: str
    expected_fitness_improvement: float
    dependency_impact: Dict[str, float]
    risk_score: float

@dataclass
class ModuleState:
    """Represents the current state of a module at Nash equilibrium."""
    module_id: str
    current_fitness: float
    current_strategy: Dict[str, Any]
    dependencies: List[str]
    dependents: List[str]
    mutation_options: List[Dict[str, Any]]

class CoordinatedChangePlanner:
    """
    Generates multi-module mutation plans for modules at Nash equilibrium.
    Analyzes dependency graphs to find mutually reinforcing changes.
    """
    
    def __init__(self, dependency_graph: nx.DiGraph, global_fitness_function: callable):
        """
        Initialize the planner with a dependency graph and global fitness function.
        
        Args:
            dependency_graph: NetworkX directed graph representing module dependencies
            global_fitness_function: Function that evaluates overall system fitness
        """
        self.dependency_graph = dependency_graph
        self.global_fitness_function = global_fitness_function
        self._module_states: Dict[str, ModuleState] = {}
        
    def register_module_state(self, module_id: str, state: ModuleState) -> None:
        """Register the current state of a module."""
        self._module_states[module_id] = state
        
    def analyze_dependency_graph(self, module_ids: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Analyze dependency graph to find mutually reinforcing relationships.
        
        Returns:
            Dictionary mapping module pairs to their reinforcement scores
        """
        reinforcement_scores = defaultdict(dict)
        
        for i, mod_a in enumerate(module_ids):
            for mod_b in module_ids[i+1:]:
                score = self._calculate_reinforcement_score(mod_a, mod_b)
                reinforcement_scores[mod_a][mod_b] = score
                reinforcement_scores[mod_b][mod_a] = score
                
        return dict(reinforcement_scores)
    
    def _calculate_reinforcement_score(self, mod_a: str, mod_b: str) -> float:
        """
        Calculate how much changes in mod_a reinforce changes in mod_b.
        Uses dependency graph structure and current module states.
        """
        score = 0.0
        
        # Check direct dependencies
        if self.dependency_graph.has_edge(mod_a, mod_b):
            score += 0.3
        if self.dependency_graph.has_edge(mod_b, mod_a):
            score += 0.3
            
        # Check shared dependencies
        shared_deps = set(self.dependency_graph.successors(mod_a)) & set(self.dependency_graph.successors(mod_b))
        score += len(shared_deps) * 0.1
        
        # Check shared dependents
        shared_dependents = set(self.dependency_graph.predecessors(mod_a)) & set(self.dependency_graph.predecessors(mod_b))
        score += len(shared_dependents) * 0.1
        
        # Consider current fitness levels
        if mod_a in self._module_states and mod_b in self._module_states:
            fitness_diff = abs(self._module_states[mod_a].current_fitness - self._module_states[mod_b].current_fitness)
            score += max(0, 0.2 - fitness_diff * 0.1)
            
        return min(1.0, score)
    
    def generate_coordinated_mutations(self, module_ids: List[str], max_plans: int = 5) -> List[CoordinatedMutation]:
        """
        Generate coordinated mutation plans for the given modules.
        
        Args:
            module_ids: List of module IDs to consider for coordinated changes
            max_plans: Maximum number of plans to generate
            
        Returns:
            List of CoordinatedMutation plans sorted by expected fitness improvement
        """
        if len(module_ids) < 2:
            return []
            
        # Analyze reinforcement patterns
        reinforcement_scores = self.analyze_dependency_graph(module_ids)
        
        # Find high-reinforcement module pairs and triples
        candidate_groups = self._find_candidate_groups(module_ids, reinforcement_scores)
        
        plans = []
        for group in candidate_groups[:max_plans]:
            plan = self._create_coordinated_plan(group, module_ids)
            if plan:
                plans.append(plan)
                
        # Sort by expected fitness improvement
        plans.sort(key=lambda p: p.expected_fitness_improvement, reverse=True)
        return plans[:max_plans]
    
    def _find_candidate_groups(self, module_ids: List[str], 
                              reinforcement_scores: Dict[str, Dict[str, float]]) -> List[List[str]]:
        """
        Find groups of 2-3 modules with high reinforcement scores.
        """
        candidates = []
        
        # Find pairs
        pairs = []
        for mod_a in module_ids:
            for mod_b in module_ids:
                if mod_a < mod_b and mod_b in reinforcement_scores.get(mod_a, {}):
                    score = reinforcement_scores[mod_a][mod_b]
                    if score > 0.3:  # Threshold for meaningful reinforcement
                        pairs.append((mod_a, mod_b, score))
        
        pairs.sort(key=lambda x: x[2], reverse=True)
        for mod_a, mod_b, _ in pairs[:max(3, len(pairs)//2)]:
            candidates.append([mod_a, mod_b])
            
        # Find triples from high-scoring pairs
        for i, (mod_a, mod_b, _) in enumerate(pairs[:5]):
            for mod_c in module_ids:
                if mod_c not in (mod_a, mod_b):
                    score_ac = reinforcement_scores.get(mod_a, {}).get(mod_c, 0)
                    score_bc = reinforcement_scores.get(mod_b, {}).get(mod_c, 0)
                    if score_ac > 0.2 and score_bc > 0.2:
                        candidates.append([mod_a, mod_b, mod_c])
                        break
                        
        return candidates
    
    def _create_coordinated_plan(self, group: List[str], all_modules: List[str]) -> Optional[CoordinatedMutation]:
        """
        Create a coordinated mutation plan for a group of modules.
        """
        if not all(m in self._module_states for m in group):
            return None
            
        mutation_types = []
        description_parts = []
        total_expected_improvement = 0.0
        dependency_impact = {}
        risk_factors = []
        
        for module_id in group:
            state = self._module_states[module_id]
            if not state.mutation_options:
                continue
                
            # Select best mutation option for this module
            best_option = max(state.mutation_options, 
                            key=lambda opt: opt.get('expected_improvement', 0))
            
            mutation_types.append(best_option.get('type', 'unknown'))
            description_parts.append(f"{module_id}: {best_option.get('description', 'unknown mutation')}")
            total_expected_improvement += best_option.get('expected_improvement', 0)
            
            # Calculate dependency impact
            for dep in state.dependencies:
                if dep in group:
                    dependency_impact[dep] = dependency_impact.get(dep, 0) + 0.2
                    
            # Assess risk
            risk_factors.append(best_option.get('risk', 0.5))
            
        if not mutation_types:
            return None
            
        # Calculate combined risk (slightly higher than individual risks)
        combined_risk = min(1.0, sum(risk_factors) / len(risk_factors) * 1.2)
        
        # Validate with global fitness function
        expected_global_improvement = self._estimate_global_improvement(group, mutation_types)
        
        return CoordinatedMutation(
            module_ids=group,
            mutation_types=mutation_types,
            description="; ".join(description_parts),
            expected_fitness_improvement=expected_global_improvement,
            dependency_impact=dict(dependency_impact),
            risk_score=combined_risk
        )
    
    def _estimate_global_improvement(self, module_ids: List[str], mutation_types: List[str]) -> float:
        """
        Estimate the global fitness improvement from coordinated mutations.
        Uses the global fitness function if available, otherwise estimates from module states.
        """
        try:
            # Create a mock state to evaluate
            mock_state = {}
            for i, mod_id in enumerate(module_ids):
                if mod_id in self._module_states:
                    state = self._module_states[mod_id]
                    mock_state[mod_id] = {
                        'current_fitness': state.current_fitness,
                        'mutation_type': mutation_types[i] if i < len(mutation_types) else 'unknown',
                        'expected_improvement': state.mutation_options[0].get('expected_improvement', 0) if state.mutation_options else 0
                    }
                    
            # Use global fitness function if it accepts dict
            try:
                return self.global_fitness_function(mock_state)
            except (TypeError, ValueError):
                # Fallback: estimate from individual improvements
                total = sum(s['expected_improvement'] for s in mock_state.values())
                synergy_bonus = total * 0.2  # 20% synergy bonus for coordinated changes
                return total + synergy_bonus
                
        except Exception:
            # Conservative estimate
            return sum(
                self._module_states[mod_id].current_fitness * 0.1 
                for mod_id in module_ids 
                if mod_id in self._module_states
            )
    
    def validate_coordinated_change(self, mutation: CoordinatedMutation) -> Tuple[bool, float, List[str]]:
        """
        Validate a coordinated mutation plan.
        
        Returns:
            Tuple of (is_valid, expected_fitness, warnings)
        """
        warnings = []
        
        # Check all modules exist
        for mod_id in mutation.module_ids:
            if mod_id not in self._module_states:
                warnings.append(f"Module {mod_id} not registered")
                
        # Check dependency consistency
        for mod_id in mutation.module_ids:
            if mod_id in mutation.dependency_impact:
                impact = mutation.dependency_impact[mod_id]
                if impact > 0.5:
                    warnings.append(f"High dependency impact on {mod_id}: {impact}")
                    
        # Check risk threshold
        if mutation.risk_score > 0.8:
            warnings.append(f"High risk score: {mutation.risk_score}")
            
        # Estimate combined fitness
        expected_fitness = mutation.expected_fitness_improvement
        
        # Validate with global fitness function
        is_valid = len(warnings) < 3 and expected_fitness > 0
        
        return is_valid, expected_fitness, warnings
    
    def get_mutually_reinforcing_pairs(self, module_ids: List[str], threshold: float = 0.4) -> List[Tuple[str, str, float]]:
        """
        Get pairs of modules that have mutually reinforcing relationships.
        
        Returns:
            List of (module_a, module_b, reinforcement_score) tuples
        """
        reinforcement_scores = self.analyze_dependency_graph(module_ids)
        pairs = []
        
        for mod_a in module_ids:
            for mod_b, score in reinforcement_scores.get(mod_a, {}).items():
                if mod_a < mod_b and score >= threshold:
                    pairs.append((mod_a, mod_b, score))
                    
        pairs.sort(key=lambda x: x[2], reverse=True)
        return pairs