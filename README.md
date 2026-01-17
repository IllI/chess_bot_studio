# Chess Bot Studio

An interactive learning environment for understanding AI and machine learning concepts through chess engine tuning. Train, tune, and evolve your own chess bot configurations using evolutionary algorithms.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the wizard
python -B main.py --mode wizard

# Open http://localhost:8000 in your browser
```

---

## ⚡ Fast Optimization for Lichess (15-20 min)

Get your bot playing better on Lichess in under 30 minutes:

### Step 1: Start Training
```bash
python -B main.py --mode wizard
```
Open http://localhost:8000 and click the **Train** tab (🧬)

### Step 2: Use These Settings

| Parameter | Setting |
|-----------|---------|
| Generations | **5** |
| Population | **4** |
| Games/Match | **2** |

### Step 3: Train
1. Click **"Start Evolution"**
2. Watch the live chessboard show self-play games
3. Wait 15-20 minutes for training to complete

### Step 4: Apply Results
1. Click **"Apply Best Config"** when training completes
2. Your bot is now optimized!

### Expected Results
- **Fast training (5 gen)**: +50-100 Elo improvement
- **Quality training (15 gen, 1-2 hrs)**: +100-200 Elo
- **Deep training (50 gen, overnight)**: +200-400 Elo

📖 See **[OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)** for detailed instructions and advanced techniques.

---

## Features

### 🧬 Train Tab
- **Evolutionary Training**: Watch configurations compete and evolve through self-play
- **Live Game Visualization**: See chess games being played in real-time
- **Progress Tracking**: Monitor fitness scores and generation progress

### ⚙️ Lab Tab
- **Parameter Tuning**: Adjust piece values, mobility weight, king safety, search depth
- **Save to Model**: Apply tuned parameters to the active bot

### 📚 Academy Tab
- **Learning Resources**: Understand chess engine evaluation
- **ML Concepts**: See how parameter tuning relates to machine learning

### 🧠 Neural Tab
- **Neural Network Visualization**: See how weights flow through layers
- **Backpropagation Demo**: Understand how gradients update weights

---

## How It Works

Chess Bot Studio uses an **evolutionary algorithm** to discover optimal parameters:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Initialize  │ ──▶ │  Evaluate   │ ──▶ │   Select    │
│ Population  │     │ (Self-Play) │     │ (Fitness)   │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                                       │
       │            ┌─────────────┐            │
       └──────────  │  Reproduce  │ ◀──────────┘
                    │  (Crossover │
                    │  + Mutate)  │
                    └─────────────┘
```

Each generation, the best configurations survive and combine to create even stronger offspring.

---

## Config Files

| File | Purpose |
|------|---------|
| `configs/trained_best.json` | Best evolution-trained weights |
| `configs/online_learned.json` | Weights learned from Lichess games |
| `configs/user_profile.json` | Your Lichess token and preferences |

**Priority Order**: Online Learned → Evolution Trained → Default

---

## Online Learning

The bot learns from every Lichess game automatically:

| Outcome | Response |
|---------|----------|
| Win | Reinforce current weights (3%) |
| Win streak | Stronger reinforcement (up to 15%) |
| Loss | Mutate to explore alternatives |
| Loss streak | Stronger mutations to escape |

---

## Other Run Modes

```bash
# Run bot on Lichess
python main.py --mode bot --token YOUR_LICHESS_TOKEN

# Multi-bot management
python main.py --mode multi-bot --help

# A/B test two configs
python multi_bot_cli.py ab-test config1 config2 --games 20
```

---

## Documentation

- **[OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)** - Detailed optimization instructions
- **[TRAINING_SYSTEM_PLAN.md](TRAINING_SYSTEM_PLAN.md)** - Technical training system design
- **[MULTI_BOT_USAGE.md](MULTI_BOT_USAGE.md)** - Multi-bot management guide
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Code architecture overview

---

## Requirements

- Python 3.8+
- `python-chess` library
- Modern web browser

```bash
pip install -r requirements.txt
```

---

## License

MIT
