"""
api_client_example.py

Reference client script demonstrating how to interact with the API:
- Query capabilities
- Trigger evolution
- Retrieve knowledge

This serves as both documentation and a test harness.
"""

import requests
import json
import sys
from typing import Optional, Dict, Any

# Configuration - adjust these as needed
BASE_URL = "http://localhost:8000/api/v1"
API_KEY = "your-api-key-here"  # Replace with actual API key

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}


def query_capabilities() -> Optional[Dict[str, Any]]:
    """
    Query the API to retrieve a list of available capabilities.
    
    Returns:
        Dictionary with capabilities data or None on failure.
    """
    url = f"{BASE_URL}/capabilities"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        print("=== Capabilities Retrieved ===")
        print(json.dumps(data, indent=2))
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error querying capabilities: {e}", file=sys.stderr)
        return None


def trigger_evolution(prompt: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Trigger an evolution process with a given prompt and optional parameters.
    
    Args:
        prompt: The prompt/input for the evolution.
        params: Optional dictionary of parameters (e.g., temperature, max_tokens).
    
    Returns:
        Dictionary with evolution result or None on failure.
    """
    url = f"{BASE_URL}/evolve"
    payload = {"prompt": prompt}
    if params:
        payload["params"] = params
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        print("=== Evolution Triggered ===")
        print(json.dumps(data, indent=2))
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error triggering evolution: {e}", file=sys.stderr)
        return None


def retrieve_knowledge(query: str, limit: int = 10) -> Optional[Dict[str, Any]]:
    """
    Retrieve knowledge based on a query string.
    
    Args:
        query: The search query.
        limit: Maximum number of results to return.
    
    Returns:
        Dictionary with knowledge results or None on failure.
    """
    url = f"{BASE_URL}/knowledge"
    params = {"query": query, "limit": limit}
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        print("=== Knowledge Retrieved ===")
        print(json.dumps(data, indent=2))
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving knowledge: {e}", file=sys.stderr)
        return None


def run_example_workflow():
    """
    Run a complete example workflow demonstrating all three API interactions.
    This serves as a test harness.
    """
    print("Starting API Client Example Workflow")
    print("=" * 50)
    
    # Step 1: Query capabilities
    print("\n[Step 1] Querying capabilities...")
    caps = query_capabilities()
    if caps is None:
        print("Failed to retrieve capabilities. Aborting workflow.")
        return
    
    # Step 2: Trigger evolution
    print("\n[Step 2] Triggering evolution...")
    evolution_prompt = "Generate a creative solution for optimizing energy consumption in smart homes."
    evolution_params = {"temperature": 0.7, "max_tokens": 200}
    result = trigger_evolution(evolution_prompt, evolution_params)
    if result is None:
        print("Evolution failed. Continuing with remaining steps.")
    
    # Step 3: Retrieve knowledge
    print("\n[Step 3] Retrieving knowledge...")
    knowledge_query = "energy optimization techniques"
    knowledge = retrieve_knowledge(knowledge_query, limit=5)
    if knowledge is None:
        print("Knowledge retrieval failed.")
    
    print("\n" + "=" * 50)
    print("Example workflow completed.")


if __name__ == "__main__":
    # If run directly, execute the example workflow
    run_example_workflow()