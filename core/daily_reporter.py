"""Daily Reporter module for generating structured daily reports."""

import os
from datetime import datetime


class DailyReporter:
    """Generates daily markdown reports from evolution state."""

    def __init__(self, capabilities=None, cycle_number=0, failures=None, insights=None):
        """Initialize the reporter with evolution state.

        Args:
            capabilities: List of capability strings.
            cycle_number: Current evolution cycle number.
            failures: List of failure dictionaries with 'description', 'reason', 'resolution'.
            insights: List of insight strings.
        """
        self.capabilities = capabilities or []
        self.cycle_number = cycle_number
        self.failures = failures or []
        self.insights = insights or []

    def generate_report(self):
        """Generate and write the daily markdown report.

        Returns:
            The path to the generated report file as a string.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        report_dir = os.path.join("reports", "daily")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"{today}.md")

        report_content = self._format_report()
        with open(report_path, "w") as f:
            f.write(report_content)

        return report_path

    def _format_report(self):
        """Format the report content as markdown."""
        lines = []
        lines.append("# Daily Report")
        lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"**Cycle:** {self.cycle_number}")
        lines.append("")

        # Completed Goals - filter capabilities added today
        lines.append("## Completed Goals")
        today_caps = [cap for cap in self.capabilities if "today" in cap.lower() or "added" in cap.lower()]
        if today_caps:
            for cap in today_caps:
                lines.append(f"- {cap}")
        elif self.capabilities:
            for cap in self.capabilities:
                lines.append(f"- {cap}")
        else:
            lines.append("_No goals completed today._")
        lines.append("")

        # Failure Analysis
        lines.append("## Failure Analysis")
        if self.failures:
            for failure in self.failures:
                desc = failure.get("description", "Unknown failure")
                lines.append(f"- **{desc}**")
                reason = failure.get("reason")
                if reason:
                    lines.append(f"  - Reason: {reason}")
                resolution = failure.get("resolution")
                if resolution:
                    lines.append(f"  - Resolution: {resolution}")
        else:
            lines.append("_No failures recorded today._")
        lines.append("")

        # New Insights
        lines.append("## New Insights")
        if self.insights:
            for insight in self.insights:
                lines.append(f"- {insight}")
        else:
            lines.append("_No new insights today._")
        lines.append("")

        # Next Steps - prioritized from capabilities
        lines.append("## Next Steps")
        next_steps = []
        # Prioritize unresolved failures
        for failure in self.failures:
            if not failure.get("resolution"):
                next_steps.append(f"Resolve: {failure.get('description', 'Unknown failure')}")
        # Add capability-based next steps
        if self.capabilities:
            next_steps.append("Continue building on current capabilities.")
        if not next_steps:
            next_steps.append("Continue with current evolution cycle.")
        for step in next_steps:
            lines.append(f"- {step}")
        lines.append("")

        return "\n".join(lines)


def main():
    """Standalone testing function for DailyReporter."""
    # Example evolution state for testing
    capabilities = [
        "Added file parsing capability today",
        "Enhanced error handling",
        "Integrated logging system"
    ]
    cycle_number = 42
    failures = [
        {
            "description": "Failed to parse malformed JSON input",
            "reason": "Missing error handling for edge cases",
            "resolution": "Implemented try-except block with fallback parsing"
        },
        {
            "description": "API rate limit exceeded",
            "reason": "Too many concurrent requests",
            "resolution": None
        }
    ]
    insights = [
        "Discovered that retry logic improves reliability by 30%",
        "Learned that caching frequently accessed data reduces latency"
    ]

    reporter = DailyReporter(
        capabilities=capabilities,
        cycle_number=cycle_number,
        failures=failures,
        insights=insights
    )

    report_path = reporter.generate_report()
    print(f"Report generated at: {report_path}")

    # Print report content for verification
    with open(report_path, "r") as f:
        print(f.read())


if __name__ == "__main__":
    main()