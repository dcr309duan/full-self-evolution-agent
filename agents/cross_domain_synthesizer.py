"""Cross-Domain Knowledge Synthesizer.

Breaks the 'local optimum trap' by importing concepts from unrelated domains
(biology, physics, game theory, distributed systems, economics) and synthesizing
novel evolution strategies that the agent would never discover by introspecting
only its own codebase.

This module provides 'conceptual mutations' — ideas from outside the system's
closed loop that can seed genuinely new architectural directions.
"""

import random
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CrossDomainConcept:
    source_domain: str
    concept_name: str
    description: str
    application_to_evolution: str
    novelty_score: float  # 0-1, how different from current capabilities
    implementation_hint: str


CONCEPT_LIBRARY: List[CrossDomainConcept] = [
    CrossDomainConcept(
        source_domain="immunology",
        concept_name="Clonal Selection with Hypermutation",
        description="Immune system produces many variants of antibodies, "
                    "selecting those that bind to antigens and hypermutating "
                    "the winners for further optimization.",
        application_to_evolution="Instead of mutating one strategy at a time, "
                                 "generate N parallel variants of each mutation "
                                 "strategy, run all against a 'fitness antigen' "
                                 "(test suite), select winners, and hypermutate "
                                 "only those for next generation.",
        novelty_score=0.85,
        implementation_hint="Create a PopulationMutator that maintains a pool "
                           "of 5-10 strategy variants per mutation target, "
                           "applies tournament selection, and uses elevated "
                           "mutation rate on winners.",
    ),
    CrossDomainConcept(
        source_domain="thermodynamics",
        concept_name="Simulated Annealing with Adaptive Cooling",
        description="Accept worse solutions with decreasing probability over time, "
                    "allowing escape from local optima early, then converging later.",
        application_to_evolution="Allow the agent to deliberately accept 'worse' "
                                 "mutations (lower test scores, more complex code) "
                                 "early in evolution cycles to explore new regions "
                                 "of the design space, with acceptance probability "
                                 "decreasing as generation number increases.",
        novelty_score=0.78,
        implementation_hint="Add a temperature parameter T = 1.0 / (1 + gen/50). "
                           "Accept mutations with fitness delta < 0 with probability "
                           "exp(delta/T). This escapes the 100% success rate trap.",
    ),
    CrossDomainConcept(
        source_domain="game_theory",
        concept_name="Nash Equilibrium Detection for Module Interactions",
        description="In multi-agent systems, Nash equilibria represent stable states "
                    "where no agent can unilaterally improve. These can be suboptimal.",
        application_to_evolution="Detect when module interactions reach a Nash equilibrium "
                                 "(no single module change improves the system). "
                                 "Then force coordinated multi-module changes that "
                                 "wouldn't be discovered by single-module optimization.",
        novelty_score=0.90,
        implementation_hint="Track per-module fitness contributions. When all modules "
                           "show zero marginal improvement for 3+ cycles, trigger "
                           "a 'coordinated disruption' that simultaneously mutates "
                           "2-3 tightly coupled modules.",
    ),
    CrossDomainConcept(
        source_domain="ecology",
        concept_name="Niche Construction and Ecosystem Engineering",
        description="Organisms modify their own environment, creating new niches "
                    "that enable novel adaptations impossible in the original environment.",
        application_to_evolution="The agent should not just adapt to its current test suite — "
                                 "it should modify its own test suite, create new benchmarks, "
                                 "and introduce environmental pressures that don't yet exist. "
                                 "Evolution of the fitness landscape itself.",
        novelty_score=0.92,
        implementation_hint="Periodically generate new test cases that target weaknesses "
                           "not covered by existing tests. Mutate the test suite alongside "
                           "the codebase. Co-evolve code and tests.",
    ),
    CrossDomainConcept(
        source_domain="neuroscience",
        concept_name="Hebbian Learning with Synaptic Pruning",
        description="Neurons that fire together wire together; unused connections "
                    "are pruned. Sparse, efficient representations emerge.",
        application_to_evolution="Track which capabilities are actually used together "
                                 "in successful evolution cycles. Strengthen those connections "
                                 "(merge into combined modules). Prune capabilities that are "
                                 "never co-activated — they're dead weight or badly integrated.",
        novelty_score=0.80,
        implementation_hint="Add co-activation tracking: when goal G uses capabilities "
                           "[A, B, C], increment edge weights A-B, A-C, B-C. After "
                           "N cycles, prune edges below threshold and suggest module "
                           "merges for strong edges.",
    ),
    CrossDomainConcept(
        source_domain="quantum_computing",
        concept_name="Superposition of Strategies",
        description="A quantum system exists in multiple states simultaneously until "
                    "measured (collapsed). Interference between states can amplify "
                    "good solutions.",
        application_to_evolution="Maintain multiple competing evolution strategies in "
                                 "'superposition' — don't commit to one until forced. "
                                 "Let strategies interfere (share partial results). "
                                 "Collapse to the best only when a decision point "
                                 "requires commitment.",
        novelty_score=0.88,
        implementation_hint="For each goal, generate 3 competing plans. Execute first "
                           "step of each in parallel. Use results to update probability "
                           "amplitudes. Collapse to best plan after 2-3 steps.",
    ),
    CrossDomainConcept(
        source_domain="swarm_intelligence",
        concept_name="Stigmergy-Based Coordination",
        description="Ants coordinate through pheromone trails left in the environment, "
                    "not through direct communication. Good paths get reinforced.",
        application_to_evolution="Leave 'pheromone traces' on code regions that led to "
                                 "successful mutations. Future mutations preferentially "
                                 "target high-pheromone regions. Traces decay over time "
                                 "to prevent over-exploitation.",
        novelty_score=0.75,
        implementation_hint="Maintain a heat map of file regions (function-level). "
                           "+1 pheromone on successful mutation location. "
                           "Decay all by 0.9x each cycle. Use as weight when "
                           "selecting mutation targets.",
    ),
    CrossDomainConcept(
        source_domain="economics",
        concept_name="Comparative Advantage and Specialization",
        description="Entities should specialize in what they're relatively best at, "
                    "trading with others for the rest, even if they could do everything.",
        application_to_evolution="Instead of making every module general-purpose, identify "
                                 "each module's comparative advantage and double down. "
                                 "Let the reflection parser ONLY reflect, let the mutation "
                                 "engine ONLY mutate. Remove bloated cross-cutting concerns "
                                 "and create minimal, focused interfaces.",
        novelty_score=0.70,
        implementation_hint="Measure lines-of-code and responsibility overlap between "
                           "modules. If module A does 3 things, split into 3 focused "
                           "modules. If 2 modules overlap >30%, merge the overlap.",
    ),
]


