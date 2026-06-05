from typing import Dict, List, Any
import json
from datetime import datetime
from .capability_fitness_tracker import CapabilityFitnessTracker

class CapabilityDashboard:
    """Dashboard for monitoring and reporting on capability fitness metrics."""
    
    def __init__(self, fitness_tracker: CapabilityFitnessTracker):
        self.fitness_tracker = fitness_tracker
        self._risk_threshold = 0.3  # Fitness score below which a capability is considered at risk
    
    def set_risk_threshold(self, threshold: float) -> None:
        """Set the threshold for considering a capability at risk."""
        if not 0 <= threshold <= 1:
            raise ValueError("Risk threshold must be between 0 and 1")
        self._risk_threshold = threshold
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive dashboard report."""
        capabilities = self.fitness_tracker.get_all_capabilities()
        
        report_entries = []
        for cap_name, cap_data in capabilities.items():
            entry = {
                "capability_name": cap_name,
                "fitness_score": cap_data.get("fitness_score", 0.0),
                "deprecated": cap_data.get("deprecated", False),
                "cycles_since_last_use": cap_data.get("cycles_since_last_use", 0),
                "at_risk": cap_data.get("fitness_score", 0.0) < self._risk_threshold
            }
            report_entries.append(entry)
        
        summary = self._generate_summary(report_entries)
        
        report = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "risk_threshold": self._risk_threshold,
            "capabilities": report_entries,
            "summary": summary
        }
        
        return report
    
    def _generate_summary(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics from report entries."""
        if not entries:
            return {
                "total_capabilities": 0,
                "average_fitness": 0.0,
                "number_deprecated": 0,
                "number_at_risk": 0
            }
        
        total = len(entries)
        avg_fitness = sum(e["fitness_score"] for e in entries) / total
        num_deprecated = sum(1 for e in entries if e["deprecated"])
        num_at_risk = sum(1 for e in entries if e["at_risk"])
        
        return {
            "total_capabilities": total,
            "average_fitness": round(avg_fitness, 4),
            "number_deprecated": num_deprecated,
            "number_at_risk": num_at_risk
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Output the report as a JSON string for API consumption."""
        report = self.generate_report()
        return json.dumps(report, indent=indent)
    
    def print_formatted_report(self) -> None:
        """Print a human-readable formatted report to stdout."""
        report = self.generate_report()
        
        print("=" * 70)
        print("CAPABILITY FITNESS DASHBOARD REPORT")
        print(f"Generated at: {report['generated_at']}")
        print(f"Risk threshold: {report['risk_threshold']}")
        print("=" * 70)
        
        print("\n--- Capability Details ---")
        print(f"{'Capability Name':<30} {'Fitness':<10} {'Deprecated':<12} {'Cycles Since Use':<16} {'At Risk':<8}")
        print("-" * 76)
        
        for cap in report["capabilities"]:
            name = cap["capability_name"][:29]
            fitness = f"{cap['fitness_score']:.4f}"
            deprecated = "YES" if cap["deprecated"] else "NO"
            cycles = str(cap["cycles_since_last_use"])
            at_risk = "YES" if cap["at_risk"] else "NO"
            print(f"{name:<30} {fitness:<10} {deprecated:<12} {cycles:<16} {at_risk:<8}")
        
        print("\n--- Summary Statistics ---")
        summary = report["summary"]
        print(f"Total capabilities: {summary['total_capabilities']}")
        print(f"Average fitness score: {summary['average_fitness']:.4f}")
        print(f"Number deprecated: {summary['number_deprecated']}")
        print(f"Number at risk: {summary['number_at_risk']}")
        print("=" * 70)


def create_dashboard(fitness_tracker: CapabilityFitnessTracker) -> CapabilityDashboard:
    """Factory function to create a CapabilityDashboard instance."""
    return CapabilityDashboard(fitness_tracker)