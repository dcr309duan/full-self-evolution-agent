"""Core agent module for managing capabilities and cycle tracking."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import os

@dataclass
class Capability:
    """Represents a capability that the agent can perform."""
    name: str
    description: str
    enabled: bool = True
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

class Agent:
    """Main agent class that manages capabilities and tracks evolution cycles."""
    
    def __init__(self, state_file: str = "agent_state.json"):
        self.state_file = state_file
        self.capabilities: List[Capability] = []
        self.cycle_counter: int = 0
        self.implementation_log: List[Dict[str, Any]] = []
        self._load_state()
        
    def _load_state(self) -> None:
        """Load agent state from file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.cycle_counter = data.get('cycle_counter', 0)
                    self.implementation_log = data.get('implementation_log', [])
                    for cap_data in data.get('capabilities', []):
                        self.capabilities.append(Capability(**cap_data))
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load state file: {e}")
                
    def _save_state(self) -> None:
        """Save current agent state to file."""
        state = {
            'cycle_counter': self.cycle_counter,
            'implementation_log': self.implementation_log,
            'capabilities': [
                {
                    'name': cap.name,
                    'description': cap.description,
                    'enabled': cap.enabled,
                    'added_at': cap.added_at,
                    'metadata': cap.metadata
                }
                for cap in self.capabilities
            ]
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
            
    def add_capability(self, name: str, description: str, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a new capability to the agent's capability list.
        
        Args:
            name: The name of the capability
            description: A description of what the capability does
            metadata: Optional metadata associated with the capability
            
        Returns:
            True if the capability was added successfully, False if it already exists
        """
        # Check if capability already exists
        if any(cap.name == name for cap in self.capabilities):
            print(f"Capability '{name}' already exists.")
            return False
            
        capability = Capability(
            name=name,
            description=description,
            metadata=metadata or {}
        )
        self.capabilities.append(capability)
        self._save_state()
        print(f"Added capability: {name}")
        return True
        
    def add_pre_mutation_validation_guard(self) -> bool:
        """Add the 'pre_mutation_validation_guard' capability after successful testing.
        
        This capability ensures that mutations are validated before being applied,
        preventing invalid or harmful changes to the agent's codebase.
        
        Returns:
            True if the capability was added successfully
        """
        success = self.add_capability(
            name="pre_mutation_validation_guard",
            description="Validates mutations before application to prevent invalid changes",
            metadata={
                "type": "guard",
                "validation_level": "strict",
                "applied_after_testing": True
            }
        )
        
        if success:
            self.increment_cycle()
            self.record_implementation("pre_mutation_validation_guard")
            
        return success
        
    def increment_cycle(self) -> int:
        """Increment the cycle counter and return the new value."""
        self.cycle_counter += 1
        self._save_state()
        return self.cycle_counter
        
    def record_implementation(self, capability_name: str) -> None:
        """Record a successful implementation in the log."""
        record = {
            'capability': capability_name,
            'cycle': self.cycle_counter,
            'timestamp': datetime.now().isoformat(),
            'status': 'successful'
        }
        self.implementation_log.append(record)
        self._save_state()
        
    def get_capability(self, name: str) -> Optional[Capability]:
        """Get a capability by name."""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None
        
    def enable_capability(self, name: str) -> bool:
        """Enable a capability by name."""
        cap = self.get_capability(name)
        if cap:
            cap.enabled = True
            self._save_state()
            return True
        return False
        
    def disable_capability(self, name: str) -> bool:
        """Disable a capability by name."""
        cap = self.get_capability(name)
        if cap:
            cap.enabled = False
            self._save_state()
            return True
        return False
        
    def list_capabilities(self, enabled_only: bool = False) -> List[Capability]:
        """List all capabilities, optionally filtering to only enabled ones."""
        if enabled_only:
            return [cap for cap in self.capabilities if cap.enabled]
        return self.capabilities.copy()
        
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the agent."""
        return {
            'cycle_counter': self.cycle_counter,
            'capabilities_count': len(self.capabilities),
            'enabled_capabilities': len([c for c in self.capabilities if c.enabled]),
            'implementations_count': len(self.implementation_log),
            'last_implementation': self.implementation_log[-1] if self.implementation_log else None
        }


# Module-level singleton instance
_agent_instance: Optional[Agent] = None

def get_agent() -> Agent:
    """Get or create the singleton agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = Agent()
    return _agent_instance

def add_pre_mutation_validation_guard() -> bool:
    """Convenience function to add the pre_mutation_validation_guard capability."""
    agent = get_agent()
    return agent.add_pre_mutation_validation_guard()