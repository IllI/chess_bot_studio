"""
Online Learning Module for Chess Bot Studio.
Learns from real Lichess games to improve configuration over time.
"""

import json
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from copy import deepcopy
from dataclasses import dataclass, asdict

from config import DEFAULT_CONFIG, ChessConfig

# Paths for persistence
ONLINE_CONFIG_PATH = Path(__file__).parent / "configs" / "online_learned.json"
GAME_HISTORY_PATH = Path(__file__).parent / "configs" / "game_history.json"


@dataclass
class GameRecord:
    """Record of a played game for learning."""
    game_id: str
    outcome: str  # "win", "loss", "draw"
    our_color: str
    opponent_rating: int
    config_snapshot: Dict[str, Any]
    timestamp: str
    move_count: int


class OnlineLearner:
    """
    Learns from real games to improve configuration.
    
    Uses streak-based reinforcement:
    - Winning streak: Reinforce current config (stronger with longer streaks)
    - Losing streak: Mutate away from current config (stronger with longer streaks)
    - Single win/loss: Small adjustment
    """
    
    def __init__(self, 
                 base_learning_rate: float = 0.03,
                 max_learning_rate: float = 0.15,
                 streak_multiplier: float = 1.5):
        """
        Initialize the online learner.
        
        Args:
            base_learning_rate: Base adjustment rate for single game
            max_learning_rate: Maximum adjustment rate (caps streak effect)
            streak_multiplier: How much each streak game multiplies the rate
        """
        self.base_learning_rate = base_learning_rate
        self.max_learning_rate = max_learning_rate
        self.streak_multiplier = streak_multiplier
        
        self.current_config = self._load_or_create_config()
        self.game_history: List[GameRecord] = self._load_game_history()
        
        # Streak tracking
        self.current_streak = 0  # Positive = wins, Negative = losses
        self.streak_type = None  # "win", "loss", or None
        
        # Stats
        self.wins = 0
        self.losses = 0
        self.draws = 0
        self._load_stats()
    
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load existing online-learned config or start from trained/default."""
        if ONLINE_CONFIG_PATH.exists():
            try:
                with open(ONLINE_CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                print("[OnlineLearner] Loaded online-learned config")
                return data.get('config', deepcopy(DEFAULT_CONFIG))
            except Exception as e:
                print(f"[OnlineLearner] Error loading online config: {e}")
        
        # Fall back to trained config from evolution
        trained_path = Path(__file__).parent / "configs" / "trained_best.json"
        if trained_path.exists():
            try:
                with open(trained_path, 'r') as f:
                    data = json.load(f)
                print("[OnlineLearner] Starting from trained config")
                return data.get('config', deepcopy(DEFAULT_CONFIG))
            except Exception:
                pass
        
        print("[OnlineLearner] Starting from default config")
        return deepcopy(DEFAULT_CONFIG)
    
    def _load_game_history(self) -> List[GameRecord]:
        """Load game history from disk."""
        if not GAME_HISTORY_PATH.exists():
            return []
        
        try:
            with open(GAME_HISTORY_PATH, 'r') as f:
                data = json.load(f)
            return [GameRecord(**g) for g in data.get('games', [])]
        except Exception:
            return []
    
    def _load_stats(self) -> None:
        """Load stats from saved config."""
        if ONLINE_CONFIG_PATH.exists():
            try:
                with open(ONLINE_CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                stats = data.get('stats', {})
                self.wins = stats.get('wins', 0)
                self.losses = stats.get('losses', 0)
                self.draws = stats.get('draws', 0)
                self.current_streak = data.get('current_streak', 0)
                self.streak_type = data.get('streak_type')
            except Exception:
                pass
    
    def _save_config(self) -> None:
        """Save current config to disk."""
        ONLINE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        total_games = self.wins + self.losses + self.draws
        save_data = {
            'config': self.current_config,
            'updated_at': datetime.now().isoformat(),
            'total_games': total_games,
            'win_rate': self.wins / max(1, total_games),
            'current_streak': self.current_streak,
            'streak_type': self.streak_type,
            'stats': {
                'wins': self.wins,
                'losses': self.losses,
                'draws': self.draws
            }
        }
        
        with open(ONLINE_CONFIG_PATH, 'w') as f:
            json.dump(save_data, f, indent=2)
    
    def _save_game_history(self) -> None:
        """Save game history to disk."""
        GAME_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Keep last 100 games
        recent_games = self.game_history[-100:]
        
        save_data = {
            'games': [asdict(g) for g in recent_games],
            'updated_at': datetime.now().isoformat()
        }
        
        with open(GAME_HISTORY_PATH, 'w') as f:
            json.dump(save_data, f, indent=2)
    
    def get_config(self) -> Dict[str, Any]:
        """Get the current learned configuration."""
        return deepcopy(self.current_config)
    
    def _calculate_learning_rate(self, streak_length: int) -> float:
        """Calculate learning rate based on streak length."""
        # Rate increases with streak: base * (multiplier ^ (streak - 1))
        rate = self.base_learning_rate * (self.streak_multiplier ** max(0, streak_length - 1))
        return min(rate, self.max_learning_rate)
    
    def record_game(self, 
                    game_id: str,
                    outcome: str,
                    our_color: str,
                    opponent_rating: int = 0,
                    move_count: int = 0) -> None:
        """
        Record a completed game and immediately learn from it.
        
        Args:
            game_id: Lichess game ID
            outcome: "win", "loss", or "draw"
            our_color: "white" or "black"
            opponent_rating: Opponent's rating
            move_count: Number of moves in the game
        """
        record = GameRecord(
            game_id=game_id,
            outcome=outcome,
            our_color=our_color,
            opponent_rating=opponent_rating,
            config_snapshot=deepcopy(self.current_config),
            timestamp=datetime.now().isoformat(),
            move_count=move_count
        )
        
        self.game_history.append(record)
        
        # Update stats
        if outcome == "win":
            self.wins += 1
        elif outcome == "loss":
            self.losses += 1
        else:
            self.draws += 1
        
        # Update streak
        self._update_streak(outcome)
        
        # Learn from this game immediately
        self._apply_learning(outcome)
        
        # Save everything
        self._save_config()
        self._save_game_history()
        
        streak_info = f" (streak: {abs(self.current_streak)} {self.streak_type}s)" if self.current_streak != 0 else ""
        print(f"[OnlineLearner] {outcome.upper()}{streak_info} - Config updated")
    
    def _update_streak(self, outcome: str) -> None:
        """Update the current streak based on game outcome."""
        if outcome == "win":
            if self.streak_type == "win":
                self.current_streak += 1
            else:
                self.current_streak = 1
                self.streak_type = "win"
        elif outcome == "loss":
            if self.streak_type == "loss":
                self.current_streak += 1
            else:
                self.current_streak = 1
                self.streak_type = "loss"
        else:  # draw
            # Draws break streaks but don't start new ones
            self.current_streak = 0
            self.streak_type = None
    
    def _apply_learning(self, outcome: str) -> None:
        """Apply learning based on game outcome and current streak."""
        learning_rate = self._calculate_learning_rate(self.current_streak)
        
        if outcome == "win":
            # Reinforce current config - small positive adjustments
            self._reinforce_config(learning_rate)
            print(f"[OnlineLearner] Reinforcing config (rate: {learning_rate:.3f})")
        elif outcome == "loss":
            # Mutate away from current config
            self._mutate_config(learning_rate)
            print(f"[OnlineLearner] Mutating config (rate: {learning_rate:.3f})")
        else:  # draw
            # Small exploration on draws
            if random.random() < 0.3:
                self._mutate_config(self.base_learning_rate * 0.5)
                print(f"[OnlineLearner] Small exploration after draw")
    
    def _reinforce_config(self, strength: float) -> None:
        """Reinforce current config with small positive adjustments."""
        if 'piece_values' in self.current_config:
            for piece in self.current_config['piece_values']:
                if piece != 'king' and random.random() < 0.3:
                    current = self.current_config['piece_values'][piece]
                    # Small adjustment toward slightly higher values
                    delta = current * random.uniform(0, strength * 0.3)
                    self.current_config['piece_values'][piece] = int(current + delta)
        
        # Slightly increase mobility weight if winning
        if 'mobility_weight' in self.current_config and random.random() < 0.2:
            current = self.current_config['mobility_weight']
            delta = current * random.uniform(0, strength * 0.2)
            self.current_config['mobility_weight'] = min(100, round(current + delta, 1))
    
    def _mutate_config(self, strength: float) -> None:
        """Mutate config to explore new parameter space."""
        # Mutate piece values
        if 'piece_values' in self.current_config:
            for piece in self.current_config['piece_values']:
                if piece != 'king' and random.random() < 0.5:
                    current = self.current_config['piece_values'][piece]
                    delta = current * random.gauss(0, strength)
                    new_value = max(10, min(2000, int(current + delta)))
                    self.current_config['piece_values'][piece] = new_value
        
        # Mutate mobility weight
        if 'mobility_weight' in self.current_config and random.random() < 0.4:
            current = self.current_config['mobility_weight']
            delta = current * random.gauss(0, strength)
            self.current_config['mobility_weight'] = max(0, min(100, round(current + delta, 1)))
        
        # Mutate king safety
        if 'king_safety_penalty' in self.current_config and random.random() < 0.3:
            for key in self.current_config['king_safety_penalty']:
                if random.random() < 0.5:
                    current = self.current_config['king_safety_penalty'][key]
                    delta = abs(current) * random.gauss(0, strength)
                    self.current_config['king_safety_penalty'][key] = int(min(0, current - abs(delta)))
        
        # Occasionally mutate search depth
        if 'search_depth' in self.current_config and random.random() < 0.1:
            current = self.current_config['search_depth']
            self.current_config['search_depth'] = max(2, min(6, current + random.choice([-1, 1])))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current learning statistics."""
        total = self.wins + self.losses + self.draws
        return {
            'total_games': total,
            'wins': self.wins,
            'losses': self.losses,
            'draws': self.draws,
            'win_rate': self.wins / max(1, total),
            'current_streak': self.current_streak,
            'streak_type': self.streak_type,
            'learning_rate': self._calculate_learning_rate(self.current_streak)
        }
    
    def force_save(self) -> None:
        """Force save current state (call on shutdown)."""
        self._save_config()
        self._save_game_history()


# Global learner instance
_online_learner: Optional[OnlineLearner] = None


def get_online_learner() -> OnlineLearner:
    """Get or create the global online learner."""
    global _online_learner
    if _online_learner is None:
        _online_learner = OnlineLearner()
    return _online_learner
