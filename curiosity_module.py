import random
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

# Assuming the existence of a task scheduler API with an 'inject_task' function
# This would typically be imported from a shared module
from task_scheduler_api import inject_task

# Domain templates with task descriptions, required capabilities, and success criteria
DOMAIN_TEMPLATES: List[Dict[str, Any]] = [
    {
        "domain": "natural_language_interaction",
        "description": "Engage in a multi-turn conversation to extract user intent and provide coherent responses.",
        "required_capabilities": [],
        "success_criteria": "Achieve at least 3 meaningful exchanges with clear intent recognition."
    },
    {
        "domain": "file_system_manipulation",
        "description": "Navigate the file system, create a temporary directory, write a sample file, and clean up.",
        "required_capabilities": [],
        "success_criteria": "Directory created, file written with correct content, and cleanup completed without errors."
    },
    {
        "domain": "data_analysis",
        "description": "Analyze a provided CSV dataset, compute summary statistics, and generate a simple visualization.",
        "required_capabilities": [],
        "success_criteria": "Statistics computed correctly and visualization saved as PNG."
    },
    {
        "domain": "web_api_integration",
        "description": "Make a GET request to a public API, parse the JSON response, and extract a specific field.",
        "required_capabilities": [],
        "success_criteria": "HTTP 200 response received and target field extracted successfully."
    },
    {
        "domain": "code_generation",
        "description": "Generate a Python function that sorts a list of integers using quicksort and includes unit tests.",
        "required_capabilities": [],
        "success_criteria": "Function passes all provided test cases."
    },
    {
        "domain": "system_monitoring",
        "description": "Collect current CPU and memory usage, log the data, and alert if thresholds are exceeded.",
        "required_capabilities": [],
        "success_criteria": "Data collected and logged; alert triggered if usage > 90%."
    }
]

def generate_exploration_task() -> Dict[str, Any]:
    """
    Randomly select a domain template and generate a concrete exploration task.
    
    Returns:
        dict: Task object with unique ID, domain, description, priority, and success criteria.
    """
    template = random.choice(DOMAIN_TEMPLATES)
    task_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    
    task = {
        "task_id": task_id,
        "domain": template["domain"],
        "description": template["description"],
        "required_capabilities": template["required_capabilities"],
        "success_criteria": template["success_criteria"],
        "priority": "exploration",
        "created_at": timestamp,
        "expected_learning_outcome": f"Explore and learn about {template['domain']} capabilities."
    }
    return task

def inject_exploration_task() -> None:
    """
    Generate and inject an exploration task into the task scheduler queue.
    Logs the injection details.
    """
    task = generate_exploration_task()
    inject_task(task)
    
    # Log the injection
    log_entry = {
        "event": "exploration_task_injected",
        "domain": task["domain"],
        "timestamp": task["created_at"],
        "expected_learning_outcome": task["expected_learning_outcome"]
    }
    print(f"Exploration task injected: {log_entry}")  # Replace with proper logging

def periodic_exploration_injection(cycle_count: int = 1) -> None:
    """
    Perform periodic injection of exploration tasks.
    
    Args:
        cycle_count: Number of tasks to inject in this cycle (default 1).
    """
    for _ in range(cycle_count):
        inject_exploration_task()

# Example usage (uncomment to run)
# if __name__ == "__main__":
#     periodic_exploration_injection()