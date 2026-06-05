"""Evolution status reporter - generates human-readable reports and live dashboard."""
import json
import os
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROJECT_ROOT, MEMORY_DIR, LOGS_DIR
from core.memory import get_evolution_state, get_knowledge_base, get_goals


def generate_status_report():
    """Generate a comprehensive markdown status report."""
    state = get_evolution_state()
    kb = get_knowledge_base()
    goals = get_goals()

    cycle = state.get("cycle_count", 0)
    gen = state.get("current_generation", 1)
    caps = state.get("capabilities", [])
    history = state.get("history", [])
    status = state.get("status", "unknown")
    last_time = state.get("last_evolution_time")

    recent_history = history[-20:]
    recent_successes = sum(1 for h in recent_history if h.get("success"))
    recent_total = len(recent_history)
    success_rate = (recent_successes / recent_total * 100) if recent_total > 0 else 0

    total_successes = sum(1 for h in history if h.get("success"))
    total_rate = (total_successes / len(history) * 100) if history else 0

    insights = kb.get("insights", [])
    strategies = kb.get("successful_strategies", [])
    failures = kb.get("failed_approaches", [])

    pending_goals = [g for g in goals.get("sub_goals", []) if g["status"] == "pending"]
    completed_goals = goals.get("completed_goals", [])

    last_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_time)) if last_time else "N/A"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    uptime_cycles_per_hour = 0
    if len(history) >= 2:
        time_span = history[-1].get("timestamp", 0) - history[0].get("timestamp", 0)
        if time_span > 0:
            uptime_cycles_per_hour = len(history) / (time_span / 3600)

    report = f"""# Self-Evolution Agent - Status Report

> Generated: {now_str}

## Overview

| Metric | Value |
|--------|-------|
| Status | **{status}** |
| Current Cycle | {cycle} |
| Generation | {gen} |
| Last Activity | {last_time_str} |
| Speed | ~{uptime_cycles_per_hour:.1f} cycles/hour |

## Performance

| Metric | Value |
|--------|-------|
| Total Success Rate | {total_rate:.1f}% ({total_successes}/{len(history)}) |
| Recent Success Rate (last 20) | {success_rate:.1f}% ({recent_successes}/{recent_total}) |
| Capabilities Developed | {len(caps)} |
| Goals Completed | {len(completed_goals)} |
| Goals Pending | {len(pending_goals)} |

## Capabilities Acquired

"""
    for i, cap in enumerate(caps, 1):
        report += f"{i}. {cap}\n"

    if not caps:
        report += "_None yet_\n"

    report += f"""
## Current Goals (Pending)

"""
    for g in pending_goals[:10]:
        priority = g.get("priority", "?")
        report += f"- [{priority}/10] {g['description']}\n"

    if not pending_goals:
        report += "_No pending goals - will generate new ones_\n"

    report += f"""
## Completed Goals

"""
    for g in completed_goals[-10:]:
        completed_at = time.strftime("%m-%d %H:%M", time.localtime(g.get("completed_at", 0))) if g.get("completed_at") else "?"
        report += f"- ~~{g['description']}~~ ({completed_at})\n"

    if not completed_goals:
        report += "_None yet_\n"

    report += f"""
## Knowledge Base

| Category | Count |
|----------|-------|
| Insights | {len(insights)} |
| Successful Strategies | {len(strategies)} |
| Failed Approaches | {len(failures)} |

### Recent Insights

"""
    for ins in insights[-5:]:
        ts = time.strftime("%m-%d %H:%M", time.localtime(ins.get("timestamp", 0)))
        report += f"- [{ts}] {ins['content'][:120]}\n"

    report += f"""
## Recent Activity (Last 10 Cycles)

| Cycle | Goal | Result |
|-------|------|--------|
"""
    for h in history[-10:]:
        result_emoji = "SUCCESS" if h.get("success") else "FAILED"
        goal_short = h.get("goal", "?")[:60]
        report += f"| {h.get('cycle', '?')} | {goal_short} | {result_emoji} |\n"

    report += f"""
---
_This report auto-updates every 5 evolution cycles. View live log: `tail -f {LOGS_DIR}/evolution.log`_
"""
    return report


def write_report():
    """Write report to STATUS.md in project root."""
    report = generate_status_report()
    report_path = os.path.join(PROJECT_ROOT, "STATUS.md")
    with open(report_path, 'w') as f:
        f.write(report)
    return report_path


def generate_timeline():
    """Generate a simple timeline view of evolution history."""
    state = get_evolution_state()
    history = state.get("history", [])

    lines = ["# Evolution Timeline\n"]
    current_gen = 1
    for h in history:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(h.get("timestamp", 0)))
        status = "+" if h.get("success") else "-"
        goal = h.get("goal", "unknown")[:80]
        lines.append(f"[{ts}] [{status}] Cycle {h.get('cycle', '?')}: {goal}")

    timeline_path = os.path.join(PROJECT_ROOT, "TIMELINE.md")
    with open(timeline_path, 'w') as f:
        f.write('\n'.join(lines))
    return timeline_path


if __name__ == "__main__":
    path = write_report()
    print(f"Report written to: {path}")
    generate_timeline()
    print("Timeline written to: TIMELINE.md")
