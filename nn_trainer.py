"""
Neural Network Training Module for Chess Bot Studio.

Handles:
- Collecting training data from games (every move + outcome)
- Training the neural network on collected data
- Self-play for generating training positions
- Hot-reloading weights for live bot updates
"""

import json
import threading
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import chess

from neural_network import ChessNeuralNetwork, MoveRecord, NN_TRAINING_DATA_PATH


@dataclass
class GameTrainingData:
    """Complete training data for one game."""
    game_id: str
    moves: List[Dict[str, Any]]  # List of MoveRecord as dicts
    outcome: str  # 'white_win', 'black_win', 'draw'
    source: str  # 'lichess', 'self_play', 'imported'
    timestamp: str


class NeuralTrainingDataCollector:
    """
    Collects training data from games for neural network training.
    
    Tracks every position and move, then labels them with game outcome
    for supervised learning.
    """
    
    def __init__(self):
        self.current_games: Dict[str, List[MoveRecord]] = {}
        self.completed_games: List[GameTrainingData] = []
        self.lock = threading.Lock()
        
        # Load existing training data
        self._load_training_data()
    
    def start_game(self, game_id: str) -> None:
        """Start tracking a new game."""
        with self.lock:
            self.current_games[game_id] = []
            print(f"[NNTrainer] Started tracking game {game_id}")
    
    def record_move(self, game_id: str, fen: str, move_uci: str, move_number: int) -> None:
        """Record a move for training."""
        with self.lock:
            if game_id not in self.current_games:
                self.current_games[game_id] = []
            
            record = MoveRecord(
                fen=fen,
                move_uci=move_uci,
                game_outcome=0.5,  # Will be updated when game ends
                move_number=move_number,
                game_id=game_id
            )
            self.current_games[game_id].append(record)
    
    def finish_game(self, game_id: str, outcome: str, source: str = 'lichess') -> Optional[GameTrainingData]:
        """
        Finish tracking a game and label all positions with outcome.
        
        Args:
            game_id: Game identifier
            outcome: 'white_win', 'black_win', or 'draw'
            source: Where the game came from
        
        Returns:
            GameTrainingData if game was tracked, None otherwise
        """
        with self.lock:
            if game_id not in self.current_games:
                return None
            
            moves = self.current_games.pop(game_id)
            
            if not moves:
                return None
            
            # Convert outcome to numeric value
            if outcome == 'white_win':
                outcome_value = 1.0
            elif outcome == 'black_win':
                outcome_value = 0.0
            else:
                outcome_value = 0.5
            
            # Label all positions with the game outcome
            for move in moves:
                move.game_outcome = outcome_value
            
            # Create game training data
            game_data = GameTrainingData(
                game_id=game_id,
                moves=[asdict(m) for m in moves],
                outcome=outcome,
                source=source,
                timestamp=datetime.now().isoformat()
            )
            
            self.completed_games.append(game_data)
            
            print(f"[NNTrainer] Finished game {game_id}: {outcome} ({len(moves)} positions)")
            
            return game_data
    
    def get_training_batch(self, batch_size: int = 32) -> List[MoveRecord]:
        """Get a random batch of positions for training."""
        all_moves = []
        
        with self.lock:
            for game in self.completed_games:
                for move_dict in game.moves:
                    all_moves.append(MoveRecord(**move_dict))
        
        if len(all_moves) <= batch_size:
            return all_moves
        
        return random.sample(all_moves, batch_size)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get training data statistics."""
        total_positions = sum(len(g.moves) for g in self.completed_games)
        outcomes = {'white_win': 0, 'black_win': 0, 'draw': 0}
        
        for game in self.completed_games:
            outcomes[game.outcome] = outcomes.get(game.outcome, 0) + 1
        
        return {
            'total_games': len(self.completed_games),
            'total_positions': total_positions,
            'games_in_progress': len(self.current_games),
            'outcomes': outcomes
        }
    
    def save_training_data(self) -> None:
        """Save training data to disk."""
        NN_TRAINING_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with self.lock:
            data = {
                'games': [asdict(g) for g in self.completed_games[-1000:]],  # Keep last 1000 games
                'stats': self.get_stats(),
                'saved_at': datetime.now().isoformat()
            }
        
        with open(NN_TRAINING_DATA_PATH, 'w') as f:
            json.dump(data, f)
        
        print(f"[NNTrainer] Saved {len(self.completed_games)} games of training data")
    
    def _load_training_data(self) -> None:
        """Load existing training data."""
        if not NN_TRAINING_DATA_PATH.exists():
            return
        
        try:
            with open(NN_TRAINING_DATA_PATH, 'r') as f:
                data = json.load(f)
            
            for game_dict in data.get('games', []):
                self.completed_games.append(GameTrainingData(**game_dict))
            
            print(f"[NNTrainer] Loaded {len(self.completed_games)} games of training data")
            
        except Exception as e:
            print(f"[NNTrainer] Error loading training data: {e}")


class NeuralNetworkTrainer:
    """
    Manages neural network training with live updates.
    
    Features:
    - Background training thread
    - Hot-reload of weights for live bot
    - Training progress tracking
    - Self-play game generation
    """
    
    def __init__(self):
        self.network = ChessNeuralNetwork()
        self.data_collector = NeuralTrainingDataCollector()
        
        self.is_training = False
        self.training_thread: Optional[threading.Thread] = None
        self.stop_training = False
        
        # Training session state
        self.session_id: Optional[str] = None
        self.epochs_completed = 0
        self.target_epochs = 0
        self.current_loss = 0.0
        self.training_history: List[Dict[str, float]] = []
        
        # Self-play progress tracking
        self.self_play_in_progress = False
        self.self_play_games_completed = 0
        self.self_play_games_target = 0
        self.current_phase = 'idle'  # 'idle', 'self_play', 'training', 'complete'
        
        # Current game state for live preview
        self.current_game: Optional[Dict[str, Any]] = None
        
        # Callbacks for UI updates
        self.on_epoch_complete = None
        self.on_training_complete = None
    
    def start_training(self, 
                      epochs: int = 10,
                      batch_size: int = 32,
                      learning_rate: float = 0.01,
                      include_self_play: bool = True,
                      self_play_games: int = 50) -> Dict[str, Any]:
        """
        Start neural network training.
        
        Args:
            epochs: Number of training epochs
            batch_size: Positions per training batch
            learning_rate: Learning rate for gradient descent
            include_self_play: Whether to generate self-play games
            self_play_games: Number of self-play games to generate
        """
        if self.is_training:
            return {'ok': False, 'error': 'Training already in progress'}
        
        self.session_id = f"nn_session_{int(time.time())}"
        self.target_epochs = epochs
        self.epochs_completed = 0
        self.training_history = []
        self.stop_training = False
        self.network.learning_rate = learning_rate
        
        # Reset self-play tracking
        self.self_play_in_progress = False
        self.self_play_games_completed = 0
        self.self_play_games_target = self_play_games if include_self_play else 0
        self.current_phase = 'starting'
        
        self.is_training = True
        
        self.training_thread = threading.Thread(
            target=self._training_loop,
            args=(epochs, batch_size, include_self_play, self_play_games),
            daemon=True
        )
        self.training_thread.start()
        
        return {
            'ok': True,
            'session_id': self.session_id,
            'message': f'Started training for {epochs} epochs'
        }
    
    def stop_training_session(self) -> Dict[str, Any]:
        """Stop the current training session."""
        if not self.is_training:
            return {'ok': False, 'error': 'No training in progress'}
        
        self.stop_training = True
        return {'ok': True, 'message': 'Stopping training...'}
    
    def _training_loop(self, epochs: int, batch_size: int, 
                       include_self_play: bool, self_play_games: int) -> None:
        """Main training loop."""
        try:
            print(f"[NNTrainer] Starting training: {epochs} epochs, batch_size={batch_size}")
            
            # Generate self-play games if requested
            if include_self_play and self_play_games > 0:
                self.current_phase = 'self_play'
                self.self_play_in_progress = True
                print(f"[NNTrainer] Generating {self_play_games} self-play games...")
                self._generate_self_play_games(self_play_games)
                self.self_play_in_progress = False
            
            # Training epochs
            self.current_phase = 'training'
            for epoch in range(epochs):
                if self.stop_training:
                    break
                
                epoch_loss = self._train_epoch(batch_size)
                self.epochs_completed = epoch + 1
                self.current_loss = epoch_loss
                
                self.training_history.append({
                    'epoch': epoch + 1,
                    'loss': epoch_loss,
                    'positions_trained': self.network.positions_trained
                })
                
                # Save weights periodically
                if (epoch + 1) % 5 == 0:
                    self.network.save_weights()
                    self.data_collector.save_training_data()
                
                print(f"[NNTrainer] Epoch {epoch + 1}/{epochs} - Loss: {epoch_loss:.6f}")
                
                if self.on_epoch_complete:
                    self.on_epoch_complete(epoch + 1, epoch_loss)
            
            # Final save
            self.network.save_weights()
            self.data_collector.save_training_data()
            
            self.current_phase = 'complete'
            print(f"[NNTrainer] Training complete: {self.epochs_completed} epochs")
            
            if self.on_training_complete:
                self.on_training_complete(self.get_status())
                
        except Exception as e:
            print(f"[NNTrainer] Training error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_training = False
            self.current_phase = 'idle'
    
    def _train_epoch(self, batch_size: int) -> float:
        """Train for one epoch."""
        batch = self.data_collector.get_training_batch(batch_size)
        
        if not batch:
            return 0.0
        
        total_loss = 0.0
        for move_record in batch:
            try:
                board = chess.Board(move_record.fen)
                loss = self.network.train_on_position(board, move_record.game_outcome)
                total_loss += loss
            except Exception as e:
                continue
        
        return total_loss / max(1, len(batch))
    
    def _generate_self_play_games(self, num_games: int) -> None:
        """Generate self-play games for training data."""
        from search import ChessSearchEngine
        from config import ChessConfig
        
        config = ChessConfig("self_play")
        engine = ChessSearchEngine(config)
        
        self.self_play_games_completed = 0
        self.self_play_games_target = num_games
        
        for game_num in range(num_games):
            if self.stop_training:
                break
            
            game_id = f"selfplay_{int(time.time())}_{game_num}"
            self.data_collector.start_game(game_id)
            
            board = chess.Board()
            move_count = 0
            max_moves = 100
            last_move = None
            
            # Initialize current game for live preview
            self.current_game = {
                'game_id': game_id,
                'game_number': game_num + 1,
                'total_games': num_games,
                'fen': board.fen(),
                'move_count': 0,
                'white_id': f'NN_White_{game_num}',
                'black_id': f'NN_Black_{game_num}',
                'last_move': None
            }
            
            while not board.is_game_over() and move_count < max_moves:
                # Record position before move
                fen = board.fen()
                
                # Get move from engine (with some randomness for variety)
                move = engine.find_best_move(board, depth=2)
                
                if move is None:
                    break
                
                self.data_collector.record_move(game_id, fen, move.uci(), move_count + 1)
                board.push(move)
                move_count += 1
                last_move = move.uci()
                
                # Update current game state for live preview
                self.current_game = {
                    'game_id': game_id,
                    'game_number': game_num + 1,
                    'total_games': num_games,
                    'fen': board.fen(),
                    'move_count': move_count,
                    'white_id': f'NN_White_{game_num}',
                    'black_id': f'NN_Black_{game_num}',
                    'last_move': last_move
                }
            
            # Determine outcome
            if board.is_checkmate():
                outcome = 'black_win' if board.turn == chess.WHITE else 'white_win'
            else:
                outcome = 'draw'
            
            self.data_collector.finish_game(game_id, outcome, source='self_play')
            self.self_play_games_completed = game_num + 1
            
            if (game_num + 1) % 10 == 0:
                print(f"[NNTrainer] Generated {game_num + 1}/{num_games} self-play games")
        
        # Clear current game when done
        self.current_game = None
    
    def get_status(self) -> Dict[str, Any]:
        """Get current training status."""
        # Calculate overall progress
        if self.current_phase == 'self_play':
            # During self-play, progress is based on games generated
            phase_progress = (self.self_play_games_completed / max(1, self.self_play_games_target)) * 100
            overall_progress = phase_progress * 0.3  # Self-play is ~30% of total time
        elif self.current_phase == 'training':
            # During training, progress is based on epochs
            epoch_progress = (self.epochs_completed / max(1, self.target_epochs)) * 100
            overall_progress = 30 + epoch_progress * 0.7  # Training is ~70% of total time
        elif self.current_phase == 'complete':
            overall_progress = 100
        else:
            overall_progress = 0
        
        return {
            'is_training': self.is_training,
            'session_id': self.session_id,
            'current_phase': self.current_phase,
            'epochs_completed': self.epochs_completed,
            'target_epochs': self.target_epochs,
            'current_loss': round(self.current_loss, 6),
            'progress_percent': round(overall_progress, 1),
            'self_play': {
                'in_progress': self.self_play_in_progress,
                'games_completed': self.self_play_games_completed,
                'games_target': self.self_play_games_target
            },
            'current_game': self.current_game,
            'network_stats': self.network.get_stats(),
            'data_stats': self.data_collector.get_stats(),
            'training_history': self.training_history[-20:]  # Last 20 epochs
        }
    
    def get_current_game(self) -> Optional[Dict[str, Any]]:
        """Get the current self-play game state for live preview."""
        return self.current_game
    
    def evaluate_position(self, fen: str) -> Dict[str, Any]:
        """Evaluate a position using the neural network."""
        try:
            board = chess.Board(fen)
            evaluation = self.network.evaluate(board)
            
            return {
                'ok': True,
                'evaluation': round(evaluation, 4),
                'interpretation': self._interpret_evaluation(evaluation)
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}
    
    def _interpret_evaluation(self, eval_score: float) -> str:
        """Convert evaluation to human-readable interpretation."""
        if eval_score > 0.5:
            return "White has a winning advantage"
        elif eval_score > 0.2:
            return "White has a clear advantage"
        elif eval_score > 0.05:
            return "White is slightly better"
        elif eval_score > -0.05:
            return "Position is roughly equal"
        elif eval_score > -0.2:
            return "Black is slightly better"
        elif eval_score > -0.5:
            return "Black has a clear advantage"
        else:
            return "Black has a winning advantage"
    
    def reset_network(self) -> Dict[str, Any]:
        """Reset the neural network to random weights."""
        self.network.reset_weights()
        return {
            'ok': True,
            'message': 'Neural network reset to random weights'
        }
    
    def set_learning_rate(self, rate: float) -> Dict[str, Any]:
        """Update the learning rate."""
        if rate <= 0 or rate > 1:
            return {'ok': False, 'error': 'Learning rate must be between 0 and 1'}
        
        self.network.learning_rate = rate
        return {'ok': True, 'learning_rate': rate}


# Global trainer instance
_nn_trainer: Optional[NeuralNetworkTrainer] = None


def get_nn_trainer() -> NeuralNetworkTrainer:
    """Get or create the global neural network trainer."""
    global _nn_trainer
    if _nn_trainer is None:
        _nn_trainer = NeuralNetworkTrainer()
    return _nn_trainer
