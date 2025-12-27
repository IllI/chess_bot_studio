# Multi-Bot System Usage Guide

The Chess Engine Tuner now supports running multiple bot instances with different configurations for A/B testing and parameter comparison.

## Quick Start

### 1. Create Bot Instances

```bash
# Create a standard configuration bot
python main.py --mode multi-bot bot create standard-bot --config-file configs/examples/defensive_bot.json --description "Standard defensive configuration"

# Create an aggressive configuration bot
python main.py --mode multi-bot bot create aggressive-bot --config-file configs/examples/aggressive_bot.json --description "Aggressive attacking configuration"
```

### 2. List Bot Instances

```bash
python main.py --mode multi-bot bot list
```

### 3. Start Bot Instances (requires Lichess tokens)

```bash
# Start bots with their respective Lichess tokens
python main.py --mode multi-bot bot start standard-bot --token YOUR_STANDARD_BOT_TOKEN
python main.py --mode multi-bot bot start aggressive-bot --token YOUR_AGGRESSIVE_BOT_TOKEN
```

### 4. Create A/B Test

```bash
# Create an A/B test between the two configurations
python main.py --mode multi-bot ab-test create standard-bot aggressive-bot --num-games 10 --description "Standard vs Aggressive comparison"
```

### 5. Start A/B Test

```bash
# Start the A/B test (bots must be active)
python main.py --mode multi-bot ab-test start ab_test_standard-bot_vs_aggressive-bot_TIMESTAMP
```

### 6. Monitor Results

```bash
# List all A/B tests
python main.py --mode multi-bot ab-test list

# View detailed results
python main.py --mode multi-bot ab-test results ab_test_standard-bot_vs_aggressive-bot_TIMESTAMP
```

## Key Features

### Multi-Bot Configuration Management
- **Isolated Configurations**: Each bot instance has its own configuration space
- **Configuration Validation**: All parameters are validated against defined bounds
- **Conflict Detection**: Automatic detection of duplicate or similar configurations
- **Configuration Export/Import**: Save and share bot configurations

### A/B Testing Framework
- **Automated Testing**: Create test suites with multiple games between configurations
- **Statistical Analysis**: Automatic calculation of win rates, confidence intervals, and statistical significance
- **Progress Monitoring**: Real-time tracking of test progress and results
- **Fair Testing**: Automatic color alternation to ensure fair comparison

### Inter-Bot Challenges
- **Direct Challenges**: Bots can challenge each other for immediate testing
- **Time Control Management**: Configurable time controls for different test scenarios
- **Game Logging**: Comprehensive logging of all games for analysis

### Performance Comparison
- **Win Rate Analysis**: Detailed win/loss/draw statistics
- **Configuration Correlation**: Link game outcomes to specific parameter settings
- **Historical Tracking**: Maintain history of all configuration changes and their impact

## Configuration Examples

### Defensive Bot Configuration
```json
{
  "piece_values": {
    "pawn": 95,
    "knight": 310,
    "bishop": 320,
    "rook": 490,
    "queen": 880,
    "king": 0
  },
  "mobility_weight": 8.0,
  "pawn_structure_bonus": {
    "passed_pawn": 40,
    "doubled_pawn": -15,
    "isolated_pawn": -10,
    "backward_pawn": -8,
    "connected_pawns": 3
  },
  "king_safety_penalty": {
    "open_file_near_king": -20,
    "weak_pawn_shield": -15,
    "king_in_center": -30,
    "enemy_pieces_near_king": -10
  },
  "search_depth": 3
}
```

### Aggressive Bot Configuration
```json
{
  "piece_values": {
    "pawn": 110,
    "knight": 330,
    "bishop": 340,
    "rook": 510,
    "queen": 920,
    "king": 0
  },
  "mobility_weight": 15.0,
  "pawn_structure_bonus": {
    "passed_pawn": 60,
    "doubled_pawn": -25,
    "isolated_pawn": -20,
    "backward_pawn": -15,
    "connected_pawns": 8
  },
  "king_safety_penalty": {
    "open_file_near_king": -40,
    "weak_pawn_shield": -30,
    "king_in_center": -50,
    "enemy_pieces_near_king": -20
  },
  "search_depth": 5
}
```

## Educational Benefits

### Parameter Understanding
- **Direct Comparison**: See how different parameter values affect gameplay
- **Statistical Validation**: Understand which changes are statistically significant
- **Iterative Learning**: Test hypotheses about chess evaluation functions

### A/B Testing Methodology
- **Scientific Approach**: Learn proper A/B testing methodology for AI systems
- **Statistical Significance**: Understand confidence intervals and statistical significance
- **Controlled Experiments**: Design fair and unbiased comparison tests

### Chess AI Concepts
- **Evaluation Functions**: Understand how different evaluation components affect play
- **Search Depth**: See the impact of deeper vs. shallower search
- **Playing Styles**: Create bots with distinct playing personalities

## Advanced Usage

### Batch Configuration Updates
```bash
# Update multiple parameters at once
python main.py --mode multi-bot bot update my-bot config_updates.json
```

### Configuration Analysis
```bash
# Check for configuration conflicts
python main.py --mode multi-bot bot conflicts

# Export configuration for sharing
python main.py --mode multi-bot bot export my-bot my-bot-config.json
```

### Custom Time Controls
```bash
# Create A/B test with custom time control
python main.py --mode multi-bot ab-test create bot1 bot2 --time-control '{"limit": 180, "increment": 2}' --num-games 20
```

## Requirements

- Python 3.7+
- Lichess bot accounts (one per bot instance)
- Valid Lichess API tokens
- Network connection for online play

## Troubleshooting

### Common Issues
1. **Bot Creation Fails**: Check configuration file format and parameter bounds
2. **Bot Won't Start**: Verify Lichess token is valid and account is a bot account
3. **A/B Test Fails**: Ensure both bots are active before starting test
4. **Configuration Conflicts**: Use conflict detection to identify duplicate configurations

### Logging
All operations are logged with detailed information. Check the console output for error messages and debugging information.