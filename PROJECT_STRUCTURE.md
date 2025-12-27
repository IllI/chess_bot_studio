# Lichess Chess Tuner - Project Structure

## Overview

The Lichess Chess Tuner is an educational system that teaches chess AI fundamentals through hands-on parameter tuning and live gameplay testing. The project is designed with progressive complexity and includes advanced features for visualization, automation, and educational support.

## Directory Structure

```
lichess-chess-tuner/
├── chess_engine_tuner/          # Core engine implementation
│   ├── config.py                # Configuration management system
│   ├── evaluation.py            # Position evaluation functions
│   ├── search.py                # Search algorithm implementation
│   ├── custom_lichess_bot.py    # Lichess API integration
│   └── analysis.py              # Game analysis and logging
├── configs/                     # Configuration files
│   ├── default.json             # Default balanced configuration
│   ├── examples/                # Example configurations
│   │   ├── aggressive.json      # Aggressive playing style
│   │   └── defensive.json       # Defensive playing style
│   ├── user/                    # User-specific configurations
│   └── experiments/             # A/B testing configurations
├── logs/                        # System logs
├── data/                        # Analytics and performance data
├── visualization/               # Visualization components
│   ├── evaluation_plotter.py    # Real-time evaluation plotting
│   ├── performance_dashboard.py # Web dashboard
│   └── parameter_impact_viz.py  # Parameter comparison tools
├── automation/                  # Automated tuning and learning
│   ├── grid_search.py           # Grid search optimization
│   ├── evolutionary_tuner.py    # Evolutionary algorithms
│   ├── progressive_complexity.py # Learning phase management
│   └── ml_analogy_components.py # ML comparison tools
├── security/                    # Security and sandboxing
│   ├── config_validator.py      # Configuration validation
│   ├── sandbox_runner.py        # Sandboxed execution
│   └── upload_handler.py        # Safe file uploads
├── educational/                 # Educational resources
│   ├── ml_analogy_materials.py  # Traditional vs Neural comparisons
│   ├── progressive_learning.py  # Phase-based learning
│   └── interactive_tutorials.py # Step-by-step guides
└── main.py                      # Main entry point
```

## Core Features

### 1. Configuration Management
- **Class-based system** with validation and bounds checking
- **Real-time parameter updates** without system restart
- **Configuration export/import** with JSON format
- **Change history tracking** for educational analysis
- **Multi-bot support** for A/B testing

### 2. Progressive Learning System
- **Phase 1**: Material + Mobility (basic concepts)
- **Phase 2**: + Pawn Structure + King Safety (positional concepts)
- **Phase 3**: + Piece-Square Tables (advanced evaluation)
- **Phase 4**: Automated Tuning (bridge to ML)

### 3. Visualization and Analytics
- **Real-time evaluation plotting** during games
- **Parameter impact visualization** showing how changes affect play
- **Performance dashboards** with win rates and rating changes
- **A/B testing result comparison** tools
- **Educational diagrams** explaining concepts

### 4. Learning Automation
- **Grid search optimization** for systematic parameter exploration
- **Evolutionary algorithms** for advanced optimization
- **Random search baselines** for comparison
- **Bayesian optimization** for efficient parameter search
- **Automated A/B testing** between configurations

### 5. Security and Safety
- **Configuration-only uploads** (no code execution)
- **Parameter validation** with strict bounds checking
- **Sandboxed execution** with resource limits
- **Safe file handling** with virus scanning
- **Data privacy protection** with anonymization

### 6. Educational Components
- **ML analogy materials** comparing traditional and neural approaches
- **Interactive tutorials** for step-by-step learning
- **Progress tracking** for students
- **Concept visualization** tools
- **Comparison frameworks** between different AI approaches

## Enhanced Learning Flow

### Traditional Approach (Manual Tuning)
1. **Understand Parameters**: Learn what each parameter controls
2. **Manual Experimentation**: Adjust values and observe results
3. **Iterative Improvement**: Refine based on game outcomes
4. **Pattern Recognition**: Identify successful parameter combinations

### Automated Approach (Bridge to ML)
1. **Automated Search**: Let algorithms find optimal parameters
2. **Optimization Comparison**: Compare manual vs automated results
3. **Algorithm Understanding**: Learn how optimization works
4. **ML Connection**: Understand how this relates to neural networks

### Neural Network Analogy
```
Traditional Engine          Neural Network
├── Hand-tuned weights  →   ├── Learned weights
├── Explicit features   →   ├── Learned features
├── Human knowledge     →   ├── Data-driven patterns
└── Manual optimization →   └── Gradient descent
```

## Key Educational Insights

### 1. Parameter Sensitivity
- Small changes can have large effects on gameplay
- Some parameters are more important than others
- Parameter interactions create complex optimization landscapes

### 2. Optimization Challenges
- Local vs global optima in parameter space
- The curse of dimensionality with many parameters
- Why automated methods outperform manual tuning

### 3. Traditional vs Modern AI
- Evolution from hand-crafted to learned features
- The role of self-play in modern chess engines
- How neural networks revolutionized chess AI

### 4. Practical ML Concepts
- Feature engineering vs feature learning
- Optimization algorithms and their trade-offs
- The importance of evaluation metrics and testing

## Usage Examples

### Basic Parameter Tuning
```python
from chess_engine_tuner.config import ChessConfig

config = ChessConfig("my_bot")
config.update_parameter('mobility_weight', 15.0)
config.export_config("configs/user/my_aggressive_bot.json")
```

### Automated Optimization
```python
from automation.evolutionary_tuner import EvolutionaryTuner

tuner = EvolutionaryTuner()
best_params = tuner.optimize(
    generations=50,
    population_size=20,
    target_rating=1600
)
```

### Visualization
```python
from visualization.evaluation_plotter import EvaluationPlotter

plotter = EvaluationPlotter()
plotter.compare_configurations([
    "configs/examples/aggressive.json",
    "configs/examples/defensive.json"
])
```

### Progressive Learning
```python
from educational.progressive_learning import LearningPhaseManager

phase_manager = LearningPhaseManager()
phase_manager.start_phase(1)  # Material + Mobility only
# ... learning activities ...
phase_manager.advance_to_next_phase()
```

This structure provides a comprehensive learning environment that bridges traditional chess AI concepts with modern machine learning approaches, offering both hands-on experience and theoretical understanding.