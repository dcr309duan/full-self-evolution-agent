class ModuleInteractionTracker:
    """
    Tracks pairwise module interaction success/failure rates and detects
    when no single-module change improves the system (Nash equilibrium).
    """
    
    def __init__(self, num_modules=5, sliding_window_size=20):
        self.num_modules = num_modules
        self.sliding_window_size = sliding_window_size
        
        self.module_interaction_pairs = {}
        self.interaction_history = []
        self.interaction_frequencies = {}
        self.interaction_success_rates = {}
        self.module_improvement_history = {}
        
        self.improvement_threshold = 0.05
        self.equilibrium_window = 5
        self.equilibrium_tolerance = 0.001
        self.consecutive_no_improvement = 0
        self.in_equilibrium = False
        self.equilibrium_pairs = []
        
        self.total_cycles = 0
        self.cycles_in_equilibrium = 0
        self.total_multi_module_perturbations_attempted = 0
        self.successful_multi_module_perturbations = 0
        
        self.dependency_graph = {}
    
    def _get_or_create_pair(self, key):
        if key not in self.module_interaction_pairs:
            self.module_interaction_pairs[key] = {
                "success_count": 0,
                "total_count": 0,
                "success_rate": 0.0,
                "last_cycles": []
            }
        return self.module_interaction_pairs[key]
    
    def _add_to_sliding_window(self, item):
        self.interaction_history.append(item)
        if len(self.interaction_history) > self.sliding_window_size:
            self.interaction_history.pop(0)
    
    def record_interaction(self, module_i, module_j, success):
        interaction_key = (min(module_i, module_j), max(module_i, module_j))
        self._add_to_sliding_window((interaction_key, success))
        
        self.interaction_frequencies = {}
        success_counts = {}
        total_counts = {}
        
        for key, suc in self.interaction_history:
            if key not in total_counts:
                total_counts[key] = 0
                success_counts[key] = 0
            total_counts[key] += 1
            if suc:
                success_counts[key] += 1
        
        for key in total_counts:
            self.interaction_frequencies[key] = total_counts[key]
            self.interaction_success_rates[key] = success_counts[key] / total_counts[key]
        
        pair_key = (module_i, module_j)
        pair_data = self._get_or_create_pair(pair_key)
        pair_data["total_count"] += 1
        if success:
            pair_data["success_count"] += 1
        pair_data["success_rate"] = pair_data["success_count"] / pair_data["total_count"] if pair_data["total_count"] > 0 else 0.0
        pair_data["last_cycles"].append(success)
        if len(pair_data["last_cycles"]) > self.sliding_window_size:
            pair_data["last_cycles"].pop(0)
        
        if module_i not in self.dependency_graph:
            self.dependency_graph[module_i] = set()
        if module_j not in self.dependency_graph:
            self.dependency_graph[module_j] = set()
        self.dependency_graph[module_i].add(module_j)
        self.dependency_graph[module_j].add(module_i)
    
    def update_module_improvement(self, module_idx, improved):
        if module_idx not in self.module_improvement_history:
            self.module_improvement_history[module_idx] = []
        self.module_improvement_history[module_idx].append(improved)
        if len(self.module_improvement_history[module_idx]) > 3:
            self.module_improvement_history[module_idx].pop(0)
    
    def detect_nash_equilibrium(self, module_scores, dependency_matrix):
        if len(module_scores) < self.equilibrium_window:
            return False, []
        
        improvement_found = False
        for module_idx in range(self.num_modules):
            original_deps = dependency_matrix[module_idx][:]
            
            dep_idx = int(random() * self.num_modules)
            original_value = dependency_matrix[module_idx][dep_idx]
            dependency_matrix[module_idx][dep_idx] = min(1.0, original_value + 0.1)
            
            new_score = self._compute_module_score(module_idx, module_scores, dependency_matrix)
            
            dependency_matrix[module_idx] = original_deps
            
            if new_score > module_scores[module_idx] * (1 + self.improvement_threshold):
                improvement_found = True
                break
        
        if improvement_found:
            self.consecutive_no_improvement = 0
            return False, []
        
        all_modules_optimal = True
        equilibrium_pairs = []
        
        for module_idx in range(self.num_modules):
            module_success_rates = []
            for pair_key, pair_data in self.module_interaction_pairs.items():
                if module_idx in pair_key:
                    module_success_rates.append(pair_data["success_rate"])
            
            if not module_success_rates:
                all_modules_optimal = False
                continue
            
            avg_success_rate = sum(module_success_rates) / len(module_success_rates)
            if avg_success_rate <= 0.8:
                all_modules_optimal = False
                continue
            
            module_improvement_history = self.module_improvement_history.get(module_idx, [])
            if len(module_improvement_history) < 3:
                all_modules_optimal = False
                continue
            
            has_improvement = any(module_improvement_history)
            if has_improvement:
                all_modules_optimal = False
                continue
            
            for pair_key, pair_data in self.module_interaction_pairs.items():
                if module_idx in pair_key and pair_data["success_rate"] > 0.8:
                    other_module = pair_key[0] if pair_key[1] == module_idx else pair_key[1]
                    other_improvement_history = self.module_improvement_history.get(other_module, [])
                    if len(other_improvement_history) >= 3 and not any(other_improvement_history):
                        other_success_rates = []
                        for other_pair_key, other_pair_data in self.module_interaction_pairs.items():
                            if other_module in other_pair_key:
                                other_success_rates.append(other_pair_data["success_rate"])
                        if other_success_rates:
                            other_avg_success_rate = sum(other_success_rates) / len(other_success_rates)
                            if other_avg_success_rate > 0.8:
                                equilibrium_pairs.append(pair_key)
        
        if all_modules_optimal and equilibrium_pairs:
            self.consecutive_no_improvement += 1
            if self.consecutive_no_improvement >= 3:
                self.in_equilibrium = True
                self.equilibrium_pairs = equilibrium_pairs
                return True, equilibrium_pairs
        
        self.consecutive_no_improvement = 0
        return False, []
    
    def detect_nash_equilibrium_with_dependency_graph(self, module_scores, dependency_matrix):
        if len(module_scores) < self.equilibrium_window:
            return False, [], {}
        
        modules_in_equilibrium = []
        breakout_opportunities = {}
        
        for module_idx in range(self.num_modules):
            improvement_history = self.module_improvement_history.get(module_idx, [])
            if len(improvement_history) >= 5:
                if not any(improvement_history[-5:]):
                    modules_in_equilibrium.append(module_idx)
                    
                    neighbors = self.dependency_graph.get(module_idx, set())
                    if neighbors:
                        neighbor_equilibrium = []
                        for neighbor in neighbors:
                            neighbor_history = self.module_improvement_history.get(neighbor, [])
                            if len(neighbor_history) >= 5 and not any(neighbor_history[-5:]):
                                neighbor_equilibrium.append(neighbor)
                        
                        if neighbor_equilibrium:
                            for neighbor in neighbor_equilibrium:
                                combo_key = tuple(sorted([module_idx, neighbor]))
                                if combo_key not in breakout_opportunities:
                                    freq_key = (min(module_idx, neighbor), max(module_idx, neighbor))
                                    breakout_opportunities[combo_key] = {
                                        "type": "pair",
                                        "modules": [module_idx, neighbor],
                                        "interaction_frequency": self.interaction_frequencies.get(freq_key, 0),
                                        "success_rate": self.interaction_success_rates.get(freq_key, 0.0)
                                    }
                            
                            if len(neighbor_equilibrium) >= 2:
                                for i in range(len(neighbor_equilibrium)):
                                    for j in range(i + 1, len(neighbor_equilibrium)):
                                        combo_key = tuple(sorted([module_idx, neighbor_equilibrium[i], neighbor_equilibrium[j]]))
                                        if combo_key not in breakout_opportunities:
                                            freq_sum = 0
                                            rate_sum = 0
                                            count = 0
                                            for a, b in [(module_idx, neighbor_equilibrium[i]), (module_idx, neighbor_equilibrium[j]), (neighbor_equilibrium[i], neighbor_equilibrium[j])]:
                                                fk = (min(a, b), max(a, b))
                                                freq_sum += self.interaction_frequencies.get(fk, 0)
                                                rate_sum += self.interaction_success_rates.get(fk, 0.0)
                                                count += 1
                                            breakout_opportunities[combo_key] = {
                                                "type": "triple",
                                                "modules": [module_idx, neighbor_equilibrium[i], neighbor_equilibrium[j]],
                                                "interaction_frequency": freq_sum,
                                                "success_rate": rate_sum / count if count > 0 else 0.0
                                            }
        
        is_equilibrium = len(modules_in_equilibrium) >= 2
        
        if is_equilibrium:
            self.consecutive_no_improvement += 1
            if self.consecutive_no_improvement >= 3:
                self.in_equilibrium = True
                equilibrium_pairs = []
                for combo_key, combo_data in breakout_opportunities.items():
                    if combo_data["type"] == "pair":
                        equilibrium_pairs.append(tuple(combo_data["modules"]))
                self.equilibrium_pairs = equilibrium_pairs
                return True, equilibrium_pairs, breakout_opportunities
        
        self.consecutive_no_improvement = 0
        return False, [], breakout_opportunities
    
    def _compute_module_score(self, module_idx, module_scores, dependency_matrix):
        score = 0.0
        for j in range(self.num_modules):
            score += dependency_matrix[module_idx][j] * (module_scores[j] if j != module_idx else 1.0)
        score += random() * 0.1 - 0.05
        return score
    
    def get_interaction_stats(self):
        return {
            "interaction_frequencies": dict(self.interaction_frequencies),
            "interaction_success_rates": dict(self.interaction_success_rates),
            "module_interaction_pairs": {str(k): dict(v) for k, v in self.module_interaction_pairs.items()},
            "equilibrium_pairs": self.equilibrium_pairs,
            "in_equilibrium": self.in_equilibrium,
            "dependency_graph": {str(k): list(v) for k, v in self.dependency_graph.items()}
        }
    
    def get_logging_metrics(self):
        return {
            "total_cycles": self.total_cycles,
            "cycles_in_equilibrium": self.cycles_in_equilibrium,
            "total_multi_module_perturbations_attempted": self.total_multi_module_perturbations_attempted,
            "successful_multi_module_perturbations": self.successful_multi_module_perturbations,
            "multi_module_perturbation_success_rate": (
                self.successful_multi_module_perturbations / self.total_multi_module_perturbations_attempted
                if self.total_multi_module_perturbations_attempted > 0 else 0.0
            )
        }


