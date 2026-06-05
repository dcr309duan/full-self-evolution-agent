import json
import threading
import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.scheduler import Scheduler
from core.task import Task

TASK_REGISTRY_PATH = "task_registry.json"

def load_task_registry():
    """Load tasks from task_registry.json."""
    if not os.path.exists(TASK_REGISTRY_PATH):
        print(f"Error: {TASK_REGISTRY_PATH} not found.")
        return []
    with open(TASK_REGISTRY_PATH, "r") as f:
        data = json.load(f)
    return data.get("tasks", [])

def initialize_scheduler(tasks):
    """Initialize Scheduler and add all enabled tasks."""
    scheduler = Scheduler()
    for task_data in tasks:
        if task_data.get("enabled", True):
            task = Task(
                name=task_data["name"],
                action=task_data.get("action", ""),
                interval=task_data.get("interval", 3600),
                params=task_data.get("params", {})
            )
            scheduler.add_task(task)
    return scheduler

def run_scheduler_in_background(scheduler):
    """Run the scheduler in a background thread."""
    def scheduler_loop():
        while True:
            scheduler.tick()
            time.sleep(1)
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    return thread

def handle_command(command, scheduler):
    """Handle stdin commands."""
    parts = command.strip().split()
    if not parts:
        return
    cmd = parts[0].lower()
    if cmd == "list":
        tasks = scheduler.get_tasks()
        if tasks:
            print("Scheduled tasks:")
            for task in tasks:
                print(f"  - {task.name} (interval: {task.interval}s, enabled: {task.enabled})")
        else:
            print("No tasks scheduled.")
    elif cmd == "add" and len(parts) >= 4:
        name = parts[1]
        action = parts[2]
        interval = int(parts[3])
        params = {}
        if len(parts) > 4:
            try:
                params = json.loads(" ".join(parts[4:]))
            except json.JSONDecodeError:
                print("Invalid params JSON. Ignoring.")
        task = Task(name=name, action=action, interval=interval, params=params)
        scheduler.add_task(task)
        print(f"Task '{name}' added.")
    elif cmd == "remove" and len(parts) >= 2:
        name = parts[1]
        if scheduler.remove_task(name):
            print(f"Task '{name}' removed.")
        else:
            print(f"Task '{name}' not found.")
    elif cmd == "stop":
        print("Stopping scheduler daemon...")
        scheduler.stop()
        sys.exit(0)
    else:
        print("Unknown command. Available: list, add <name> <action> <interval> [params], remove <name>, stop")

def main():
    tasks = load_task_registry()
    if not tasks:
        print("No tasks loaded. Exiting.")
        return

    scheduler = initialize_scheduler(tasks)
    run_scheduler_in_background(scheduler)

    print("Scheduler daemon started. Commands: list, add, remove, stop")
    try:
        while True:
            command = input("> ")
            handle_command(command, scheduler)
    except (EOFError, KeyboardInterrupt):
        print("\nShutting down...")
        scheduler.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()