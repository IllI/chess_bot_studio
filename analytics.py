"""
Logging and analytics module for chess engine performance tracking.

This module provides comprehensive logging for game outcomes, evaluation breakdowns,
search statistics, and performance analytics for parameter tuning.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import chess

# Handle imports for both module and standalone execution
from config import ChessConfig


@dataclass
class EvaluationLog:
    """Log entry for position evaluation breakdown."""
    timestamp: str
    position_fen: str
    total_score: float
    material_score: float
    mobility_score: float
    pawn_structure_score: float
    king_safety_score: float
    turn: str  # 'white' or 'black'
    move_number: int
    config_snapshot: Dict[str, Any]


@dataclass
class SearchLog:
    """Log entry for search algorithm statistics."""
    timestamp: str
    position_fen: str
    search_depth: int
    nodes_evaluated: int
    positions_evaluated: int
    time_elapsed: float
    best_move: str
    best_score: float
    alpha_beta_cutoffs: int
    move_ordering_hits: int
    search_cancelled: bool
    config_snapshot: Dict[str, Any]


@dataclass
class GameLog:
    """Log entry for complete game information."""
    game_id: str
    timestamp: str
    config_id: str
    config_snapshot: Dict[str, Any]
    our_color: str  # 'white' or 'black'
    opponent_name: str
    opponent_rating: int
    time_control: Dict[str, Any]
    outcome: str  # 'win', 'loss', 'draw'
    termination: str  # 'mate', 'resign', 'timeout', 'stalemate', 'draw'
    game_length_moves: int
    game_duration_seconds: float
    final_position_fen: str
    moves_played: List[str]
    evaluation_logs: List[EvaluationLog]
    search_logs: List[SearchLog]
    our_final_rating: Optional[int] = None
    rating_change: Optional[int] = None


class GameLogger:
    """Comprehensive game logging system."""
    
    def __init__(self, log_directory: str = "logs", config: Optional[ChessConfig] = None):
        """
        Initialize the game logger.
        
        Args:
            log_directory: Directory to store log files
            config: Chess configuration instance
        """
        self.log_directory = Path(log_directory)
        self.config = config or ChessConfig()
        self.logger = logging.getLogger("GameLogger")
        
        # Create log directory if it doesn't exist
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize log files
        self.games_log_file = self.log_directory / "games.jsonl"
        self.evaluations_log_file = self.log_directory / "evaluations.jsonl"
        self.search_log_file = self.log_directory / "search.jsonl"
        
        # Current game tracking
        self.current_games: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info(f"GameLogger initialized with log directory: {self.log_directory}")
    
    def start_game_logging(self, game_id: str, our_color: str, opponent_name: str,
                          opponent_rating: int, time_control: Dict[str, Any]) -> None:
        """
        Start logging for a new game.
        
        Args:
            game_id: Unique game identifier
            our_color: Our color in the game ('white' or 'black')
            opponent_name: Opponent's username
            opponent_rating: Opponent's rating
            time_control: Time control settings
        """
        try:
            game_data = {
                'game_id': game_id,
                'start_time': datetime.now(timezone.utc).isoformat(),
                'config_id': self.config.config_id,
                'config_snapshot': self.config.get_current_config(),
                'our_color': our_color,
                'opponent_name': opponent_name,
                'opponent_rating': opponent_rating,
                'time_control': time_control,
                'moves_played': [],
                'evaluation_logs': [],
                'search_logs': [],
                'move_count': 0
            }
            
            self.current_games[game_id] = game_data
            
            self.logger.info(f"Started logging for game {game_id} vs {opponent_name} "
                           f"(rating: {opponent_rating}) as {our_color}")
            
        except Exception as e:
            self.logger.error(f"Error starting game logging: {e}")
    
    def log_evaluation_breakdown(self, game_id: str, position_fen: str, 
                               evaluation_breakdown: Dict[str, float],
                               move_number: int) -> None:
        """
        Log evaluation breakdown for a position.
        
        Args:
            game_id: Game identifier
            position_fen: FEN string of the position
            evaluation_breakdown: Dictionary with evaluation components
            move_number: Current move number
        """
        try:
            if game_id not in self.current_games:
                self.logger.warning(f"Attempted to log evaluation for unknown game {game_id}")
                return
            
            board = chess.Board(position_fen)
            turn = 'white' if board.turn == chess.WHITE else 'black'
            
            eval_log = EvaluationLog(
                timestamp=datetime.now(timezone.utc).isoformat(),
                position_fen=position_fen,
                total_score=evaluation_breakdown.get('total', 0.0),
                material_score=evaluation_breakdown.get('material', 0.0),
                mobility_score=evaluation_breakdown.get('mobility', 0.0),
                pawn_structure_score=evaluation_breakdown.get('pawn_structure', 0.0),
                king_safety_score=evaluation_breakdown.get('king_safety', 0.0),
                turn=turn,
                move_number=move_number,
                config_snapshot=self.config.get_current_config()
            )
            
            # Add to current game logs
            self.current_games[game_id]['evaluation_logs'].append(eval_log)
            
            # Write to evaluation log file
            self._write_log_entry(self.evaluations_log_file, asdict(eval_log))
            
            self.logger.debug(f"Logged evaluation for game {game_id}, move {move_number}: "
                            f"total={eval_log.total_score:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error logging evaluation breakdown: {e}")
    
    def log_search_statistics(self, game_id: str, position_fen: str,
                            search_stats: Dict[str, Any]) -> None:
        """
        Log search algorithm statistics.
        
        Args:
            game_id: Game identifier
            position_fen: FEN string of the position
            search_stats: Dictionary with search statistics
        """
        try:
            if game_id not in self.current_games:
                self.logger.warning(f"Attempted to log search stats for unknown game {game_id}")
                return
            
            search_log = SearchLog(
                timestamp=datetime.now(timezone.utc).isoformat(),
                position_fen=position_fen,
                search_depth=search_stats.get('search_depth_reached', 0),
                nodes_evaluated=search_stats.get('nodes_evaluated', 0),
                positions_evaluated=search_stats.get('positions_evaluated', 0),
                time_elapsed=search_stats.get('time_elapsed', 0.0),
                best_move=search_stats.get('best_move', ''),
                best_score=search_stats.get('best_score', 0.0),
                alpha_beta_cutoffs=search_stats.get('alpha_beta_cutoffs', 0),
                move_ordering_hits=search_stats.get('move_ordering_hits', 0),
                search_cancelled=search_stats.get('search_cancelled', False),
                config_snapshot=self.config.get_current_config()
            )
            
            # Add to current game logs
            self.current_games[game_id]['search_logs'].append(search_log)
            
            # Write to search log file
            self._write_log_entry(self.search_log_file, asdict(search_log))
            
            self.logger.debug(f"Logged search stats for game {game_id}: "
                            f"depth={search_log.search_depth}, nodes={search_log.nodes_evaluated}, "
                            f"time={search_log.time_elapsed:.3f}s")
            
        except Exception as e:
            self.logger.error(f"Error logging search statistics: {e}")
    
    def log_move_played(self, game_id: str, move_uci: str) -> None:
        """
        Log a move that was played in the game.
        
        Args:
            game_id: Game identifier
            move_uci: Move in UCI format
        """
        try:
            if game_id not in self.current_games:
                self.logger.warning(f"Attempted to log move for unknown game {game_id}")
                return
            
            self.current_games[game_id]['moves_played'].append(move_uci)
            self.current_games[game_id]['move_count'] += 1
            
            self.logger.debug(f"Logged move for game {game_id}: {move_uci}")
            
        except Exception as e:
            self.logger.error(f"Error logging move: {e}")
    
    def finish_game_logging(self, game_id: str, outcome: str, termination: str,
                          final_position_fen: str, our_final_rating: Optional[int] = None,
                          rating_change: Optional[int] = None) -> None:
        """
        Finish logging for a completed game.
        
        Args:
            game_id: Game identifier
            outcome: Game outcome ('win', 'loss', 'draw')
            termination: How the game ended ('mate', 'resign', 'timeout', etc.)
            final_position_fen: FEN of the final position
            our_final_rating: Our rating after the game
            rating_change: Change in rating from this game
        """
        try:
            if game_id not in self.current_games:
                self.logger.warning(f"Attempted to finish logging for unknown game {game_id}")
                return
            
            game_data = self.current_games[game_id]
            
            # Calculate game duration
            start_time = datetime.fromisoformat(game_data['start_time'])
            end_time = datetime.now(timezone.utc)
            duration_seconds = (end_time - start_time).total_seconds()
            
            # Create final game log
            game_log = GameLog(
                game_id=game_id,
                timestamp=game_data['start_time'],
                config_id=game_data['config_id'],
                config_snapshot=game_data['config_snapshot'],
                our_color=game_data['our_color'],
                opponent_name=game_data['opponent_name'],
                opponent_rating=game_data['opponent_rating'],
                time_control=game_data['time_control'],
                outcome=outcome,
                termination=termination,
                game_length_moves=len(game_data['moves_played']),
                game_duration_seconds=duration_seconds,
                final_position_fen=final_position_fen,
                moves_played=game_data['moves_played'],
                evaluation_logs=game_data['evaluation_logs'],
                search_logs=game_data['search_logs'],
                our_final_rating=our_final_rating,
                rating_change=rating_change
            )
            
            # Write to games log file
            self._write_log_entry(self.games_log_file, asdict(game_log))
            
            # Clean up current game tracking
            del self.current_games[game_id]
            
            self.logger.info(f"Finished logging for game {game_id}: {outcome} by {termination} "
                           f"in {len(game_data['moves_played'])} moves "
                           f"({duration_seconds:.1f}s duration)")
            
        except Exception as e:
            self.logger.error(f"Error finishing game logging: {e}")
    
    def _write_log_entry(self, log_file: Path, entry: Dict[str, Any]) -> None:
        """
        Write a log entry to a JSONL file.
        
        Args:
            log_file: Path to the log file
            entry: Dictionary to write as JSON
        """
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                json.dump(entry, f, ensure_ascii=False, default=str)
                f.write('\n')
        except Exception as e:
            self.logger.error(f"Error writing to log file {log_file}: {e}")
    
    def get_current_games(self) -> Dict[str, Dict[str, Any]]:
        """Get information about currently tracked games."""
        return self.current_games.copy()
    
    def load_game_logs(self, limit: Optional[int] = None) -> List[GameLog]:
        """
        Load game logs from file.
        
        Args:
            limit: Maximum number of games to load (most recent first)
            
        Returns:
            List of GameLog objects
        """
        try:
            if not self.games_log_file.exists():
                return []
            
            games = []
            with open(self.games_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        game_data = json.loads(line.strip())
                        # Convert nested objects back to dataclasses
                        game_data['evaluation_logs'] = [
                            EvaluationLog(**eval_log) for eval_log in game_data['evaluation_logs']
                        ]
                        game_data['search_logs'] = [
                            SearchLog(**search_log) for search_log in game_data['search_logs']
                        ]
                        games.append(GameLog(**game_data))
                    except (json.JSONDecodeError, TypeError) as e:
                        self.logger.warning(f"Error parsing game log entry: {e}")
            
            # Return most recent games first
            games.reverse()
            
            if limit:
                games = games[:limit]
            
            return games
            
        except Exception as e:
            self.logger.error(f"Error loading game logs: {e}")
            return []
    
    def clear_logs(self, confirm: bool = False) -> bool:
        """
        Clear all log files.
        
        Args:
            confirm: Must be True to actually clear logs
            
        Returns:
            True if logs were cleared, False otherwise
        """
        if not confirm:
            self.logger.warning("clear_logs called without confirmation")
            return False
        
        try:
            for log_file in [self.games_log_file, self.evaluations_log_file, self.search_log_file]:
                if log_file.exists():
                    log_file.unlink()
            
            self.logger.info("All log files cleared")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing logs: {e}")
            return False


# Global logger instance for backward compatibility
_global_logger = GameLogger()

# Backward compatibility functions
def start_game_logging(game_id: str, our_color: str, opponent_name: str,
                      opponent_rating: int, time_control: Dict[str, Any]) -> None:
    """Start logging for a new game using the global logger."""
    _global_logger.start_game_logging(game_id, our_color, opponent_name, 
                                    opponent_rating, time_control)

def log_evaluation_breakdown(game_id: str, position_fen: str, 
                           evaluation_breakdown: Dict[str, float],
                           move_number: int) -> None:
    """Log evaluation breakdown using the global logger."""
    _global_logger.log_evaluation_breakdown(game_id, position_fen, 
                                          evaluation_breakdown, move_number)

def log_search_statistics(game_id: str, position_fen: str,
                        search_stats: Dict[str, Any]) -> None:
    """Log search statistics using the global logger."""
    _global_logger.log_search_statistics(game_id, position_fen, search_stats)

def finish_game_logging(game_id: str, outcome: str, termination: str,
                       final_position_fen: str, our_final_rating: Optional[int] = None,
                       rating_change: Optional[int] = None) -> None:
    """Finish game logging using the global logger."""
    _global_logger.finish_game_logging(game_id, outcome, termination, 
                                     final_position_fen, our_final_rating, rating_change)


if __name__ == "__main__":
    # Test the logging system
    print("Testing GameLogger...")
    
    # Create test logger
    test_logger = GameLogger("test_logs")
    
    # Test game logging
    game_id = "test_game_123"
    test_logger.start_game_logging(
        game_id=game_id,
        our_color="white",
        opponent_name="TestOpponent",
        opponent_rating=1500,
        time_control={"limit": 300, "increment": 3}
    )
    
    # Test evaluation logging
    test_logger.log_evaluation_breakdown(
        game_id=game_id,
        position_fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        evaluation_breakdown={
            "total": 0.0,
            "material": 0.0,
            "mobility": 0.0,
            "pawn_structure": 0.0,
            "king_safety": 0.0
        },
        move_number=1
    )
    
    # Test search logging
    test_logger.log_search_statistics(
        game_id=game_id,
        position_fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        search_stats={
            "search_depth_reached": 4,
            "nodes_evaluated": 1000,
            "positions_evaluated": 500,
            "time_elapsed": 1.5,
            "best_move": "e2e4",
            "best_score": 0.2,
            "alpha_beta_cutoffs": 100,
            "move_ordering_hits": 50,
            "search_cancelled": False
        }
    )
    
    # Test move logging
    test_logger.log_move_played(game_id, "e2e4")
    
    # Test game completion
    test_logger.finish_game_logging(
        game_id=game_id,
        outcome="win",
        termination="mate",
        final_position_fen="rnbqkb1r/pppp1ppp/5n2/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 2 3",
        our_final_rating=1520,
        rating_change=20
    )
    
    # Test loading logs
    games = test_logger.load_game_logs(limit=1)
    if games:
        print(f"Loaded game: {games[0].game_id} - {games[0].outcome}")
    
    print("GameLogger test completed!")


@dataclass
class PerformanceMetrics:
    """Performance metrics for a configuration."""
    config_id: str
    total_games: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    average_game_length: float
    average_game_duration: float
    average_opponent_rating: int
    rating_change_total: int
    rating_change_average: float
    nodes_per_move_average: float
    time_per_move_average: float
    search_depth_average: float


class PerformanceAnalyzer:
    """Performance analysis and comparison tools."""
    
    def __init__(self, log_directory: str = "logs"):
        """
        Initialize the performance analyzer.
        
        Args:
            log_directory: Directory containing log files
        """
        self.log_directory = Path(log_directory)
        self.logger = logging.getLogger("PerformanceAnalyzer")
        
        # Cache for loaded data
        self._games_cache: Optional[List[GameLog]] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 300  # 5 minutes cache TTL
    
    def _load_games(self, force_reload: bool = False) -> List[GameLog]:
        """
        Load games from log files with caching.
        
        Args:
            force_reload: Force reload even if cache is valid
            
        Returns:
            List of GameLog objects
        """
        current_time = time.time()
        
        # Check if cache is valid
        if (not force_reload and 
            self._games_cache is not None and 
            self._cache_timestamp is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._games_cache
        
        # Load games from file
        games_file = self.log_directory / "games.jsonl"
        if not games_file.exists():
            self._games_cache = []
            self._cache_timestamp = current_time
            return []
        
        games = []
        try:
            with open(games_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        game_data = json.loads(line.strip())
                        # Convert nested objects back to dataclasses
                        game_data['evaluation_logs'] = [
                            EvaluationLog(**eval_log) for eval_log in game_data['evaluation_logs']
                        ]
                        game_data['search_logs'] = [
                            SearchLog(**search_log) for search_log in game_data['search_logs']
                        ]
                        games.append(GameLog(**game_data))
                    except (json.JSONDecodeError, TypeError) as e:
                        self.logger.warning(f"Error parsing game log entry: {e}")
            
            # Cache the results
            self._games_cache = games
            self._cache_timestamp = current_time
            
        except Exception as e:
            self.logger.error(f"Error loading games: {e}")
            self._games_cache = []
            self._cache_timestamp = current_time
        
        return self._games_cache
    
    def calculate_performance_metrics(self, config_id: str, 
                                    min_games: int = 1) -> Optional[PerformanceMetrics]:
        """
        Calculate performance metrics for a specific configuration.
        
        Args:
            config_id: Configuration identifier
            min_games: Minimum number of games required for metrics
            
        Returns:
            PerformanceMetrics object or None if insufficient data
        """
        try:
            games = self._load_games()
            config_games = [game for game in games if game.config_id == config_id]
            
            if len(config_games) < min_games:
                self.logger.warning(f"Insufficient games for config {config_id}: "
                                  f"{len(config_games)} < {min_games}")
                return None
            
            # Calculate basic game statistics
            total_games = len(config_games)
            wins = sum(1 for game in config_games if game.outcome == 'win')
            losses = sum(1 for game in config_games if game.outcome == 'loss')
            draws = sum(1 for game in config_games if game.outcome == 'draw')
            
            win_rate = wins / total_games if total_games > 0 else 0.0
            
            # Calculate averages
            total_moves = sum(game.game_length_moves for game in config_games)
            total_duration = sum(game.game_duration_seconds for game in config_games)
            total_opponent_rating = sum(game.opponent_rating for game in config_games)
            
            average_game_length = total_moves / total_games if total_games > 0 else 0.0
            average_game_duration = total_duration / total_games if total_games > 0 else 0.0
            average_opponent_rating = int(total_opponent_rating / total_games) if total_games > 0 else 0
            
            # Calculate rating changes
            rating_changes = [game.rating_change for game in config_games 
                            if game.rating_change is not None]
            rating_change_total = sum(rating_changes) if rating_changes else 0
            rating_change_average = (sum(rating_changes) / len(rating_changes) 
                                   if rating_changes else 0.0)
            
            # Calculate search statistics
            all_search_logs = []
            for game in config_games:
                all_search_logs.extend(game.search_logs)
            
            if all_search_logs:
                nodes_per_move_average = (sum(log.nodes_evaluated for log in all_search_logs) / 
                                        len(all_search_logs))
                time_per_move_average = (sum(log.time_elapsed for log in all_search_logs) / 
                                       len(all_search_logs))
                search_depth_average = (sum(log.search_depth for log in all_search_logs) / 
                                      len(all_search_logs))
            else:
                nodes_per_move_average = 0.0
                time_per_move_average = 0.0
                search_depth_average = 0.0
            
            return PerformanceMetrics(
                config_id=config_id,
                total_games=total_games,
                wins=wins,
                losses=losses,
                draws=draws,
                win_rate=win_rate,
                average_game_length=average_game_length,
                average_game_duration=average_game_duration,
                average_opponent_rating=average_opponent_rating,
                rating_change_total=rating_change_total,
                rating_change_average=rating_change_average,
                nodes_per_move_average=nodes_per_move_average,
                time_per_move_average=time_per_move_average,
                search_depth_average=search_depth_average
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating performance metrics: {e}")
            return None
    
    def compare_configurations(self, config_a: str, config_b: str, 
                             min_games: int = 5) -> Optional[Dict[str, Any]]:
        """
        Compare performance between two configurations.
        
        Args:
            config_a: First configuration ID
            config_b: Second configuration ID
            min_games: Minimum games required for each config
            
        Returns:
            Comparison results dictionary or None if insufficient data
        """
        try:
            metrics_a = self.calculate_performance_metrics(config_a, min_games)
            metrics_b = self.calculate_performance_metrics(config_b, min_games)
            
            if not metrics_a or not metrics_b:
                self.logger.warning(f"Insufficient data for comparison: "
                                  f"config_a={metrics_a is not None}, "
                                  f"config_b={metrics_b is not None}")
                return None
            
            # Calculate differences and statistical significance
            win_rate_diff = metrics_a.win_rate - metrics_b.win_rate
            rating_change_diff = metrics_a.rating_change_average - metrics_b.rating_change_average
            
            # Simple statistical test (more sophisticated tests could be added)
            total_games_a = metrics_a.total_games
            total_games_b = metrics_b.total_games
            
            # Calculate confidence intervals for win rates (approximate)
            import math
            
            def wilson_score_interval(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
                """Calculate Wilson score interval for binomial proportion."""
                if trials == 0:
                    return (0.0, 0.0)
                
                z = 1.96  # 95% confidence
                p = successes / trials
                n = trials
                
                denominator = 1 + z**2 / n
                centre = (p + z**2 / (2*n)) / denominator
                margin = z * math.sqrt((p*(1-p) + z**2/(4*n)) / n) / denominator
                
                return (max(0, centre - margin), min(1, centre + margin))
            
            ci_a = wilson_score_interval(metrics_a.wins, total_games_a)
            ci_b = wilson_score_interval(metrics_b.wins, total_games_b)
            
            # Check if confidence intervals overlap
            significant_difference = ci_a[1] < ci_b[0] or ci_b[1] < ci_a[0]
            
            return {
                'config_a': {
                    'id': config_a,
                    'metrics': asdict(metrics_a),
                    'win_rate_ci': ci_a
                },
                'config_b': {
                    'id': config_b,
                    'metrics': asdict(metrics_b),
                    'win_rate_ci': ci_b
                },
                'comparison': {
                    'win_rate_difference': win_rate_diff,
                    'rating_change_difference': rating_change_diff,
                    'statistically_significant': significant_difference,
                    'better_config': config_a if win_rate_diff > 0 else config_b,
                    'confidence_level': 0.95
                },
                'summary': {
                    'total_games': total_games_a + total_games_b,
                    'games_per_config': {'a': total_games_a, 'b': total_games_b},
                    'recommendation': self._generate_recommendation(metrics_a, metrics_b, significant_difference)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error comparing configurations: {e}")
            return None
    
    def _generate_recommendation(self, metrics_a: PerformanceMetrics, 
                               metrics_b: PerformanceMetrics, 
                               significant: bool) -> str:
        """Generate a recommendation based on comparison results."""
        if not significant:
            return "No statistically significant difference found. More games needed for reliable comparison."
        
        better_config = metrics_a.config_id if metrics_a.win_rate > metrics_b.win_rate else metrics_b.config_id
        better_metrics = metrics_a if metrics_a.win_rate > metrics_b.win_rate else metrics_b
        
        win_rate_pct = better_metrics.win_rate * 100
        
        return (f"Configuration '{better_config}' shows significantly better performance "
                f"with {win_rate_pct:.1f}% win rate. Recommend using this configuration.")
    
    def get_all_configurations(self) -> List[str]:
        """
        Get list of all configuration IDs that have game data.
        
        Returns:
            List of configuration IDs
        """
        try:
            games = self._load_games()
            config_ids = list(set(game.config_id for game in games))
            return sorted(config_ids)
        except Exception as e:
            self.logger.error(f"Error getting configurations: {e}")
            return []
    
    def get_configuration_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics for all configurations.
        
        Returns:
            Dictionary mapping config IDs to summary statistics
        """
        try:
            config_ids = self.get_all_configurations()
            summary = {}
            
            for config_id in config_ids:
                metrics = self.calculate_performance_metrics(config_id, min_games=1)
                if metrics:
                    summary[config_id] = {
                        'total_games': metrics.total_games,
                        'win_rate': metrics.win_rate,
                        'average_opponent_rating': metrics.average_opponent_rating,
                        'rating_change_total': metrics.rating_change_total,
                        'last_updated': datetime.now(timezone.utc).isoformat()
                    }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting configuration summary: {e}")
            return {}
    
    def export_performance_data(self, output_file: str, 
                              config_ids: Optional[List[str]] = None,
                              format: str = 'json') -> bool:
        """
        Export performance data for external analysis.
        
        Args:
            output_file: Path to output file
            config_ids: List of config IDs to export (all if None)
            format: Export format ('json' or 'csv')
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            if config_ids is None:
                config_ids = self.get_all_configurations()
            
            export_data = {}
            
            for config_id in config_ids:
                metrics = self.calculate_performance_metrics(config_id, min_games=1)
                if metrics:
                    export_data[config_id] = asdict(metrics)
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format.lower() == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            
            elif format.lower() == 'csv':
                import csv
                
                if not export_data:
                    self.logger.warning("No data to export")
                    return False
                
                # Get all field names from the first metrics object
                first_metrics = next(iter(export_data.values()))
                fieldnames = list(first_metrics.keys())
                
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for config_id, metrics in export_data.items():
                        writer.writerow(metrics)
            
            else:
                self.logger.error(f"Unsupported export format: {format}")
                return False
            
            self.logger.info(f"Performance data exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting performance data: {e}")
            return False
    
    def run_ab_test_analysis(self, config_a: str, config_b: str, 
                           target_games: int = 50, 
                           significance_level: float = 0.05) -> Dict[str, Any]:
        """
        Run A/B test analysis between two configurations.
        
        Args:
            config_a: First configuration ID
            config_b: Second configuration ID
            target_games: Target number of games for reliable results
            significance_level: Statistical significance level
            
        Returns:
            A/B test analysis results
        """
        try:
            games = self._load_games()
            games_a = [g for g in games if g.config_id == config_a]
            games_b = [g for g in games if g.config_id == config_b]
            
            current_games_a = len(games_a)
            current_games_b = len(games_b)
            
            # Calculate current results
            comparison = self.compare_configurations(config_a, config_b, min_games=1)
            
            # Estimate required sample size for desired power
            # This is a simplified calculation - more sophisticated power analysis could be added
            estimated_effect_size = 0.1  # Assume we want to detect 10% difference in win rate
            
            # Rough sample size calculation (per group)
            import math
            z_alpha = 1.96  # 95% confidence
            z_beta = 0.84   # 80% power
            p = 0.5  # Assume 50% baseline win rate
            
            n_required = (2 * (z_alpha + z_beta)**2 * p * (1-p)) / (estimated_effect_size**2)
            n_required = int(math.ceil(n_required))
            
            return {
                'test_setup': {
                    'config_a': config_a,
                    'config_b': config_b,
                    'target_games_per_config': target_games,
                    'significance_level': significance_level
                },
                'current_status': {
                    'games_a': current_games_a,
                    'games_b': current_games_b,
                    'progress_a': min(1.0, current_games_a / target_games),
                    'progress_b': min(1.0, current_games_b / target_games),
                    'overall_progress': min(1.0, (current_games_a + current_games_b) / (2 * target_games))
                },
                'current_results': comparison,
                'recommendations': {
                    'games_needed_a': max(0, target_games - current_games_a),
                    'games_needed_b': max(0, target_games - current_games_b),
                    'estimated_sample_size': n_required,
                    'test_complete': (current_games_a >= target_games and 
                                    current_games_b >= target_games),
                    'preliminary_winner': (comparison['comparison']['better_config'] 
                                         if comparison else None)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error running A/B test analysis: {e}")
            return {}


# Global analyzer instance for backward compatibility
_global_analyzer = PerformanceAnalyzer()

# Backward compatibility functions
def calculate_performance_metrics(config_id: str, min_games: int = 1) -> Optional[PerformanceMetrics]:
    """Calculate performance metrics using the global analyzer."""
    return _global_analyzer.calculate_performance_metrics(config_id, min_games)

def compare_configurations(config_a: str, config_b: str, min_games: int = 5) -> Optional[Dict[str, Any]]:
    """Compare configurations using the global analyzer."""
    return _global_analyzer.compare_configurations(config_a, config_b, min_games)

def export_performance_data(output_file: str, config_ids: Optional[List[str]] = None,
                          format: str = 'json') -> bool:
    """Export performance data using the global analyzer."""
    return _global_analyzer.export_performance_data(output_file, config_ids, format)


if __name__ == "__main__":
    # Test the performance analysis system
    print("Testing PerformanceAnalyzer...")
    
    # Create test analyzer
    analyzer = PerformanceAnalyzer("test_logs")
    
    # Test configuration summary
    summary = analyzer.get_configuration_summary()
    print(f"Configuration summary: {summary}")
    
    # Test getting all configurations
    configs = analyzer.get_all_configurations()
    print(f"Available configurations: {configs}")
    
    if len(configs) >= 2:
        # Test comparison
        comparison = analyzer.compare_configurations(configs[0], configs[1], min_games=1)
        if comparison:
            print(f"Comparison result: {comparison['comparison']}")
        
        # Test A/B test analysis
        ab_test = analyzer.run_ab_test_analysis(configs[0], configs[1], target_games=10)
        print(f"A/B test status: {ab_test.get('current_status', {})}")
    
    # Test export
    if analyzer.export_performance_data("test_export.json"):
        print("Export successful")
    
    print("PerformanceAnalyzer test completed!")