class CrossDomainSynthesizer:
    """Synthesizes novel evolution strategies from cross-domain concepts."""

    def __init__(self, current_capabilities: Optional[List[str]] = None):
        self.current_capabilities = current_capabilities or []
        self.applied_concepts: List[str] = []
        self.synthesis_history: List[Dict[str, Any]] = []

    def get_novel_concepts(self, n: int = 3) -> List[CrossDomainConcept]:
        """Select N concepts most different from current capabilities."""
        available = [
            c for c in CONCEPT_LIBRARY
            if c.concept_name not in self.applied_concepts
        ]
        available.sort(key=lambda c: c.novelty_score, reverse=True)
        return available[:n]

    def synthesize_goal(self, concept: CrossDomainConcept) -> Dict[str, Any]:
        """Transform a cross-domain concept into a concrete evolution goal."""
        goal = {
            "description": (
                f"[{concept.source_domain.upper()}] {concept.application_to_evolution}"
            ),
            "implementation_hint": concept.implementation_hint,
            "source_domain": concept.source_domain,
            "concept_name": concept.concept_name,
            "novelty_score": concept.novelty_score,
            "generated_at": time.time(),
        }

        self.synthesis_history.append(goal)
        self.applied_concepts.append(concept.concept_name)
        return goal

    def inject_novelty(self, goal_queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Inject 1-2 novel cross-domain goals into the goal queue."""
        concepts = self.get_novel_concepts(n=2)
        injected = []

        for concept in concepts:
            goal = self.synthesize_goal(concept)
            injected.append(goal)
            logger.info(
                f"Injected cross-domain goal from {concept.source_domain}: "
                f"{concept.concept_name} (novelty={concept.novelty_score:.2f})"
            )

        insert_positions = sorted(
            random.sample(range(len(goal_queue) + 1), min(len(injected), len(goal_queue) + 1))
        )
        for i, pos in enumerate(insert_positions):
            if i < len(injected):
                goal_queue.insert(pos + i, injected[i])

        return goal_queue

    def evaluate_concept_fitness(
        self, concept_name: str, success: bool
    ) -> None:
        """Update concept effectiveness based on results."""
        for concept in CONCEPT_LIBRARY:
            if concept.concept_name == concept_name:
                if success:
                    concept.novelty_score = min(1.0, concept.novelty_score + 0.05)
                else:
                    concept.novelty_score = max(0.1, concept.novelty_score - 0.1)
                break

    def get_synthesis_report(self) -> Dict[str, Any]:
        """Report on cross-domain synthesis activity."""
        return {
            "total_concepts_available": len(CONCEPT_LIBRARY),
            "concepts_applied": len(self.applied_concepts),
            "domains_explored": list(set(
                c.source_domain for c in CONCEPT_LIBRARY
                if c.concept_name in self.applied_concepts
            )),
            "avg_novelty_score": (
                sum(c.novelty_score for c in CONCEPT_LIBRARY) / len(CONCEPT_LIBRARY)
                if CONCEPT_LIBRARY else 0
            ),
            "history": self.synthesis_history[-10:],
        }