class CoordinatedMutationPlanner:
    def __init__(self, num_modules=5):
        self.num_modules = num_modules
    
    def plan_mutations(self, equilibrium_pairs, interaction_frequencies, dependency_matrix, breakout_opportunities=None):
        if breakout_opportunities and len(breakout_opportunities) > 0:
            sorted_opportunities = sorted(
                breakout_opportunities.items(),
                key=lambda x: x[1]["interaction_frequency"],
                reverse=True
            )
            
            best_opportunity = sorted_opportunities[0][1]
            modules_to_mutate = best_opportunity["modules"]
            
            mutation_plan = {
                "type": "coordinated_mutation",
                "modules_changed": modules_to_mutate,
                "mutations": [],
                "rationale": "Breakout from equilibrium using " + best_opportunity["type"] + " combination"
            }
            
            for module_idx in modules_to_mutate:
                mutation_type = ["dependency_shift", "dependency_swap", "dependency_reset"][int(random() * 3)]
                
                if mutation_type == "dependency_shift":
                    shift_amount = random() * 0.4 - 0.2
                    original = dependency_matrix[module_idx][:]
                    new_deps = []
                    for j in range(self.num_modules):
                        new_val = max(0.0, min(1.0, dependency_matrix[module_idx][j] + shift_amount))
                        new_deps.append(new_val)
                    mutation_plan["mutations"].append({
                        "module": module_idx,
                        "type": "shift",
                        "amount": shift_amount,
                        "original": original,
                        "new": new_deps
                    })
                    
                elif mutation_type == "dependency_swap":
                    indices = list(range(self.num_modules))
                    j1 = indices[int(random() * len(indices))]
                    indices.remove(j1)
                    j2 = indices[int(random() * len(indices))]
                    original = dependency_matrix[module_idx][:]
                    new_deps = original[:]
                    new_deps[j1], new_deps[j2] = new_deps[j2], new_deps[j1]
                    mutation_plan["mutations"].append({
                        "module": module_idx,
                        "type": "swap",
                        "indices": (j1, j2),
                        "original": original,
                        "new": new_deps
                    })
                    
                else:
                    num_to_reset = int(random() * max(1, self.num_modules // 2)) + 1
                    indices = list(range(self.num_modules))
                    indices_to_reset = []
                    for _ in range(num_to_reset):
                        idx = indices[int(random() * len(indices))]
                        indices_to_reset.append(idx)
                        indices.remove(idx)
                    original = dependency_matrix[module_idx][:]
                    new_deps = original[:]
                    for j in indices_to_reset:
                        new_deps[j] = random()
                    mutation_plan["mutations"].append({
                        "module": module_idx,
                        "type": "reset",
                        "indices_reset": indices_to_reset,
                        "original": original,
                        "new": new_deps
                    })
            
            return mutation_plan
        
        modules_to_mutate = self._select_modules_for_mutation(equilibrium_pairs, interaction_frequencies)
        
        if len(modules_to_mutate) < 2:
            modules_to_mutate = []
            indices = list(range(self.num_modules))
            for _ in range(min(3, self.num_modules)):
                idx = indices[int(random() * len(indices))]
                modules_to_mutate.append(idx)
                indices.remove(idx)
        
        mutation_plan = {
            "type": "coordinated_mutation",
            "modules_changed": modules_to_mutate,
            "mutations": [],
            "rationale": "Simultaneous changes to escape single-module optimization"
        }
        
        for module_idx in modules_to_mutate:
            mutation_type = ["dependency_shift", "dependency_swap", "dependency_reset"][int(random() * 3)]
            
            if mutation_type == "dependency_shift":
                shift_amount = random() * 0.4 - 0.2
                original = dependency_matrix[module_idx][:]
                new_deps = []
                for j in range(self.num_modules):
                    new_val = max(0.0, min(1.0, dependency_matrix[module_idx][j] + shift_amount))
                    new_deps.append(new_val)
                mutation_plan["mutations"].append({
                    "module": module_idx,
                    "type": "shift",
                    "amount": shift_amount,
                    "original": original,
                    "new": new_deps
                })
                
            elif mutation_type == "dependency_swap":
                indices = list(range(self.num_modules))
                j1 = indices[int(random() * len(indices))]
                indices.remove(j1)
                j2 = indices[int(random() * len(indices))]
                original = dependency_matrix[module_idx][:]
                new_deps = original[:]
                new_deps[j1], new_deps[j2] = new_deps[j2], new_deps[j1]
                mutation_plan["mutations"].append({
                    "module": module_idx,
                    "type": "swap",
                    "indices": (j1, j2),
                    "original": original,
                    "new": new_deps
                })
                
            else:
                num_to_reset = int(random() * max(1, self.num_modules // 2)) + 1
                indices = list(range(self.num_modules))
                indices_to_reset = []
                for _ in range(num_to_reset):
                    idx = indices[int(random() * len(indices))]
                    indices_to_reset.append(idx)
                    indices.remove(idx)
                original = dependency_matrix[module_idx][:]
                new_deps = original[:]
                for j in indices_to_reset:
                    new_deps[j] = random()
                mutation_plan["mutations"].append({
                    "module": module_idx,
                    "type": "reset",
                    "indices_reset": indices_to_reset,
                    "original": original,
                    "new": new_deps
                })
        
        return mutation_plan
    
    def _select_modules_for_mutation(self, equilibrium_pairs, interaction_frequencies):
        if not equilibrium_pairs:
            modules = []
            indices = list(range(self.num_modules))
            for _ in range(min(3, self.num_modules)):
                idx = indices[int(random() * len(indices))]
                modules.append(idx)
                indices.remove(idx)
            return modules
        
        modules_in_equilibrium = set()
        for pair in equilibrium_pairs:
            modules_in_equilibrium.add(pair[0])
            modules_in_equilibrium.add(pair[1])
        
        if len(modules_in_equilibrium) >= 2:
            selected = list(modules_in_equilibrium)
            if len(selected) > 3:
                module_frequencies = {}
                for m in modules_in_equilibrium:
                    module_frequencies[m] = 0
                for (i, j), freq in interaction_frequencies.items():
                    if i in modules_in_equilibrium:
                        module_frequencies[i] = module_frequencies.get(i, 0) + freq
                    if j in modules_in_equilibrium:
                        module_frequencies[j] = module_frequencies.get(j, 0) + freq
                
                sorted_modules = sorted(module_frequencies.items(), key=lambda x: x[1], reverse=True)
                selected = [m[0] for m in sorted_modules[:3]]
            
            return selected[:3]
        
        modules = []
        indices = list(range(self.num_modules))
        for _ in range(min(3, self.num_modules)):
            idx = indices[int(random() * len(indices))]
            modules.append(idx)
            indices.remove(idx)
        return modules


class NashDetector:
    """
    Detects when no single module change improves the system (Nash equilibrium).
    Uses a simple scoring matrix and convergence detection.
    """
    
    def __init__(self, num_modules=5):
        self.num_modules = num_modules
        self.score_history = []
        self.equilibrium_window = 5
        self.equilibrium_tolerance = 0.001
        self.consecutive_no_improvement = 0
        self.in_equilibrium = False
        self.equilibrium_pairs = []
        self.module_scores = [0.0] * num_modules
        self.dependency_matrix = [[random() for _ in range(num_modules)] for _ in range(num_modules)]
        self.interaction_tracker = ModuleInteractionTracker(num_modules)
    
    def detect_nash(self):
        """
        Detect if the system is in Nash equilibrium.
        Returns True if no single module change improves the system.
        """
        if len(self.score_history) < self.equilibrium_window:
            return False
        
        recent_scores = self.score_history[-self.equilibrium_window:]
        
        for i in range(self.num_modules):
            scores_i = [s[i] for s in recent_scores]
            if max(scores_i) - min(scores_i) > self.equilibrium_tolerance:
                self.consecutive_no_improvement = 0
                return False
        
        is_equilibrium, equilibrium_pairs, _ = self.interaction_tracker.detect_nash_equilibrium_with_dependency_graph(
            self.module_scores, self.dependency_matrix
        )
        
        if is_equilibrium:
            self.in_equilibrium = True
            self.equilibrium_pairs = equilibrium_pairs
            return True
        
        return False
    
    def update_scores(self, new_scores):
        self.module_scores = new_scores
        self.score_history.append(new_scores[:])
        if len(self.score_history) > 100:
            self.score_history.pop(0)


class MultiModuleForcer:
    """
    Generates coordinated multi-module mutations by analyzing dependency graphs
    and proposing changes to 2-3 modules simultaneously.
    """
    
    def __init__(self, num_modules=5):
        self.num_modules = num_modules
        self.planner = CoordinatedMutationPlanner(num_modules)
        self.dependency_matrix = [[random() for _ in range(num_modules)] for _ in range(num_modules)]
        self.equilibrium_pairs = []
        self.interaction_frequencies = {}
        self.breakout_opportunities = {}
    
    def force_multi_module_change(self):
        """
        Generate a coordinated multi-module change plan.
        Returns a dictionary describing the changes to make.
        """
        mutation_plan = self.planner.plan_mutations(
            self.equilibrium_pairs,
            self.interaction_frequencies,
            self.dependency_matrix,
            self.breakout_opportunities
        )
        return mutation_plan
    
    def update_state(self, dependency_matrix, equilibrium_pairs, interaction_frequencies, breakout_opportunities):
        self.dependency_matrix = dependency_matrix
        self.equilibrium_pairs = equilibrium_pairs
        self.interaction_frequencies = interaction_frequencies
        self.breakout_opportunities = breakout_opportunities


def random():
    """Simple linear congruential generator for reproducibility."""
    global _random_seed
    if '_random_seed' not in globals():
        _random_seed = 123456789
    _random_seed = (_random_seed * 1103515245 + 12345) & 0x7fffffff
    return _random_seed / 0x7fffffff


def seed(val):
    global _random_seed
    _random_seed = val


class NashDetectorAndForcer:
    """
    A self-contained module for detecting Nash equilibria in a system of interacting modules
    and forcing coordinated multi-module changes to escape suboptimal equilibria.
    
    Uses only built-in Python types (dicts, lists, sets) with no external libraries.
    """

    def __init__(self, num_modules=5, random_seed=None):
        if random_seed is not None:
            seed(random_seed)
        
        self.num_modules = num_modules
        self.dependency_matrix = [[random() for _ in range(num_modules)] for _ in range(num_modules)]
        self.module_scores = [0.0 for _ in range(num_modules)]
        self.score_history = []
        
        self.interaction_tracker = ModuleInteractionTracker(num_modules)
        self.mutation_planner = CoordinatedMutationPlanner(num_modules)
        
        self.equilibrium_window = 5
        self.equilibrium_tolerance = 0.001
        
        self.in_equilibrium = False
        self.equilibrium_iterations = 0
        
        self.consecutive_no_improvement = 0
        self.equilibrium_detected = False
        
        self.module_interaction_pairs = {}
        self.module_improvement_history = {}
        
        self.equilibrium_pairs = []
        self.breakout_opportunities = {}
        
        self.last_mutation_plan = None
        self.last_mutation_success = None

    def set_dependency_matrix(self, matrix):
        if len(matrix) != self.num_modules:
            raise ValueError("Matrix must have " + str(self.num_modules) + " rows")
        for row in matrix:
            if len(row) != self.num_modules:
                raise ValueError("Each row must have " + str(self.num_modules) + " elements")
        self.dependency_matrix = matrix

    def compute_module_score(self, module_idx):
        score = 0.0
        for j in range(self.num_modules):
            score += self.dependency_matrix[module_idx][j] * (self.module_scores[j] if j != module_idx else 1.0)
        score += random() * 0.1 - 0.05
        return score

    def update_all_scores(self):
        new_scores = []
        for i in range(self.num_modules):
            new_scores.append(self.compute_module_score(i))
        
        self.module_scores = new_scores
        self.score_history.append(new_scores[:])
        
        if len(self.score_history) > 100:
            self.score_history.pop(0)
        
        return new_scores

    def record_interaction(self, module_i, module_j, success):
        self.interaction_tracker.record_interaction(module_i, module_j, success)
        
        interaction_key = (min(module_i, module_j), max(module_i, module_j))
        
        pair_key = (module_i, module_j)
        if pair_key not in self.module_interaction_pairs:
            self.module_interaction_pairs[pair_key] = {"success_count": 0, "total_count": 0, "success_rate": 0.0, "last_cycles": []}
        pair_data = self.module_interaction_pairs[pair_key]
        pair_data["total_count"] += 1
        if success:
            pair_data["success_count"] += 1
        pair_data["success_rate"] = pair_data["success_count"] / pair_data["total_count"] if pair_data["total_count"] > 0 else 0.0
        pair_data["last_cycles"].append(success)
        if len(pair_data["last_cycles"]) > 20:
            pair_data["last_cycles"].pop(0)

    def detect_nash_equilibrium(self):
        if len(self.score_history) < self.equilibrium_window:
            return False
        
        recent_scores = self.score_history[-self.equilibrium_window:]
        
        for i in range(self.num_modules):
            scores_i = [s[i] for s in recent_scores]
            if max(scores_i) - min(scores_i) > self.equilibrium_tolerance:
                self.consecutive_no_improvement = 0
                return False
        
        is_equilibrium, equilibrium_pairs, breakout_opportunities = self.interaction_tracker.detect_nash_equilibrium_with_dependency_graph(
            self.module_scores, self.dependency_matrix
        )
        
        if is_equilibrium:
            self.in_equilibrium = True
            self.equilibrium_iterations += 1
            self.equilibrium_detected = True
            self.equilibrium_pairs = equilibrium_pairs
            self.breakout_opportunities = breakout_opportunities
            return True
        
        return False

    def _check_interaction_stability(self):
        if len(self.interaction_tracker.interaction_history) < 10:
            return False
        
        if not self.interaction_tracker.interaction_frequencies:
            return False
        
        total_interactions = sum(self.interaction_tracker.interaction_frequencies.values())
        if total_interactions == 0:
            return False
        
        for key, freq in self.interaction_tracker.interaction_frequencies.items():
            if freq / total_interactions > 0.5:
                return False
        
        if self.interaction_tracker.interaction_success_rates:
            rates = list(self.interaction_tracker.interaction_success_rates.values())
            if rates:
                avg_rate = sum(rates) / len(rates)
                if avg_rate < 0.2 or avg_rate > 0.9:
                    return False
        
        return True

    def check_equilibrium(self):
        return self.detect_nash_equilibrium()

    def force_coordinated_change(self, num_modules_to_change=3):
        num_modules_to_change = 3
        
        mutation_plan = self.mutation_planner.plan_mutations(
            self.equilibrium_pairs,
            self.interaction_tracker.interaction_frequencies,
            self.dependency_matrix,
            self.breakout_opportunities
        )
        
        self.interaction_tracker.total_multi_module_perturbations_attempted += 1
        
        return mutation_plan

    def _select_interdependent_modules(self, num_modules):
        if not self.interaction_tracker.interaction_frequencies:
            modules = []
            indices = list(range(self.num_modules))
            for _ in range(num_modules):
                idx = indices[int(random() * len(indices))]
                modules.append(idx)
                indices.remove(idx)
            return modules
        
        sorted_interactions = sorted(
            self.interaction_tracker.interaction_frequencies.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        selected_modules = set()
        for (i, j), freq in sorted_interactions:
            if len(selected_modules) >= num_modules:
                break
            selected_modules.add(i)
            if len(selected_modules) < num_modules:
                selected_modules.add(j)
        
        while len(selected_modules) < num_modules:
            candidate = int(random() * self.num_modules)
            if candidate not in selected_modules:
                selected_modules.add(candidate)
        
        return list(selected_modules)[:num_modules]

    def execute_coordinated_change(self, mutation_plan):
        execution_record = {
            "type": "coordinated_mutation_executed",
            "modules_changed": mutation_plan["modules_changed"],
            "mutations_applied": []
        }
        
        for mutation in mutation_plan["mutations"]:
            module_idx = mutation["module"]
            new_deps = mutation["new"]
            
            self.dependency_matrix[module_idx] = new_deps[:]
            
            execution_record["mutations_applied"].append({
                "module": module_idx,
                "type": mutation["type"],
                "new_dependencies": new_deps
            })
        
        self.update_all_scores()
        self.in_equilibrium = False
        self.equilibrium_detected = False
        self.consecutive_no_improvement = 0
        self.breakout_opportunities = {}
        
        self.interaction_tracker.successful_multi_module_perturbations += 1
        
        return execution_record

    def run_equilibrium_cycle(self, max_iterations=100):
        results = {
            "iterations": 0,
            "equilibria_detected": 0,
            "coordinated_changes_forced": 0,
            "final_scores": [],
            "history": [],
            "logging_metrics": {}
        }
        
        for iteration in range(max_iterations):
            scores = self.update_all_scores()
            
            for i in range(self.num_modules):
                for j in range(i + 1, self.num_modules):
                    interaction_success = random() > 0.3
                    self.record_interaction(i, j, interaction_success)
            
            self.interaction_tracker.total_cycles += 1
            
            if self.detect_nash_equilibrium():
                results["equilibria_detected"] += 1
                self.interaction_tracker.cycles_in_equilibrium += 1
                
                num_to_change = 3
                change_plan = self.force_coordinated_change(num_to_change)
                
                execution_result = self.execute_coordinated_change(change_plan)
                results["coordinated_changes_forced"] += 1
                results["history"].append({
                    "iteration": iteration,
                    "equilibrium_detected": True,
                    "change_plan": change_plan,
                    "execution": execution_result,
                    "scores_after": self.module_scores[:]
                })
            
            results["iterations"] = iteration + 1
        
        results["final_scores"] = self.module_scores[:]
        results["logging_metrics"] = self.interaction_tracker.get_logging_metrics()
        
        return results


def detect_nash(module_scores, dependency_matrix):
    """
    Simple API function to detect Nash equilibrium.
    Returns True if no single module change improves the system.
    """
    detector = NashDetector(len(module_scores))
    detector.module_scores = module_scores
    detector.dependency_matrix = dependency_matrix
    return detector.detect_nash()


def force_multi_module_change(dependency_matrix, equilibrium_pairs, interaction_frequencies, breakout_opportunities=None):
    """
    Simple API function to force a multi-module change.
    Returns a mutation plan dictionary.
    """
    num_modules = len(dependency_matrix)
    forcer = MultiModuleForcer(num_modules)
    forcer.update_state(dependency_matrix, equilibrium_pairs, interaction_frequencies, breakout_opportunities or {})
    return forcer.force_multi_module_change()