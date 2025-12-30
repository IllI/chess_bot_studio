"""
Evolutionary Optimizer for Chess Bot Training.
Uses genetic algorithms to discover better weight configurations through self-play.
"""

import random
import json
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime
from copy import deepcopy

from config import DEFAULT_CONFIG
from self_play import SelfPlayEngine, MatchResult, get_self_play_engine


@dataclass
class ConfigGenome:
    """A configuration treated as a genome for evolutionary optimization."""
    id: str
    generation: int
    config: Dict[str, Any]
    fitness: float = 0.0
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    parent_ids: List[str] = field(default_factory=list)
    
    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return (self.wins + 0.5 * self.draws) / self.games_played


@dataclass
class TrainingSession:
    """Tracks the state of a training session."""
    session_id: str
    start_time: str
    status: str  # "running", "paused", "completed", "stopped"
    current_generation: int
    max_generations: int
    population_size: int
    games_per_match: int
    best_config: Optional[Dict[str, Any]]
    best_fitness: float
    generation_history: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'status': self.status,
            'current_generation': self.current_generation,
            'max_generations': self.max_generations,
            'population_size': self.population_size,
            'games_per_match': self.games_per_match,
            'best_config': self.best_config,
            'best_fitness': self.best_fitness,
            'progress_percent': (self.current_generation / self.max_generations * 100) if self.max_generations > 0 else 0,
            'generation_history': self.generation_history[-10:]  # Last 10 generations
        }


