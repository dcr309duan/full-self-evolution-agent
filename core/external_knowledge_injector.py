import os
import json
import re
import requests
from datetime import datetime
from typing import List, Dict, Optional

# Pre-approved list of GitHub repos related to self-evolving systems and meta-learning
PRE_APPROVED_REPOS = [
    "openai/evolution-strategies",
    "google-research/meta-learning",
    "uber-research/poet",
    "openai/neural-mmo",
    "google-research/planet",
    "uber-research/ppga",
]

# Cycle counter file path
CYCLE_COUNTER_FILE = "cycle_counter.json"
KNOWLEDGE_LOG_FILE = "accumulated_knowledge.json"

# Pattern extraction patterns
PATTERN_PATTERNS = [
    r"(?:pattern|technique|method|approach|strategy)\s*[:;]\s*([A-Za-z0-9_\-\s]+)",
    r"(?:novel|new|innovative)\s+(?:pattern|technique|method|approach)\s*[:;]?\s*([A-Za-z0-9_\-\s]+)",
    r"(?:reward|loss|objective)\s*(?:shaping|engineering|design|function)\s*[:;]?\s*([A-Za-z0-9_\-\s]+)",
]

class ExternalKnowledgeInjector:
    def __init__(self, cycle_interval: int = 20):
        self.cycle_interval = cycle_interval
        self.cycle_counter = self._load_cycle_counter()
        self.accumulated_knowledge = self._load_accumulated_knowledge()

    def _load_cycle_counter(self) -> int:
        if os.path.exists(CYCLE_COUNTER_FILE):
            with open(CYCLE_COUNTER_FILE, "r") as f:
                data = json.load(f)
                return data.get("cycle_count", 0)
        return 0

    def _save_cycle_counter(self):
        with open(CYCLE_COUNTER_FILE, "w") as f:
            json.dump({"cycle_count": self.cycle_counter}, f)

    def _load_accumulated_knowledge(self) -> List[Dict]:
        if os.path.exists(KNOWLEDGE_LOG_FILE):
            with open(KNOWLEDGE_LOG_FILE, "r") as f:
                return json.load(f)
        return []

    def _save_accumulated_knowledge(self):
        with open(KNOWLEDGE_LOG_FILE, "w") as f:
            json.dump(self.accumulated_knowledge, f, indent=2)

    def _fetch_readme(self, repo_full_name: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{repo_full_name}/readme"
        try:
            response = requests.get(url, headers={"Accept": "application/vnd.github.v3.raw"})
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"Error fetching README for {repo_full_name}: {e}")
        return None

    def _fetch_recent_commits(self, repo_full_name: str, count: int = 5) -> List[str]:
        url = f"https://api.github.com/repos/{repo_full_name}/commits?per_page={count}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                commits = response.json()
                return [commit.get("commit", {}).get("message", "") for commit in commits]
        except Exception as e:
            print(f"Error fetching commits for {repo_full_name}: {e}")
        return []

    def _extract_patterns(self, text: str) -> List[str]:
        patterns_found = []
        for pattern in PATTERN_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            patterns_found.extend([match.strip() for match in matches if match.strip()])
        return list(set(patterns_found))

    def _generate_goal(self, repo_name: str, pattern: str) -> str:
        # Generate a goal to integrate the pattern
        goal_templates = [
            f"Add a {pattern.lower()} module based on pattern from {repo_name}",
            f"Implement {pattern.lower()} technique inspired by {repo_name}",
            f"Integrate {pattern.lower()} approach from {repo_name} into the system",
            f"Create a reward-shaping module based on {pattern.lower()} from {repo_name}",
        ]
        # Simple selection based on pattern content
        if "reward" in pattern.lower() or "loss" in pattern.lower():
            return goal_templates[3]
        elif "module" in pattern.lower() or "component" in pattern.lower():
            return goal_templates[0]
        else:
            return goal_templates[1]

    def inject_knowledge(self) -> List[Dict]:
        """Run the injection process for all repos."""
        injections = []
        for repo in PRE_APPROVED_REPOS:
            print(f"Processing {repo}...")
            readme = self._fetch_readme(repo)
            commits = self._fetch_recent_commits(repo)

            # Combine text sources for analysis
            combined_text = ""
            if readme:
                combined_text += readme + "\n"
            for commit_msg in commits:
                combined_text += commit_msg + "\n"

            # Extract patterns
            patterns = self._extract_patterns(combined_text)

            # For each pattern found, generate a goal and log it
            for pattern in patterns[:3]:  # Limit to top 3 patterns per repo
                goal = self._generate_goal(repo, pattern)
                injection = {
                    "repo": repo,
                    "pattern": pattern,
                    "goal": goal,
                    "timestamp": datetime.now().isoformat(),
                    "source": "external_knowledge_injector",
                }
                self.accumulated_knowledge.append(injection)
                injections.append(injection)
                print(f"  Injected pattern '{pattern}' -> Goal: {goal}")

        # Save accumulated knowledge
        self._save_accumulated_knowledge()
        return injections

    def run(self):
        """Main execution logic - runs once per 20 cycles."""
        self.cycle_counter += 1
        if self.cycle_counter % self.cycle_interval == 0:
            print(f"Cycle {self.cycle_counter}: Running external knowledge injection...")
            injections = self.inject_knowledge()
            print(f"Completed injection of {len(injections)} patterns.")
        else:
            print(f"Cycle {self.cycle_counter}: Skipping (next injection at cycle {self.cycle_counter + (self.cycle_interval - self.cycle_counter % self.cycle_interval)})")

        self._save_cycle_counter()

# Example usage
if __name__ == "__main__":
    injector = ExternalKnowledgeInjector(cycle_interval=20)
    injector.run()