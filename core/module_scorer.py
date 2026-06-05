from collections import defaultdict, deque

class ModuleScorer:
    def __init__(self, window_size=10):
        self.window_size = window_size
        self.mutation_results = defaultdict(lambda: deque(maxlen=window_size))
        self.dep_failures = defaultdict(lambda: deque(maxlen=window_size))

    def record_mutation(self, module_name, success):
        self.mutation_results[module_name].append(1 if success else 0)

    def record_dep_failure(self, module_name):
        self.dep_failures[module_name].append(1)

    def get_module_scores(self):
        scores = {}
        for mod in set(list(self.mutation_results.keys()) + list(self.dep_failures.keys())):
            muts = self.mutation_results.get(mod, [])
            deps = self.dep_failures.get(mod, [])
            mut_rate = sum(muts) / len(muts) if muts else 0.5
            dep_rate = sum(deps) / self.window_size if deps else 0.0
            scores[mod] = {"mutation_success_rate": mut_rate, "dep_failure_rate": dep_rate}
        return scores