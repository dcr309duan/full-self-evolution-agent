"""
experiments/radical_mutation_ecosystem_sim.py

A concrete implementation of an ecosystem simulation as a standalone, minimal executable module.
This serves as the first radical mutation candidate.

Defines a simple ecosystem with agents, resources, and environment.
Runs a simulation for N steps.
Outputs statistics on agent survival, resource consumption, and emergent behaviors.
Self-contained with no dependencies beyond standard library.
"""

import random
import math
import sys
from collections import defaultdict
from typing import List, Tuple, Dict, Optional


class Resource:
    """A resource node in the environment."""
    
    def __init__(self, x: float, y: float, initial_amount: float = 100.0):
        self.x = x
        self.y = y
        self.amount = initial_amount
        self.max_amount = initial_amount
        self.regeneration_rate = 0.05  # per step
    
    def regenerate(self):
        """Regenerate resource over time."""
        if self.amount < self.max_amount:
            self.amount = min(self.max_amount, self.amount + self.regeneration_rate)
    
    def consume(self, amount: float) -> float:
        """Consume up to 'amount' of resource. Returns actual amount consumed."""
        consumed = min(amount, self.amount)
        self.amount -= consumed
        return consumed
    
    def distance_to(self, x: float, y: float) -> float:
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2)


class Agent:
    """An agent in the ecosystem."""
    
    def __init__(self, agent_id: int, x: float, y: float, energy: float = 50.0):
        self.agent_id = agent_id
        self.x = x
        self.y = y
        self.energy = energy
        self.max_energy = 100.0
        self.speed = random.uniform(0.5, 2.0)
        self.sense_radius = random.uniform(5.0, 15.0)
        self.consume_efficiency = random.uniform(0.3, 1.0)
        self.reproduction_threshold = 80.0
        self.reproduction_cost = 30.0
        self.mutation_rate = 0.1
        self.age = 0
        self.max_age = random.randint(50, 150)
        self.resource_consumed = 0.0
        self.alive = True
        self.generation = 0
        self.parent_id = None
    
    def move_toward(self, target_x: float, target_y: float, dt: float = 1.0):
        """Move agent toward a target position."""
        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            step = min(self.speed * dt, dist)
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step
    
    def move_random(self, bounds: Tuple[float, float, float, float], dt: float = 1.0):
        """Move agent randomly within bounds."""
        angle = random.uniform(0, 2 * math.pi)
        step = self.speed * dt
        new_x = self.x + math.cos(angle) * step
        new_y = self.y + math.sin(angle) * step
        # Clamp to bounds
        self.x = max(bounds[0], min(bounds[2], new_x))
        self.y = max(bounds[1], min(bounds[3], new_y))
    
    def find_nearest_resource(self, resources: List[Resource]) -> Optional[Resource]:
        """Find the nearest resource within sense radius."""
        nearest = None
        min_dist = self.sense_radius
        for res in resources:
            if res.amount > 0:
                dist = res.distance_to(self.x, self.y)
                if dist < min_dist:
                    min_dist = dist
                    nearest = res
        return nearest
    
    def consume_resource(self, resource: Resource) -> float:
        """Consume from a resource. Returns energy gained."""
        if resource.amount <= 0:
            return 0.0
        # Base consumption proportional to efficiency and resource amount
        base_consume = min(5.0, resource.amount)
        actual_consume = resource.consume(base_consume)
        energy_gain = actual_consume * self.consume_efficiency
        self.energy = min(self.max_energy, self.energy + energy_gain)
        self.resource_consumed += actual_consume
        return energy_gain
    
    def step(self, resources: List[Resource], bounds: Tuple[float, float, float, float], dt: float = 1.0):
        """Perform one simulation step for this agent."""
        if not self.alive:
            return
        
        self.age += 1
        
        # Energy cost for living
        self.energy -= 0.1 * self.speed
        
        # Find and move toward nearest resource
        nearest = self.find_nearest_resource(resources)
        if nearest:
            self.move_toward(nearest.x, nearest.y, dt)
            dist = nearest.distance_to(self.x, self.y)
            if dist < 1.0:
                self.consume_resource(nearest)
        else:
            self.move_random(bounds, dt)
        
        # Check death conditions
        if self.energy <= 0 or self.age >= self.max_age:
            self.alive = False
    
    def can_reproduce(self) -> bool:
        """Check if agent can reproduce."""
        return self.alive and self.energy >= self.reproduction_threshold
    
    def reproduce(self, new_id: int) -> Optional['Agent']:
        """Create a child agent through reproduction."""
        if not self.can_reproduce():
            return None
        
        self.energy -= self.reproduction_cost
        
        # Create child with mutation
        child = Agent(
            agent_id=new_id,
            x=self.x + random.uniform(-2, 2),
            y=self.y + random.uniform(-2, 2),
            energy=self.reproduction_cost * 0.5
        )
        child.parent_id = self.agent_id
        child.generation = self.generation + 1
        
        # Inherit traits with possible mutations
        child.speed = self._mutate_trait(self.speed, 0.2)
        child.sense_radius = self._mutate_trait(self.sense_radius, 0.2)
        child.consume_efficiency = self._mutate_trait(self.consume_efficiency, 0.15)
        child.reproduction_threshold = self._mutate_trait(self.reproduction_threshold, 0.1)
        child.max_age = max(10, int(self._mutate_trait(float(self.max_age), 0.1)))
        
        return child
    
    def _mutate_trait(self, trait: float, rate: float) -> float:
        """Apply mutation to a trait."""
        if random.random() < self.mutation_rate:
            trait *= random.uniform(1.0 - rate, 1.0 + rate)
        return max(0.1, trait)


