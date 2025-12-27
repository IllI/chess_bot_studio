# Visualization Components

This directory contains visualization tools for the chess engine tuner.

## Components

### Real-time Evaluation Plotting
- `evaluation_plotter.py` - Real-time plotting of evaluation scores during games
- `move_analysis_charts.py` - Charts showing how parameter changes affect move selection
- `performance_dashboard.py` - Web dashboard for monitoring bot performance

### Educational Visualizations
- `parameter_impact_viz.py` - Visual comparison of different parameter sets
- `learning_progress_charts.py` - Progress tracking for students
- `ml_analogy_diagrams.py` - Visual comparisons between traditional and ML approaches

## Features

### Live Game Analysis
- Real-time evaluation score plotting during games
- Move-by-move analysis with parameter contribution breakdown
- Interactive charts showing search tree exploration

### Parameter Comparison
- Side-by-side comparison of different configurations
- A/B testing result visualization
- Performance trend analysis over time

### Educational Tools
- Visual explanation of how parameters affect evaluation
- Interactive parameter tuning with immediate visual feedback
- Comparison diagrams showing traditional vs. neural network approaches

## Usage

```python
from visualization.evaluation_plotter import EvaluationPlotter

plotter = EvaluationPlotter()
plotter.start_game_monitoring("game_id_123")
# Evaluation scores will be plotted in real-time
```

## Dependencies

- matplotlib for static plots
- plotly for interactive visualizations
- dash for web dashboard
- numpy for data processing