class EvolutionaryOptimizer:
    """
    Evolutionary optimizer that uses genetic algorithms to find better configurations.
    
    Process:
    1. Initialize population with random mutations of base config
    2. Evaluate fitness through self-play tournaments
    3. Select fittest individuals
    4. Create next generation through crossover and mutation
    5. Repeat until convergence or max generations
    """
    
    def __init__(self,
                 base_config: Dict[str, Any] = None,
                 population_size: int = 8,
                 mutation_rate: float = 0.3,
                 mutation_strength: float = 0.15,
                 elite_count: int = 2,
                 games_per_match: int = 4):
        """
        Initialize the evolutionary optimizer.
        
        Args:
            base_config: Starting configuration (uses DEFAULT_CONFIG if None)
            population_size: Number of configurations per generation
            mutation_rate: Probability of mutating each parameter
            mutation_strength: How much to mutate (as fraction of value)
            elite_count: Number of top performers to keep unchanged
            games_per_match: Games played between each pair for evaluation
        """
        self.base_config = base_config or deepcopy(DEFAULT_CONFIG)
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.mutation_strength = mutation_strength
        self.elite_count = elite_count
        self.games_per_match = games_per_match
        
        self.population: List[ConfigGenome] = []
        self.generation = 0
        self.best_ever: Optional[ConfigGenome] = None
        self.session: Optional[TrainingSession] = None
        
        self.self_play_engine = get_self_play_engine()
        
        self._is_running = False
        self._stop_requested = False
        self._pause_requested = False
        self._training_thread: Optional[threading.Thread] = None
        
        # Callbacks for UI updates
        self.on_generation_complete: Optional[Callable] = None
        self.on_game_complete: Optional[Callable] = None
    
    def _generate_id(self) -> str:
        """Generate a unique ID for a genome."""
        return f"gen{self.generation}_{random.randint(1000, 9999)}"
    
    def _mutate_value(self, value: float, min_val: float = 0, max_val: float = float('inf')) -> float:
        """Apply Gaussian mutation to a value."""
        if random.random() < self.mutation_rate:
            delta = random.gauss(0, abs(value) * self.mutation_strength)
            new_value = value + delta
            return max(min_val, min(max_val, new_value))
        return value
    
    def mutate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply random mutations to a configuration.
        
        Args:
            config: Configuration to mutate
            
        Returns:
            New mutated configuration
        """
        mutated = deepcopy(config)
        
        # Mutate piece values
        if 'piece_values' in mutated:
            for piece in mutated['piece_values']:
                if piece != 'king':  # Don't mutate king value
                    mutated['piece_values'][piece] = int(self._mutate_value(
                        mutated['piece_values'][piece], min_val=10, max_val=2000
                    ))
        
        # Mutate mobility weight
        if 'mobility_weight' in mutated:
            mutated['mobility_weight'] = round(self._mutate_value(
                mutated['mobility_weight'], min_val=0, max_val=100
            ), 1)
        
        # Mutate king safety (as a scaled value)
        # We'll mutate via a proxy since it's stored as a penalty dict
        
        # Mutate search depth (integer, small range)
        if 'search_depth' in mutated and random.random() < self.mutation_rate * 0.5:
            mutated['search_depth'] = max(2, min(6, mutated['search_depth'] + random.choice([-1, 1])))
        
        return mutated
    
    def crossover(self, parent_a: Dict[str, Any], parent_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create offspring by combining two parent configurations.
        
        Args:
            parent_a: First parent configuration
            parent_b: Second parent configuration
            
        Returns:
            Child configuration with traits from both parents
        """
        child = deepcopy(parent_a)
        
        # Crossover piece values
        if 'piece_values' in child and 'piece_values' in parent_b:
            for piece in child['piece_values']:
                if random.random() < 0.5:
                    child['piece_values'][piece] = parent_b['piece_values'].get(
                        piece, child['piece_values'][piece]
                    )
        
        # Crossover other parameters
        for key in ['mobility_weight', 'search_depth']:
            if key in child and key in parent_b:
                if random.random() < 0.5:
                    child[key] = parent_b[key]
        
        return child
    
    def initialize_population(self) -> None:
        """Initialize the first generation of configurations."""
        self.population = []
        self.generation = 0
        
        # First individual is the base config
        base_genome = ConfigGenome(
            id=self._generate_id(),
            generation=0,
            config=deepcopy(self.base_config)
        )
        self.population.append(base_genome)
        
        # Rest are mutations of the base
        for _ in range(self.population_size - 1):
            mutated_config = self.mutate(self.base_config)
            genome = ConfigGenome(
                id=self._generate_id(),
                generation=0,
                config=mutated_config,
                parent_ids=["base"]
            )
            self.population.append(genome)
    
    def evaluate_population(self) -> None:
        """Evaluate fitness of all individuals through round-robin tournament."""
        n = len(self.population)
        
        # Reset scores
        for genome in self.population:
            genome.fitness = 0.0
            genome.games_played = 0
            genome.wins = 0
            genome.losses = 0
            genome.draws = 0
        
        # Round-robin tournament (each plays against each)
        for i in range(n):
            for j in range(i + 1, n):
                if self._stop_requested:
                    return
                
                while self._pause_requested and not self._stop_requested:
                    time.sleep(0.5)
                
                genome_a = self.population[i]
                genome_b = self.population[j]
                
                # Play match
                result = self.self_play_engine.play_match(
                    genome_a.config,
                    genome_b.config,
                    genome_a.id,
                    genome_b.id,
                    num_games=self.games_per_match
                )
                
                # Update statistics
                genome_a.games_played += result.total_games
                genome_b.games_played += result.total_games
                
                genome_a.wins += result.config_a_wins
                genome_a.losses += result.config_b_wins
                genome_a.draws += result.draws
                
                genome_b.wins += result.config_b_wins
                genome_b.losses += result.config_a_wins
                genome_b.draws += result.draws
                
                # Update fitness (ELO-like scoring)
                genome_a.fitness += result.config_a_score
                genome_b.fitness += result.total_games - result.config_a_score
                
                if self.on_game_complete:
                    self.on_game_complete(result)
    
    def select_parents(self) -> List[ConfigGenome]:
        """Select parents for next generation using tournament selection."""
        # Sort by fitness
        ranked = sorted(self.population, key=lambda g: g.fitness, reverse=True)
        
        # Keep elite unchanged
        elites = ranked[:self.elite_count]
        
        # Tournament selection for rest
        parents = list(elites)
        while len(parents) < self.population_size // 2:
            # Tournament of 3
            contestants = random.sample(self.population, min(3, len(self.population)))
            winner = max(contestants, key=lambda g: g.fitness)
            if winner not in parents:
                parents.append(winner)
        
        return parents
    
    def create_next_generation(self, parents: List[ConfigGenome]) -> None:
        """Create the next generation from selected parents."""
        self.generation += 1
        new_population = []
        
        # Keep elites (but update their generation info)
        for i, elite in enumerate(parents[:self.elite_count]):
            elite_copy = ConfigGenome(
                id=self._generate_id(),
                generation=self.generation,
                config=deepcopy(elite.config),
                parent_ids=[elite.id]
            )
            new_population.append(elite_copy)
        
        # Create rest through crossover and mutation
        while len(new_population) < self.population_size:
            # Select two parents
            parent_a, parent_b = random.sample(parents, 2)
            
            # Crossover
            child_config = self.crossover(parent_a.config, parent_b.config)
            
            # Mutate
            child_config = self.mutate(child_config)
            
            child = ConfigGenome(
                id=self._generate_id(),
                generation=self.generation,
                config=child_config,
                parent_ids=[parent_a.id, parent_b.id]
            )
            new_population.append(child)
        
        self.population = new_population
    
    def run_training(self, max_generations: int = 20) -> ConfigGenome:
        """
        Run the full evolutionary training loop.
        
        Args:
            max_generations: Maximum number of generations to evolve
            
        Returns:
            Best configuration found
        """
        self._is_running = True
        self._stop_requested = False
        
        # Initialize session
        self.session = TrainingSession(
            session_id=f"session_{int(time.time())}",
            start_time=datetime.now().isoformat(),
            status="running",
            current_generation=0,
            max_generations=max_generations,
            population_size=self.population_size,
            games_per_match=self.games_per_match,
            best_config=None,
            best_fitness=0.0,
            generation_history=[]
        )
        
        # Initialize first generation
        self.initialize_population()
        
        for gen in range(max_generations):
            if self._stop_requested:
                self.session.status = "stopped"
                break
            
            while self._pause_requested and not self._stop_requested:
                self.session.status = "paused"
                time.sleep(0.5)
            
            self.session.status = "running"
            self.session.current_generation = gen + 1
            
            # Evaluate current population
            self.evaluate_population()
            
            if self._stop_requested:
                break
            
            # Find best in this generation
            best_this_gen = max(self.population, key=lambda g: g.fitness)
            
            # Update best ever
            if self.best_ever is None or best_this_gen.fitness > self.best_ever.fitness:
                self.best_ever = best_this_gen
                self.session.best_config = best_this_gen.config
                self.session.best_fitness = best_this_gen.fitness
            
            # Record generation stats
            gen_stats = {
                'generation': gen + 1,
                'best_fitness': best_this_gen.fitness,
                'best_win_rate': best_this_gen.win_rate,
                'avg_fitness': sum(g.fitness for g in self.population) / len(self.population),
                'best_config_id': best_this_gen.id
            }
            self.session.generation_history.append(gen_stats)
            
            if self.on_generation_complete:
                self.on_generation_complete(gen + 1, best_this_gen, self.population)
            
            # Create next generation (unless this is the last)
            if gen < max_generations - 1:
                parents = self.select_parents()
                self.create_next_generation(parents)
        
        self.session.status = "completed"
        self._is_running = False
        
        return self.best_ever
    
    def start_async(self, max_generations: int = 20) -> None:
        """Start training in a background thread."""
        if self._is_running:
            return
        
        # Reset state before starting
        self.reset()
        
        def training_wrapper():
            try:
                self.run_training(max_generations)
            except Exception as e:
                print(f"[Evolution] Training error: {e}")
                import traceback
                traceback.print_exc()
                if self.session:
                    self.session.status = "error"
            finally:
                self._is_running = False
        
        self._training_thread = threading.Thread(
            target=training_wrapper,
            daemon=True
        )
        self._training_thread.start()
    
    def pause(self) -> None:
        """Pause training (can be resumed)."""
        self._pause_requested = True
    
    def resume(self) -> None:
        """Resume paused training."""
        self._pause_requested = False
    
    def stop(self) -> None:
        """Stop training completely."""
        self._stop_requested = True
        self._is_running = False
        self.self_play_engine.stop()
    
    def reset(self) -> None:
        """Reset the optimizer state for a fresh start."""
        self._is_running = False
        self._stop_requested = False
        self._pause_requested = False
        self.population = []
        self.generation = 0
        self.best_ever = None
        self.session = None
    
    def get_status(self) -> Dict[str, Any]:
        """Get current training status."""
        return {
            'is_running': self._is_running,
            'is_paused': self._pause_requested,
            'generation': self.generation,
            'population_size': len(self.population),
            'best_ever': asdict(self.best_ever) if self.best_ever else None,
            'session': self.session.to_dict() if self.session else None
        }


# Global optimizer instance
_global_optimizer = None

def get_optimizer() -> EvolutionaryOptimizer:
    """Get or create the global optimizer."""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = EvolutionaryOptimizer()
    return _global_optimizer


if __name__ == "__main__":
    print("Testing Evolutionary Optimizer...")
    
    # Create optimizer with small population for testing
    optimizer = EvolutionaryOptimizer(
        population_size=4,
        games_per_match=2
    )
    
    def on_gen_complete(gen, best, population):
        print(f"\nGeneration {gen} complete:")
        print(f"  Best fitness: {best.fitness:.1f}")
        print(f"  Best win rate: {best.win_rate:.1%}")
    
    optimizer.on_generation_complete = on_gen_complete
    
    print("Running 3 generations (this will take a few minutes)...")
    best = optimizer.run_training(max_generations=3)
    
    print(f"\n=== Training Complete ===")
    print(f"Best configuration found:")
    print(json.dumps(best.config, indent=2))
    print(f"Fitness: {best.fitness:.1f}")
    print(f"Win rate: {best.win_rate:.1%}")
