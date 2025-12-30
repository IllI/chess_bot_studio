# Chess Bot Studio

An interactive learning environment for understanding AI and machine learning concepts through chess engine tuning. Train, tune, and evolve your own chess bot configurations using evolutionary algorithms.

## Quick Start

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Installation

1. Clone or download this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the Application

Launch the full interactive experience with a single command:

```bash
python -B main.py --mode wizard
```

This starts:
- **Web UI** at http://localhost:8000 - The main interface for training and tuning
- **API Server** at http://localhost:5050 - Backend for configuration and training control

Open http://localhost:8000 in your browser to begin.

## Features

### Train Tab
- **Evolutionary Training**: Watch configurations compete and evolve through self-play
- **Live Game Visualization**: See games being played in real-time
- **Parameter Guide**: Learn what each parameter does

### Lab Tab
- **Parameter Tuning**: Adjust piece values, mobility weight, king safety, and search depth
- **Save to Model**: Apply your tuned parameters to the active bot

### Academy Tab
- **Learning Resources**: Understand how chess engines evaluate positions
- **ML Concepts**: See how traditional parameter tuning relates to machine learning

## How It Works

Chess Bot Studio uses an **evolutionary algorithm** to discover optimal chess engine parameters:

1. **Initialize**: Create a population of random parameter configurations
2. **Evaluate**: Configurations play chess against each other
3. **Select**: Best performers survive based on win rate
4. **Reproduce**: Winners combine (crossover) and mutate to create the next generation
5. **Repeat**: Each generation gets stronger

This mirrors how neural networks learn - through iterative improvement based on performance feedback.

## Other Run Modes

```bash
# Run a single bot on Lichess
python main.py --mode bot --token YOUR_LICHESS_TOKEN

# Multi-bot management CLI
python main.py --mode multi-bot --help

# Test mode (shows available options)
python main.py --mode test
```

## Project Structure

- `main.py` - Entry point for all modes
- `wizard.py` - Wizard mode launcher (starts UI + API)
- `config_api_server.py` - REST API for the web interface
- `evolution.py` - Evolutionary optimization algorithm
- `self_play.py` - Self-play engine for training games
- `search.py` - Chess move search (minimax with alpha-beta)
- `evaluation.py` - Position evaluation functions
- `config.py` - Configuration management
- `index.html` - Web UI (single-page React app)

## Configuration

User preferences are stored in `configs/user_profile.json`:

```json
{
  "lichess_token": "your_token_here",
  "preferred_bot_id": "aggressive_v1",
  "strategy": "aggressive",
  "ui_port": 8000,
  "api_port": 5050
}
```

## License

MIT
