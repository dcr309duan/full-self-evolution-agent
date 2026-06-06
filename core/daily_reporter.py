"""Daily Reporter module for generating structured daily reports."""

import os
from datetime import datetime


def generate_daily_report(capabilities=None, cycle_count=0, failures=None, insights=None, state_file=None):
    """Generate a daily report from evolution state.

    Args:
        capabilities: List of capability strings.
        cycle_count: Current evolution cycle number.
        failures: List of failure dictionaries with 'description', 'reason', 'resolution'.
        insights: List of insight strings.
        state_file: Optional path to a state file to read capabilities and cycle count from.

    Returns:
        The path to the generated report file as a string.
    """
    # If state_file is provided, read state from it
    if state_file and os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state_content = f.read()
        # Simple parsing: assume first line is cycle count, rest are capabilities
        lines = state_content.strip().split('\n')
        if lines:
            try:
                cycle_count = int(lines[0].strip())
            except ValueError:
                cycle_count = 0
            capabilities = lines[1:] if len(lines) > 1 else []
    else:
        capabilities = capabilities or []
        cycle_count = cycle_count or 0

    failures = failures or []
    insights = insights or []

    today = datetime.now().strftime("%Y-%m-%d")
    report_dir = os.path.join("reports", "daily")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"report_{today}.md")

    report_content = _format_report(capabilities, cycle_count, failures, insights)
    with open(report_path, "w") as f:
        f.write(report_content)

    return report_path


def _format_report(capabilities, cycle_count, failures, insights):
    """Format the report content as markdown."""
    lines = []
    lines.append("# Daily Report")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"**Cycle:** {cycle_count}")
    lines.append("")

    # Completed Goals
    lines.append("## Completed Goals")
    today_caps = [cap for cap in capabilities if "today" in cap.lower() or "added" in cap.lower()]
    if today_caps:
        for cap in today_caps:
            lines.append(f"- {cap}")
    elif capabilities:
        for cap in capabilities:
            lines.append(f"- {cap}")
    else:
        lines.append("_No goals completed today._")
    lines.append("")

    # Failure Analysis
    lines.append("## Failure Analysis")
    if failures:
        for failure in failures:
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
    if insights:
        for insight in insights:
            lines.append(f"- {insight}")
    else:
        lines.append("_No new insights today._")
    lines.append("")

    # Next Steps
    lines.append("## Next Steps")
    next_steps = []
    for failure in failures:
        if not failure.get("resolution"):
            next_steps.append(f"Resolve: {failure.get('description', 'Unknown failure')}")
    if capabilities:
        next_steps.append("Continue building on current capabilities.")
    if not next_steps:
        next_steps.append("Continue with current evolution cycle.")
    for step in next_steps:
        lines.append(f"- {step}")
    lines.append("")

    return "\n".join(lines)


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
        return generate_daily_report(
            capabilities=self.capabilities,
            cycle_count=self.cycle_number,
            failures=self.failures,
            insights=self.insights
        )

    def _format_report(self):
        """Format the report content as markdown."""
        return _format_report(self.capabilities, self.cycle_number, self.failures, self.insights)

    def run(self):
        """Run the reporter to generate and display the report."""
        report_path = self.generate_report()
        print(f"Report generated at: {report_path}")
        with open(report_path, "r") as f:
            print(f.read())


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