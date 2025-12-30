"""
Self-Play Engine for Chess Bot Training.
Enables bots to play against each other to discover better weight configurations.
"""

import chess
import random
import time
import json
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from copy import deepcopy

from search import ChessSearchEngine
from config import ChessConfig, DEFAULT_CONFIG


@dataclass
class GameResult:
    """Result of a single self-play game."""
    white_config_id: str
    black_config_id: str
    result: str  # "1-0", "0-1", "1/2-1/2"
    moves: List[str]
    move_count: int
    duration_ms: int
    final_fen: str
    termination: str  # "checkmate", "stalemate", "insufficient", "50-move", "repetition"


@dataclass
class MatchResult:
    """Result of a match (multiple games) between two configs."""
    config_a_id: str
    config_b_id: str
    config_a_wins: int
    config_b_wins: int
    draws: int
    games: List[GameResult]
    
    @property
    def total_games(self) -> int:
        return self.config_a_wins + self.config_b_wins + self.draws
    
    @property
    def config_a_score(self) -> float:
        """Score from config A's perspective (win=1, draw=0.5, loss=0)"""
        return self.config_a_wins + 0.5 * self.draws
    
    @property
    def config_a_win_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.config_a_score / self.total_games


class SelfPlayEngine:
    """Engine for running self-play games between configurations."""
    
    def __init__(self, max_moves: int = 80, time_per_move_ms: int = 50):
        """
        Initialize the self-play engine.
        
        Args:
            max_moves: Maximum moves before declaring draw (reduced for faster training)
            time_per_move_ms: Time limit per move in milliseconds
        """
        self.max_moves = max_moves
        self.time_per_move_ms = time_per_move_ms
        self.games_played = 0
        self.current_game = None
        self.is_running = False
        self._stop_requested = False
    
    def create_engine_from_config(self, config_dict: Dict[str, Any]) -> ChessSearchEngine:
        """Create a search engine from a config dictionary."""
        chess_config = ChessConfig()
        # Apply all config values
        for key, value in config_dict.items():
            chess_config.update_parameter(key, value)
        return ChessSearchEngine(chess_config)
    
    def play_game(self, 
                  white_config: Dict[str, Any], 
                  black_config: Dict[str, Any],
                  white_id: str = "white",
                  black_id: str = "black") -> GameResult:
        """
        Play a single game between two configurations.
        
        Args:
            white_config: Configuration for white
            black_config: Configuration for black
            white_id: Identifier for white config
            black_id: Identifier for black config
            
        Returns:
            GameResult with outcome details
        """
        board = chess.Board()
        moves = []
        start_time = time.time()
        
        # Create engines
        white_engine = self.create_engine_from_config(white_config)
        black_engine = self.create_engine_from_config(black_config)
        
        self.current_game = {
            'board': board,
            'move_count': 0,
            'white_id': white_id,
            'black_id': black_id,
            'fen': board.fen(),
            'last_move': ''
        }
        
        while not board.is_game_over() and len(moves) < self.max_moves:
            if self._stop_requested:
                break
                
            engine = white_engine if board.turn == chess.WHITE else black_engine
            
            try:
                # Get best move with depth 1 for fast training games
                # Depth 1 is enough to differentiate configs by their evaluation
                move = engine.find_best_move(board, depth=1)
                
                if move and move in board.legal_moves:
                    moves.append(move.uci())
                    board.push(move)
                    self.current_game['move_count'] = len(moves)
                    self.current_game['last_move'] = move.uci()
                    self.current_game['fen'] = board.fen()
                else:
                    # If engine fails, pick random legal move
                    legal_moves = list(board.legal_moves)
                    if legal_moves:
                        move = random.choice(legal_moves)
                        moves.append(move.uci())
                        board.push(move)
                        self.current_game['move_count'] = len(moves)
                        self.current_game['last_move'] = move.uci()
                        self.current_game['fen'] = board.fen()
                    else:
                        break
            except Exception as e:
                print(f"[SelfPlay] Engine error: {e}")
                # Pick random move on error
                legal_moves = list(board.legal_moves)
                if legal_moves:
                    move = random.choice(legal_moves)
                    moves.append(move.uci())
                    board.push(move)
                    self.current_game['move_count'] = len(moves)
                    self.current_game['last_move'] = move.uci()
                    self.current_game['fen'] = board.fen()
                else:
                    break
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Determine result
        if board.is_checkmate():
            result = "0-1" if board.turn == chess.WHITE else "1-0"
            termination = "checkmate"
        elif board.is_stalemate():
            result = "1/2-1/2"
            termination = "stalemate"
        elif board.is_insufficient_material():
            result = "1/2-1/2"
            termination = "insufficient"
        elif board.can_claim_fifty_moves():
            result = "1/2-1/2"
            termination = "50-move"
        elif board.can_claim_threefold_repetition():
            result = "1/2-1/2"
            termination = "repetition"
        elif len(moves) >= self.max_moves:
            result = "1/2-1/2"
            termination = "max-moves"
        else:
            result = "1/2-1/2"
            termination = "stopped"
        
        self.games_played += 1
        self.current_game = None
        
        # Log game completion
        print(f"[SelfPlay] Game #{self.games_played}: {white_id} vs {black_id} = {result} ({termination}, {len(moves)} moves)")
        
        return GameResult(
            white_config_id=white_id,
            black_config_id=black_id,
            result=result,
            moves=moves,
            move_count=len(moves),
            duration_ms=duration_ms,
            final_fen=board.fen(),
            termination=termination
        )
    
    def play_match(self,
                   config_a: Dict[str, Any],
                   config_b: Dict[str, Any],
                   config_a_id: str = "A",
                   config_b_id: str = "B",
                   num_games: int = 10) -> MatchResult:
        """
        Play a match (multiple games) between two configurations.
        Each config plays half the games as white and half as black.
        
        Args:
            config_a: First configuration
            config_b: Second configuration
            config_a_id: Identifier for first config
            config_b_id: Identifier for second config
            num_games: Total number of games to play
            
        Returns:
            MatchResult with aggregate statistics
        """
        games = []
        a_wins = 0
        b_wins = 0
        draws = 0
        
        self.is_running = True
        self._stop_requested = False
        
        for i in range(num_games):
            if self._stop_requested:
                break
            
            # Alternate colors
            if i % 2 == 0:
                result = self.play_game(config_a, config_b, config_a_id, config_b_id)
                if result.result == "1-0":
                    a_wins += 1
                elif result.result == "0-1":
                    b_wins += 1
                else:
                    draws += 1
            else:
                result = self.play_game(config_b, config_a, config_b_id, config_a_id)
                if result.result == "1-0":
                    b_wins += 1
                elif result.result == "0-1":
                    a_wins += 1
                else:
                    draws += 1
            
            games.append(result)
        
        self.is_running = False
        
        return MatchResult(
            config_a_id=config_a_id,
            config_b_id=config_b_id,
            config_a_wins=a_wins,
            config_b_wins=b_wins,
            draws=draws,
            games=games
        )
    
    def stop(self):
        """Request stop of current game/match."""
        self._stop_requested = True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        return {
            'is_running': self.is_running,
            'games_played': self.games_played,
            'current_game': self.current_game
        }


