import json
import os
import time
import random
import hashlib
from collections import defaultdict

class NashOrchestrator:
    """
    Orchestrator that periodically checks for Nash equilibria across module pairs,
    generates coordinated multi-module change plans, executes them via multi_module_forcer,
    and logs results to nash_history.json.
    """

    def __init__(self, nash_detector, multi_module_forcer, check_interval=60, history_file="nash_history.json"):
        """
        Initialize the orchestrator.

        Args:
            nash_detector: Instance of NashDetector (or compatible interface)
            multi_module_forcer: Instance of MultiModuleForcer (or compatible interface)
            check_interval: Seconds between equilibrium checks
            history_file: Path to the JSON history file
        """
        self.nash_detector = nash_detector
        self.multi_module_forcer = multi_module_forcer
        self.check_interval = check_interval
        self.history_file = history_file
        self.running = False
        self._load_history()

    def _load_history(self):
        """Load existing history from file or create empty history."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.history = {"equilibria": [], "plans": [], "executions": []}
        else:
            self.history = {"equilibria": [], "plans": [], "executions": []}

    def _save_history(self):
        """Save current history to file."""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def _generate_plan_id(self, modules):
        """Generate a unique plan ID based on module names and timestamp."""
        raw = f"{sorted(modules)}-{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def _detect_equilibria(self):
        """
        Check for Nash equilibria across all module pairs.
        Returns list of equilibrium tuples: (module_a, module_b, equilibrium_data)
        """
        equilibria = []
        modules = self.nash_detector.get_all_modules() if hasattr(self.nash_detector, 'get_all_modules') else []

        for i in range(len(modules)):
            for j in range(i + 1, len(modules)):
                mod_a = modules[i]
                mod_b = modules[j]
                try:
                    result = self.nash_detector.check_equilibrium(mod_a, mod_b)
                    if result.get("is_equilibrium", False):
                        equilibria.append((mod_a, mod_b, result))
                except Exception as e:
                    # Log error but continue checking other pairs
                    self._log_error(f"Equilibrium check failed for {mod_a}-{mod_b}: {e}")
        return equilibria

    def _generate_change_plan(self, equilibria):
        """
        Generate a coordinated multi-module change plan from detected equilibria.
        Selects 2-3 modules to change simultaneously.

        Returns:
            dict with keys: plan_id, modules, changes, timestamp
        """
        if not equilibria:
            return None

        # Collect all modules involved in equilibria
        module_set = set()
        for mod_a, mod_b, _ in equilibria:
            module_set.add(mod_a)
            module_set.add(mod_b)

        modules_list = list(module_set)
        random.shuffle(modules_list)

        # Select 2-3 modules (or fewer if not enough)
        num_to_change = min(random.randint(2, 3), len(modules_list))
        selected_modules = modules_list[:num_to_change]

        # Generate changes for each selected module
        changes = {}
        for module in selected_modules:
            # Find equilibrium data involving this module
            module_equilibria = [eq for eq in equilibria if module in (eq[0], eq[1])]
            if module_equilibria:
                # Use the first equilibrium data to inform the change
                eq_data = module_equilibria[0][2]
                change = self._derive_change_from_equilibrium(module, eq_data)
                if change:
                    changes[module] = change

        if not changes:
            return None

        plan = {
            "plan_id": self._generate_plan_id(list(changes.keys())),
            "modules": list(changes.keys()),
            "changes": changes,
            "timestamp": time.time()
        }
        return plan

    def _derive_change_from_equilibrium(self, module, eq_data):
        """
        Derive a specific change for a module based on equilibrium data.
        Returns a dict with 'type' and 'params' or None if no change needed.
        """
        # Example logic: adjust a parameter based on equilibrium strategy
        if "strategy" in eq_data and module in eq_data["strategy"]:
            strategy = eq_data["strategy"][module]
            if isinstance(strategy, dict):
                # Find a parameter to adjust
                for key, value in strategy.items():
                    if isinstance(value, (int, float)):
                        return {
                            "type": "parameter_adjustment",
                            "params": {
                                "parameter": key,
                                "new_value": value * (1 + random.uniform(-0.1, 0.1))
                            }
                        }
        return None

    def _execute_plan(self, plan):
        """
        Execute a change plan via multi_module_forcer.
        Returns execution result.
        """
        if not plan:
            return {"status": "no_plan", "message": "No plan to execute"}

        try:
            result = self.multi_module_forcer.apply_changes(plan["modules"], plan["changes"])
            execution_record = {
                "plan_id": plan["plan_id"],
                "timestamp": time.time(),
                "status": result.get("status", "unknown"),
                "details": result
            }
            self.history["executions"].append(execution_record)
            self._save_history()
            return execution_record
        except Exception as e:
            error_record = {
                "plan_id": plan["plan_id"],
                "timestamp": time.time(),
                "status": "failed",
                "error": str(e)
            }
            self.history["executions"].append(error_record)
            self._save_history()
            return error_record

    def _log_error(self, message):
        """Log an error to the history."""
        if "errors" not in self.history:
            self.history["errors"] = []
        self.history["errors"].append({
            "timestamp": time.time(),
            "message": message
        })
        self._save_history()

    def run_cycle(self):
        """
        Execute one full cycle: detect equilibria, generate plan, execute plan.
        Returns the execution result.
        """
        # Step 1: Detect equilibria
        equilibria = self._detect_equilibria()

        # Record equilibria in history
        for eq in equilibria:
            self.history["equilibria"].append({
                "module_a": eq[0],
                "module_b": eq[1],
                "data": eq[2],
                "timestamp": time.time()
            })

        if not equilibria:
            return {"status": "no_equilibrium", "message": "No Nash equilibria detected"}

        # Step 2: Generate change plan
        plan = self._generate_change_plan(equilibria)
        if plan:
            self.history["plans"].append(plan)
            self._save_history()

        # Step 3: Execute plan
        result = self._execute_plan(plan)
        return result

    def start(self):
        """Start the orchestrator loop."""
        self.running = True
        while self.running:
            result = self.run_cycle()
            if result.get("status") == "no_equilibrium":
                time.sleep(self.check_interval)
            else:
                # If changes were made, check more frequently for a bit
                time.sleep(max(1, self.check_interval // 2))

    def stop(self):
        """Stop the orchestrator loop."""
        self.running = False

    def get_history(self):
        """Return the full history."""
        return self.history

    def clear_history(self):
        """Clear all history."""
        self.history = {"equilibria": [], "plans": [], "executions": []}
        self._save_history()

    def get_equilibrium_summary(self):
        """Return a summary of all detected equilibria."""
        summary = defaultdict(list)
        for eq in self.history.get("equilibria", []):
            pair = (eq["module_a"], eq["module_b"])
            summary[pair].append(eq["data"])
        return dict(summary)

    def get_execution_stats(self):
        """Return statistics about plan executions."""
        executions = self.history.get("executions", [])
        total = len(executions)
        successful = sum(1 for e in executions if e.get("status") == "success")
        failed = sum(1 for e in executions if e.get("status") == "failed")
        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0.0
        }