class Environment:
    """The environment containing resources."""
    
    def __init__(self, width: float = 100.0, height: float = 100.0, num_resources: int = 20):
        self.width = width
        self.height = height
        self.bounds = (0, 0, width, height)
        self.resources = []
        for _ in range(num_resources):
            x = random.uniform(0, width)
            y = random.uniform(0, height)
            amount = random.uniform(50, 150)
            self.resources.append(Resource(x, y, amount))
    
    def step(self):
        """Perform one environment step."""
        for res in self.resources:
            res.regenerate()


class EcosystemSimulation:
    """Main ecosystem simulation."""
    
    def __init__(self, num_agents: int = 30, width: float = 100.0, height: float = 100.0, 
                 num_resources: int = 20):
        self.environment = Environment(width, height, num_resources)
        self.agents: List[Agent] = []
        self.step_count = 0
        self.next_agent_id = 0
        self.history: Dict[int, Dict] = defaultdict(dict)
        
        # Initialize agents
        for i in range(num_agents):
            x = random.uniform(0, width)
            y = random.uniform(0, height)
            agent = Agent(self.next_agent_id, x, y)
            self.agents.append(agent)
            self.next_agent_id += 1
    
    def step(self):
        """Perform one simulation step."""
        self.step_count += 1
        
        # Environment step
        self.environment.step()
        
        # Agent steps
        for agent in self.agents:
            agent.step(self.environment.resources, self.environment.bounds)
        
        # Reproduction
        new_agents = []
        for agent in self.agents:
            if agent.can_reproduce():
                child = agent.reproduce(self.next_agent_id)
                if child:
                    new_agents.append(child)
                    self.next_agent_id += 1
        self.agents.extend(new_agents)
        
        # Remove dead agents
        self.agents = [a for a in self.agents if a.alive]
        
        # Record statistics
        if self.step_count % 10 == 0:
            self._record_stats()
    
    def _record_stats(self):
        """Record current statistics."""
        if not self.agents:
            return
        
        stats = {
            'population': len(self.agents),
            'avg_energy': sum(a.energy for a in self.agents) / len(self.agents),
            'avg_speed': sum(a.speed for a in self.agents) / len(self.agents),
            'avg_sense': sum(a.sense_radius for a in self.agents) / len(self.agents),
            'avg_efficiency': sum(a.consume_efficiency for a in self.agents) / len(self.agents),
            'avg_age': sum(a.age for a in self.agents) / len(self.agents),
            'total_resource_consumed': sum(a.resource_consumed for a in self.agents),
            'max_generation': max(a.generation for a in self.agents),
        }
        self.history[self.step_count] = stats
    
    def run(self, num_steps: int = 200):
        """Run the simulation for a given number of steps."""
        print(f"Starting ecosystem simulation with {len(self.agents)} agents, "
              f"{len(self.environment.resources)} resources")
        print(f"Environment: {self.environment.width}x{self.environment.height}")
        print(f"Running for {num_steps} steps...\n")
        
        for step in range(1, num_steps + 1):
            self.step()
            
            # Progress indicator
            if step % 50 == 0 or step == num_steps:
                alive = len(self.agents)
                print(f"  Step {step:4d}: Population = {alive:4d}, "
                      f"Resources = {sum(r.amount for r in self.environment.resources):.0f}")
        
        print("\nSimulation complete.\n")
        self._print_final_stats()
    
    def _print_final_stats(self):
        """Print final statistics and analysis."""
        if not self.agents:
            print("All agents went extinct.")
            return
        
        print("=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print(f"Final population: {len(self.agents)}")
        print(f"Total steps: {self.step_count}")
        
        # Agent statistics
        speeds = [a.speed for a in self.agents]
        senses = [a.sense_radius for a in self.agents]
        efficiencies = [a.consume_efficiency for a in self.agents]
        ages = [a.age for a in self.agents]
        generations = [a.generation for a in self.agents]
        energies = [a.energy for a in self.agents]
        
        print(f"\nAgent Traits (mean ± std):")
        print(f"  Speed:       {sum(speeds)/len(speeds):.3f} ± {self._std(speeds):.3f}")
        print(f"  Sense radius:{sum(senses)/len(senses):.3f} ± {self._std(senses):.3f}")
        print(f"  Efficiency:  {sum(efficiencies)/len(efficiencies):.3f} ± {self._std(efficiencies):.3f}")
        print(f"  Age:         {sum(ages)/len(ages):.1f} ± {self._std(ages):.1f}")
        print(f"  Energy:      {sum(energies)/len(energies):.1f} ± {self._std(energies):.1f}")
        print(f"  Generation:  {sum(generations)/len(generations):.1f} (max: {max(generations)})")
        
        # Resource statistics
        total_resource = sum(r.amount for r in self.environment.resources)
        total_consumed = sum(a.resource_consumed for a in self.agents)
        print(f"\nResource Statistics:")
        print(f"  Total remaining: {total_resource:.1f}")
        print(f"  Total consumed:  {total_consumed:.1f}")
        
        # Emergent behaviors analysis
        print(f"\nEmergent Behaviors:")
        self._analyze_emergent_behaviors()
        
        # History summary
        if self.history:
            steps = sorted(self.history.keys())
            print(f"\nPopulation over time:")
            for s in steps:
                pop = self.history[s]['population']
                print(f"  Step {s:4d}: {pop:4d} agents")
    
    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    def _analyze_emergent_behaviors(self):
        """Analyze and report emergent behaviors."""
        if len(self.agents) < 2:
            print("  Too few agents to analyze emergent behaviors.")
            return
        
        # Check for specialization
        efficiencies = [a.consume_efficiency for a in self.agents]
        speeds = [a.speed for a in self.agents]
        
        # Coefficient of variation as a measure of diversity
        cv_efficiency = self._std(efficiencies) / (sum(efficiencies) / len(efficiencies)) if efficiencies else 0
        cv_speed = self._std(speeds) / (sum(speeds) / len(speeds)) if speeds else 0
        
        print(f"  Trait diversity (CV):")
        print(f"    Efficiency CV: {cv_efficiency:.3f}")
        print(f"    Speed CV:      {cv_speed:.3f}")
        
        # Check for clustering (spatial analysis)
        if len(self.agents) >= 5:
            # Simple clustering measure: average distance to nearest neighbor
            total_dist = 0.0
            for a in self.agents:
                min_dist = float('inf')
                for b in self.agents:
                    if a.agent_id != b.agent_id:
                        dist = math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
                        if dist < min_dist:
                            min_dist = dist
                total_dist += min_dist
            avg_nn_dist = total_dist / len(self.agents)
            print(f"  Avg nearest neighbor distance: {avg_nn_dist:.2f}")
            
            # Check if agents cluster near resources
            if self.environment.resources:
                avg_dist_to_resource = 0.0
                for a in self.agents:
                    min_dist = min(r.distance_to(a.x, a.y) for r in self.environment.resources)
                    avg_dist_to_resource += min_dist
                avg_dist_to_resource /= len(self.agents)
                print(f"  Avg distance to nearest resource: {avg_dist_to_resource:.2f}")
        
        # Check for reproduction strategy
        if self.history:
            pops = [self.history[s]['population'] for s in sorted(self.history.keys())]
            if len(pops) > 1:
                growth_rates = [(pops[i] - pops[i-1]) / pops[i-1] if pops[i-1] > 0 else 0 
                               for i in range(1, len(pops))]
                avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0
                print(f"  Avg population growth rate: {avg_growth:.4f} per 10 steps")
        
        # Check for extreme traits (possible adaptations)
        extreme_agents = [a for a in self.agents if a.speed > 1.8 or a.consume_efficiency > 0.9]
        if extreme_agents:
            print(f"  Extreme trait agents: {len(extreme_agents)} (potential adaptation)")


def main():
    """Main entry point."""
    # Parse command line arguments
    num_steps = 200
    num_agents = 30
    num_resources = 20
    
    if len(sys.argv) > 1:
        try:
            num_steps = int(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2:
        try:
            num_agents = int(sys.argv[2])
        except ValueError:
            pass
    if len(sys.argv) > 3:
        try:
            num_resources = int(sys.argv[3])
        except ValueError:
            pass
    
    # Run simulation
    sim = EcosystemSimulation(num_agents=num_agents, num_resources=num_resources)
    sim.run(num_steps=num_steps)


if __name__ == "__main__":
    main()