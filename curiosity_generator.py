import random
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class Domain(Enum):
    BIOLOGY = "biology"
    LINGUISTICS = "linguistics"
    GAME_DESIGN = "game_design"
    ARCHITECTURE = "architecture"
    MUSIC_THEORY = "music_theory"
    MATHEMATICS = "mathematics"
    PHYSICS = "physics"
    PSYCHOLOGY = "psychology"
    COMPUTER_SCIENCE = "computer_science"
    PHILOSOPHY = "philosophy"
    ART_HISTORY = "art_history"
    ECONOMICS = "economics"
    SOCIOLOGY = "sociology"
    LITERATURE = "literature"
    ENGINEERING = "engineering"
    NEUROSCIENCE = "neuroscience"
    ECOLOGY = "ecology"
    CHEMISTRY = "chemistry"
    ASTRONOMY = "astronomy"
    GEOLOGY = "geology"
    LINGUISTICS_2 = "linguistics_2"
    COGNITIVE_SCIENCE = "cognitive_science"

@dataclass
class CuriosityTask:
    domain: Domain
    task_description: str
    acceptance_criteria: List[str]
    difficulty: int  # 1-5

@dataclass
class Goal:
    task: CuriosityTask
    priority: int
    timestamp: float
    goal_id: str

class CuriosityGenerator:
    """
    Maintains a counter of cycles since last curiosity injection,
    contains a curated list of cross-domain tasks, and injects high-priority
    goals into a goal queue based on least-recently-used domain selection.
    """

    def __init__(self, injection_interval: int = 10):
        self.cycle_counter: int = 0
        self.last_injection_cycle: int = 0
        self.injection_interval: int = injection_interval
        self.domain_last_used: Dict[Domain, float] = defaultdict(lambda: 0.0)
        self.goal_queue: List[Goal] = []
        self._tasks: List[CuriosityTask] = self._initialize_tasks()
        self._used_tasks: set = set()

    def _initialize_tasks(self) -> List[CuriosityTask]:
        """Initialize the curated list of cross-domain tasks."""
        tasks = [
            # Biology
            CuriosityTask(Domain.BIOLOGY, "Model the evolution of antibiotic resistance in a bacterial population using a simple genetic algorithm",
                         ["Simulation runs for at least 100 generations", "Mutation rate is configurable", "Outputs resistance frequency over time"], 3),
            CuriosityTask(Domain.BIOLOGY, "Design a synthetic biological circuit that produces a detectable output in response to two different chemical inputs",
                         ["AND gate logic implemented", "Output is measurable (e.g., fluorescence)", "Circuit diagram and explanation provided"], 4),

            # Linguistics
            CuriosityTask(Domain.LINGUISTICS, "Create a minimal programming language with a grammar inspired by a natural language of your choice",
                         ["Parser implemented in Python", "At least 3 distinct sentence types", "Can execute simple arithmetic expressions"], 4),
            CuriosityTask(Domain.LINGUISTICS, "Analyze the phoneme distribution in a corpus of 1000 English words and identify the most common consonant clusters",
                         ["Corpus loaded from file", "Phoneme transcription using IPA", "Top 10 clusters listed with frequencies"], 2),

            # Game Design
            CuriosityTask(Domain.GAME_DESIGN, "Design a non-violent puzzle game mechanic based on the concept of 'temporal recursion'",
                         ["Mechanic described in detail", "Prototype implemented in Pygame or similar", "At least 3 levels demonstrating the mechanic"], 5),
            CuriosityTask(Domain.GAME_DESIGN, "Create a simple text-based adventure game where the player's choices affect the narrative in a branching tree structure",
                         ["At least 10 distinct endings", "Player can save/load progress", "Story graph is acyclic"], 3),

            # Architecture
            CuriosityTask(Domain.ARCHITECTURE, "Design a parametric facade system that responds to solar angle and wind direction using Grasshopper or Python",
                         ["Algorithm generates facade geometry", "Inputs: latitude, longitude, time of day", "Outputs: shading pattern and ventilation openings"], 4),
            CuriosityTask(Domain.ARCHITECTURE, "Analyze the spatial syntax of a famous building (e.g., Villa Savoye) using graph theory",
                         ["Floor plan converted to graph", "Calculate integration and connectivity values", "Visualization of graph overlayed on plan"], 3),

            # Music Theory
            CuriosityTask(Domain.MUSIC_THEORY, "Implement a harmonic progression generator that follows classical voice-leading rules",
                         ["Generates 4-part chorale style progressions", "Avoids parallel fifths and octaves", "Supports major and minor keys"], 4),
            CuriosityTask(Domain.MUSIC_THEORY, "Create a tool that transcribes a melody from audio (WAV) into MIDI notes using FFT analysis",
                         ["Detects fundamental frequency", "Outputs MIDI file with correct timing", "Handles polyphony up to 2 notes"], 5),

            # Mathematics
            CuriosityTask(Domain.MATHEMATICS, "Visualize the Mandelbrot set with a zoomable interface and color mapping based on iteration count",
                         ["Supports zoom by mouse drag", "Color palette is customizable", "Renders in under 2 seconds for default view"], 3),
            CuriosityTask(Domain.MATHEMATICS, "Prove or disprove that the sum of two irrational numbers can be rational, with a constructive example",
                         ["Proof written in LaTeX", "At least two examples provided", "Includes discussion of algebraic vs transcendental numbers"], 2),

            # Physics
            CuriosityTask(Domain.PHYSICS, "Simulate the double pendulum chaotic system and compute its Lyapunov exponent",
                         ["Animation of pendulum motion", "Lyapunov exponent calculated from trajectory", "Comparison with known values"], 4),
            CuriosityTask(Domain.PHYSICS, "Design a simple experiment to measure the speed of light using a microwave oven and chocolate",
                         ["Procedure described step-by-step", "Expected precision within 10%", "Error analysis included"], 2),

            # Psychology
            CuriosityTask(Domain.PSYCHOLOGY, "Implement a Stroop test in Python with randomized color-word pairs and reaction time measurement",
                         ["Displays color words in incongruent colors", "Records response time and accuracy", "Generates summary statistics"], 3),
            CuriosityTask(Domain.PSYCHOLOGY, "Design a survey to measure the 'curiosity gap' effect in learning new topics",
                         ["Survey has at least 10 questions", "Uses Likert scale", "Includes control for prior knowledge"], 2),

            # Computer Science
            CuriosityTask(Domain.COMPUTER_SCIENCE, "Implement a concurrent web crawler with politeness policy and rate limiting",
                         ["Respects robots.txt", "Configurable max concurrent requests", "Outputs site map as JSON"], 4),
            CuriosityTask(Domain.COMPUTER_SCIENCE, "Create a simple blockchain implementation with proof-of-work and transaction validation",
                         ["Supports mining with adjustable difficulty", "Validates transaction signatures", "Persists chain to disk"], 5),

            # Philosophy
            CuriosityTask(Domain.PHILOSOPHY, "Write a dialogue between a utilitarian and a deontologist about the ethics of autonomous vehicles",
                         ["At least 2000 words", "Each position has at least 3 arguments", "Includes a synthesis or compromise"], 3),
            CuriosityTask(Domain.PHILOSOPHY, "Analyze the 'Chinese Room' argument using a simple NLP chatbot as a case study",
                         ["Chatbot implemented with rule-based responses", "Discussion of intentionality vs syntax", "Conclusion on strong AI"], 4),

            # Art History
            CuriosityTask(Domain.ART_HISTORY, "Create a style transfer algorithm that applies the visual characteristics of a specific art movement (e.g., Cubism) to photographs",
                         ["Uses neural style transfer or hand-crafted filters", "Before/after comparison images", "Explanation of artistic principles used"], 5),
            CuriosityTask(Domain.ART_HISTORY, "Generate a timeline of major art movements from 1400 to 2000 with key artists and works",
                         ["Interactive HTML timeline", "At least 15 movements", "Clickable entries with details"], 2),

            # Economics
            CuriosityTask(Domain.ECONOMICS, "Simulate a simple market economy with agents that have different utility functions and trading strategies",
                         ["At least 3 types of agents", "Market clears each time step", "Visualization of price and quantity over time"], 4),
            CuriosityTask(Domain.ECONOMICS, "Analyze the Gini coefficient of a synthetic income distribution generated by different taxation models",
                         ["Models: flat, progressive, regressive tax", "Calculates Gini for each", "Comparison chart"], 3),

            # Sociology
            CuriosityTask(Domain.SOCIOLOGY, "Model the spread of a meme through a social network using a SIR-like epidemic model",
                         ["Network generated with configurable topology", "Simulation runs for 500 steps", "Visualization of infection curve"], 3),
            CuriosityTask(Domain.SOCIOLOGY, "Design a survey to study the correlation between social media usage and political polarization",
                         ["Survey instrument with 15+ questions", "Includes demographic controls", "Proposed statistical analysis method"], 2),

            # Literature
            CuriosityTask(Domain.LITERATURE, "Generate a short story (1000 words) using a Markov chain trained on the works of a specific author",
                         ["Model trained on at least 3 works", "Output is coherent and grammatically correct", "Author's style is recognizable"], 4),
            CuriosityTask(Domain.LITERATURE, "Analyze the sentiment arc of a novel by chapter using NLP sentiment analysis",
                         ["Sentiment score per chapter", "Plot of sentiment over time", "Comparison with plot structure (Freytag's pyramid)"], 3),

            # Engineering
            CuriosityTask(Domain.ENGINEERING, "Design a PID controller for a simulated inverted pendulum system",
                         ["Simulation in Python with physics engine", "Tuning method (Ziegler-Nichols) implemented", "Stabilization within 5 seconds"], 4),
            CuriosityTask(Domain.ENGINEERING, "Create a finite element analysis (FEA) for a simple beam under load using Python",
                         ["Mesh generation with configurable resolution", "Calculates stress and displacement", "Visualization of deformation"], 5),

            # Neuroscience
            CuriosityTask(Domain.NEUROSCIENCE, "Implement a simple spiking neural network (SNN) using the leaky integrate-and-fire model",
                         ["Network of at least 100 neurons", "Excitatory and inhibitory connections", "Shows spike raster plot"], 4),
            CuriosityTask(Domain.NEUROSCIENCE, "Analyze EEG data from an open dataset to detect alpha wave suppression during cognitive tasks",
                         ["Loads real EEG data", "Applies bandpass filter", "Detects event-related desynchronization"], 3),

            # Ecology
            CuriosityTask(Domain.ECOLOGY, "Model a predator-prey system using Lotka-Volterra equations with stochastic perturbations",
                         ["Deterministic and stochastic versions", "Phase portrait visualization", "Analysis of stability"], 3),
            CuriosityTask(Domain.ECOLOGY, "Design a biodiversity index calculator that uses species abundance data from a simulated ecosystem",
                         ["Calculates Shannon, Simpson, and Berger-Parker indices", "Generates rarefaction curve", "Input from CSV file"], 2),

            # Chemistry
            CuriosityTask(Domain.CHEMISTRY, "Simulate a chemical reaction network using Gillespie's stochastic simulation algorithm",
                         ["Handles at least 5 species and 3 reactions", "Outputs concentration vs time", "Comparison with deterministic ODE solution"], 4),
            CuriosityTask(Domain.CHEMISTRY, "Create a tool to predict molecular geometry using VSEPR theory from a SMILES string",
                         ["Parses SMILES notation", "Determines electron groups", "Outputs 3D coordinates"], 3),

            # Astronomy
            CuriosityTask(Domain.ASTRONOMY, "Calculate the orbital period of an exoplanet using Kepler's third law from simulated radial velocity data",
                         ["Generates synthetic RV data with noise", "Fits a Keplerian orbit", "Reports period and eccentricity"], 3),
            CuriosityTask(Domain.ASTRONOMY, "Visualize the Hertzsprung-Russell diagram from a star catalog and identify main sequence, giants, and white dwarfs",
                         ["Loads real star data (e.g., Hipparcos)", "Color-coded by spectral type", "Interactive plot with hover info"], 2),

            # Geology
            CuriosityTask(Domain.GEOLOGY, "Simulate plate tectonics with a simple cellular automaton that produces mountain ranges and rift valleys",
                         ["Grid-based simulation", "At least 3 plates", "Visualization of elevation map"], 4),
            CuriosityTask(Domain.GEOLOGY, "Analyze earthquake epicenter data to identify seismic gaps and predict future events",
                         ["Uses real USGS data", "Maps epicenters with magnitude", "Identifies gaps using statistical method"], 3),

            # Cognitive Science
            CuriosityTask(Domain.COGNITIVE_SCIENCE, "Implement a simple working memory model (e.g., Baddeley's model) that can remember and recall sequences",
                         ["Phonological loop and visuospatial sketchpad", "Forgetting curve implemented", "Performance matches human data qualitatively"], 4),
            CuriosityTask(Domain.COGNITIVE_SCIENCE, "Create a dual-task experiment to measure cognitive load using reaction time and accuracy",
                         ["Primary task: n-back", "Secondary task: visual search", "Logs performance metrics"], 3),
        ]
        return tasks

    def _select_least_recently_used_domain(self) -> Domain:
        """Select the domain that has been used least recently."""
        current_time = time.time()
        # Find domain with oldest last_used time
        oldest_domain = min(self.domain_last_used, key=lambda d: self.domain_last_used[d])
        # If multiple domains have same last_used time (e.g., never used), pick randomly among them
        candidates = [d for d, t in self.domain_last_used.items() if t == self.domain_last_used[oldest_domain]]
        return random.choice(candidates)

    def _select_task_for_domain(self, domain: Domain) -> Optional[CuriosityTask]:
        """Select a task from the given domain that hasn't been used recently."""
        domain_tasks = [t for t in self._tasks if t.domain == domain and t.task_description not in self._used_tasks]
        if not domain_tasks:
            # Reset used tasks if all have been used
            self._used_tasks.clear()
            domain_tasks = [t for t in self._tasks if t.domain == domain]
        if not domain_tasks:
            return None
        selected = random.choice(domain_tasks)
        self._used_tasks.add(selected.task_description)
        return selected

    def _format_goal(self, task: CuriosityTask) -> Goal:
        """Format the task as a structured goal with clear acceptance criteria."""
        goal_id = f"curiosity_{int(time.time())}_{random.randint(1000,9999)}"
        goal = Goal(
            task=task,
            priority=1,  # High priority
            timestamp=time.time(),
            goal_id=goal_id
        )
        return goal

    def _log_injection(self, goal: Goal):
        """Log the injection event with timestamp, domain, and task description."""
        logger.info(
            f"Curiosity injection at cycle {self.cycle_counter}: "
            f"domain={goal.task.domain.value}, "
            f"task='{goal.task.task_description}', "
            f"goal_id={goal.goal_id}, "
            f"timestamp={goal.timestamp}"
        )

    def inject_curiosity(self) -> Optional[Goal]:
        """
        Main method to inject a curiosity goal if conditions are met.
        Returns the injected Goal or None if no injection occurred.
        """
        self.cycle_counter += 1
        cycles_since_last = self.cycle_counter - self.last_injection_cycle

        if cycles_since_last < self.injection_interval:
            return None

        # Select least-recently-used domain
        domain = self._select_least_recently_used_domain()

        # Select a task from that domain
        task = self._select_task_for_domain(domain)
        if task is None:
            logger.warning(f"No available task for domain {domain.value}")
            return None

        # Format as goal
        goal = self._format_goal(task)

        # Update tracking
        self.domain_last_used[domain] = time.time()
        self.last_injection_cycle = self.cycle_counter

        # Inject into goal queue (high priority)
        self.goal_queue.append(goal)

        # Log the event
        self._log_injection(goal)

        return goal

    def get_pending_goals(self) -> List[Goal]:
        """Return and clear the current goal queue."""
        goals = self.goal_queue.copy()
        self.goal_queue.clear()
        return goals

    def reset(self):
        """Reset the generator state."""
        self.cycle_counter = 0
        self.last_injection_cycle = 0
        self.domain_last_used = defaultdict(lambda: 0.0)
        self.goal_queue.clear()
        self._used_tasks.clear()

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generator = CuriosityGenerator(injection_interval=5)
    for _ in range(20):
        goal = generator.inject_curiosity()
        if goal:
            print(f"Injected goal: {goal.task.task_description[:50]}...")
        else:
            print("No injection this cycle")
        time.sleep(0.1)