# Global self-play engine instance
_self_play_engine = None

def get_self_play_engine() -> SelfPlayEngine:
    """Get or create the global self-play engine."""
    global _self_play_engine
    if _self_play_engine is None:
        _self_play_engine = SelfPlayEngine()
    return _self_play_engine


if __name__ == "__main__":
    # Test self-play
    print("Testing Self-Play Engine...")
    
    engine = SelfPlayEngine(max_moves=50)
    
    config_aggressive = {
        'piece_values': {'pawn': 100, 'knight': 350, 'bishop': 350, 'rook': 525, 'queen': 1000, 'king': 0},
        'mobility_weight': 15.0,
        'search_depth': 3
    }
    
    config_defensive = {
        'piece_values': {'pawn': 100, 'knight': 300, 'bishop': 320, 'rook': 500, 'queen': 900, 'king': 0},
        'mobility_weight': 5.0,
        'search_depth': 3
    }
    
    print("Playing a test match (4 games)...")
    result = engine.play_match(config_aggressive, config_defensive, "aggressive", "defensive", num_games=4)
    
    print(f"\nMatch Result:")
    print(f"  Aggressive wins: {result.config_a_wins}")
    print(f"  Defensive wins: {result.config_b_wins}")
    print(f"  Draws: {result.draws}")
    print(f"  Aggressive win rate: {result.config_a_win_rate:.1%}")
    
    for i, game in enumerate(result.games):
        print(f"\n  Game {i+1}: {game.result} ({game.termination}) in {game.move_count} moves")
