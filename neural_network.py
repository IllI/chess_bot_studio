"""
Neural Network Evaluation Module for Chess Bot Studio.

This module provides a CNN-based position evaluator that learns from game outcomes.
It tracks move-level data and uses backpropagation to improve evaluation.

Educational Purpose:
- Demonstrates how neural networks can learn complex patterns
- Shows the difference between hand-crafted heuristics and learned features
- Illustrates supervised learning from game outcomes
"""

import json
import os
import random
import math
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque
import chess

# Neural network weights path
NN_WEIGHTS_PATH = Path(__file__).parent / "configs" / "neural_weights.json"
NN_TRAINING_DATA_PATH = Path(__file__).parent / "configs" / "nn_training_data.json"


@dataclass
class MoveRecord:
    """Record of a single move for training."""
    fen: str  # Position before move
    move_uci: str  # Move played
    game_outcome: float  # 1.0 = win, 0.5 = draw, 0.0 = loss (from mover's perspective)
    move_number: int
    game_id: str


class ChessNeuralNetwork:
    """
    A simple neural network for chess position evaluation.
    
    Architecture (educational, not production-grade):
    - Input: 768 features (12 piece types × 64 squares)
    - Hidden Layer 1: 256 neurons (learns piece patterns)
    - Hidden Layer 2: 64 neurons (learns positional concepts)
    - Output: 1 neuron (position evaluation -1 to +1)
    
    This demonstrates:
    - Feature extraction from chess positions
    - Forward propagation
    - Backpropagation and gradient descent
    - How networks learn patterns from data
    """
    
    # Piece to index mapping for input encoding
    PIECE_TO_INDEX = {
        'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,  # White pieces
        'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11  # Black pieces
    }
    
    def __init__(self, learning_rate: float = 0.01):
        """
        Initialize the neural network with random weights.
        
        Args:
            learning_rate: How fast the network learns (0.001 - 0.1 typical)
        """
        self.learning_rate = learning_rate
        self.input_size = 768  # 12 pieces × 64 squares
        self.hidden1_size = 256
        self.hidden2_size = 64
        self.output_size = 1
        
        # Initialize weights with Xavier initialization
        self.weights1 = self._xavier_init(self.input_size, self.hidden1_size)
        self.biases1 = [0.0] * self.hidden1_size
        
        self.weights2 = self._xavier_init(self.hidden1_size, self.hidden2_size)
        self.biases2 = [0.0] * self.hidden2_size
        
        self.weights3 = self._xavier_init(self.hidden2_size, self.output_size)
        self.biases3 = [0.0] * self.output_size
        
        # Training statistics
        self.games_trained = 0
        self.positions_trained = 0
        self.avg_loss = 0.0
        self.loss_history = deque(maxlen=100)
        
        # Version for hot-reload detection
        self.version = 0
        self.last_modified = datetime.now().isoformat()
        
        # Try to load existing weights
        self._load_weights()
    
    def _xavier_init(self, fan_in: int, fan_out: int) -> List[List[float]]:
        """Xavier/Glorot initialization for better training."""
        limit = math.sqrt(6.0 / (fan_in + fan_out))
        return [[random.uniform(-limit, limit) for _ in range(fan_out)] 
                for _ in range(fan_in)]
    
    def _relu(self, x: float) -> float:
        """ReLU activation function."""
        return max(0.0, x)
    
    def _relu_derivative(self, x: float) -> float:
        """Derivative of ReLU for backpropagation."""
        return 1.0 if x > 0 else 0.0
    
    def _tanh(self, x: float) -> float:
        """Tanh activation for output (-1 to 1 range)."""
        # Clip to prevent overflow
        x = max(-20, min(20, x))
        return math.tanh(x)
    
    def _tanh_derivative(self, x: float) -> float:
        """Derivative of tanh for backpropagation."""
        t = self._tanh(x)
        return 1.0 - t * t
    
    def encode_position(self, board: chess.Board) -> List[float]:
        """
        Encode a chess position as neural network input.
        
        Creates a 768-dimensional vector:
        - 12 planes (one per piece type)
        - 64 squares per plane
        - 1.0 if piece present, 0.0 otherwise
        
        This is a simplified version of what AlphaZero uses.
        """
        features = [0.0] * self.input_size
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                piece_idx = self.PIECE_TO_INDEX.get(piece.symbol())
                if piece_idx is not None:
                    feature_idx = piece_idx * 64 + square
                    features[feature_idx] = 1.0
        
        # Add side to move as a bias (flip evaluation if black to move)
        self.side_to_move = 1.0 if board.turn == chess.WHITE else -1.0
        
        return features
    
    def forward(self, features: List[float]) -> Tuple[float, Dict[str, Any]]:
        """
        Forward pass through the network.
        
        Returns evaluation and intermediate values for backpropagation.
        """
        # Layer 1: Input -> Hidden1
        hidden1_pre = []
        hidden1 = []
        for j in range(self.hidden1_size):
            z = self.biases1[j]
            for i in range(self.input_size):
                z += features[i] * self.weights1[i][j]
            hidden1_pre.append(z)
            hidden1.append(self._relu(z))
        
        # Layer 2: Hidden1 -> Hidden2
        hidden2_pre = []
        hidden2 = []
        for j in range(self.hidden2_size):
            z = self.biases2[j]
            for i in range(self.hidden1_size):
                z += hidden1[i] * self.weights2[i][j]
            hidden2_pre.append(z)
            hidden2.append(self._relu(z))
        
        # Layer 3: Hidden2 -> Output
        output_pre = self.biases3[0]
        for i in range(self.hidden2_size):
            output_pre += hidden2[i] * self.weights3[i][0]
        
        output = self._tanh(output_pre)
        
        # Store intermediate values for backpropagation
        cache = {
            'features': features,
            'hidden1_pre': hidden1_pre,
            'hidden1': hidden1,
            'hidden2_pre': hidden2_pre,
            'hidden2': hidden2,
            'output_pre': output_pre,
            'output': output
        }
        
        return output, cache
    
    def evaluate(self, board: chess.Board) -> float:
        """
        Evaluate a chess position using the neural network.
        
        Returns:
            Evaluation from white's perspective (-1 to +1)
            Positive = white advantage, Negative = black advantage
        """
        features = self.encode_position(board)
        output, _ = self.forward(features)
        return output * self.side_to_move  # Adjust for side to move
    
    def backward(self, cache: Dict[str, Any], target: float) -> float:
        """
        Backpropagation to compute gradients and update weights.
        
        Args:
            cache: Intermediate values from forward pass
            target: Target value (1.0 = win, 0.0 = loss, 0.5 = draw)
        
        Returns:
            Loss value for this example
        """
        # Compute loss (mean squared error)
        output = cache['output']
        # Convert target from [0, 1] to [-1, 1] range
        target_scaled = target * 2 - 1
        loss = (output - target_scaled) ** 2
        
        # Output layer gradient
        d_output = 2 * (output - target_scaled) * self._tanh_derivative(cache['output_pre'])
        
        # Hidden2 -> Output gradients
        d_hidden2 = [0.0] * self.hidden2_size
        for i in range(self.hidden2_size):
            d_hidden2[i] = d_output * self.weights3[i][0] * self._relu_derivative(cache['hidden2_pre'][i])
            # Update weights
            self.weights3[i][0] -= self.learning_rate * d_output * cache['hidden2'][i]
        self.biases3[0] -= self.learning_rate * d_output
        
        # Hidden1 -> Hidden2 gradients
        d_hidden1 = [0.0] * self.hidden1_size
        for i in range(self.hidden1_size):
            for j in range(self.hidden2_size):
                d_hidden1[i] += d_hidden2[j] * self.weights2[i][j]
            d_hidden1[i] *= self._relu_derivative(cache['hidden1_pre'][i])
            # Update weights
            for j in range(self.hidden2_size):
                self.weights2[i][j] -= self.learning_rate * d_hidden2[j] * cache['hidden1'][i]
        for j in range(self.hidden2_size):
            self.biases2[j] -= self.learning_rate * d_hidden2[j]
        
        # Input -> Hidden1 gradients (only update for non-zero inputs)
        for i in range(self.input_size):
            if cache['features'][i] > 0:
                for j in range(self.hidden1_size):
                    self.weights1[i][j] -= self.learning_rate * d_hidden1[j] * cache['features'][i]
        for j in range(self.hidden1_size):
            self.biases1[j] -= self.learning_rate * d_hidden1[j]
        
        return loss
    
    def train_on_position(self, board: chess.Board, outcome: float) -> float:
        """
        Train on a single position.
        
        Args:
            board: Chess position
            outcome: Game outcome (1.0 = white won, 0.5 = draw, 0.0 = black won)
        
        Returns:
            Loss value
        """
        features = self.encode_position(board)
        _, cache = self.forward(features)
        
        # Adjust outcome based on side to move
        if board.turn == chess.BLACK:
            outcome = 1.0 - outcome  # Flip for black's perspective
        
        loss = self.backward(cache, outcome)
        
        self.positions_trained += 1
        self.loss_history.append(loss)
        self.avg_loss = sum(self.loss_history) / len(self.loss_history)
        
        return loss
    
    def train_on_game(self, moves: List[MoveRecord]) -> Dict[str, float]:
        """
        Train on all positions from a game.
        
        Uses temporal difference: positions closer to the end
        get stronger training signal.
        """
        if not moves:
            return {'loss': 0, 'positions': 0}
        
        total_loss = 0.0
        num_moves = len(moves)
        
        for i, move_record in enumerate(moves):
            try:
                board = chess.Board(move_record.fen)
                
                # Temporal weighting: later positions matter more
                weight = (i + 1) / num_moves
                
                # Adjust learning rate based on position in game
                original_lr = self.learning_rate
                self.learning_rate = original_lr * (0.5 + 0.5 * weight)
                
                loss = self.train_on_position(board, move_record.game_outcome)
                total_loss += loss
                
                self.learning_rate = original_lr
                
            except Exception as e:
                print(f"[NeuralNet] Error training on position: {e}")
                continue
        
        self.games_trained += 1
        self.version += 1
        self.last_modified = datetime.now().isoformat()
        
        return {
            'loss': total_loss / max(1, num_moves),
            'positions': num_moves
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        return {
            'games_trained': self.games_trained,
            'positions_trained': self.positions_trained,
            'avg_loss': round(self.avg_loss, 6),
            'learning_rate': self.learning_rate,
            'version': self.version,
            'last_modified': self.last_modified,
            'architecture': {
                'input': self.input_size,
                'hidden1': self.hidden1_size,
                'hidden2': self.hidden2_size,
                'output': self.output_size
            }
        }
    
    def save_weights(self) -> None:
        """Save network weights to disk."""
        NN_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'version': self.version,
            'last_modified': self.last_modified,
            'stats': {
                'games_trained': self.games_trained,
                'positions_trained': self.positions_trained,
                'avg_loss': self.avg_loss
            },
            'hyperparameters': {
                'learning_rate': self.learning_rate,
                'input_size': self.input_size,
                'hidden1_size': self.hidden1_size,
                'hidden2_size': self.hidden2_size
            },
            'weights': {
                'w1': self.weights1,
                'b1': self.biases1,
                'w2': self.weights2,
                'b2': self.biases2,
                'w3': self.weights3,
                'b3': self.biases3
            }
        }
        
        with open(NN_WEIGHTS_PATH, 'w') as f:
            json.dump(data, f)
        
        print(f"[NeuralNet] Saved weights (v{self.version}, {self.positions_trained} positions trained)")
    
    def _load_weights(self) -> bool:
        """Load network weights from disk."""
        if not NN_WEIGHTS_PATH.exists():
            print("[NeuralNet] No saved weights found, using random initialization")
            return False
        
        try:
            with open(NN_WEIGHTS_PATH, 'r') as f:
                data = json.load(f)
            
            self.version = data.get('version', 0)
            self.last_modified = data.get('last_modified', datetime.now().isoformat())
            
            stats = data.get('stats', {})
            self.games_trained = stats.get('games_trained', 0)
            self.positions_trained = stats.get('positions_trained', 0)
            self.avg_loss = stats.get('avg_loss', 0.0)
            
            weights = data.get('weights', {})
            if weights:
                self.weights1 = weights.get('w1', self.weights1)
                self.biases1 = weights.get('b1', self.biases1)
                self.weights2 = weights.get('w2', self.weights2)
                self.biases2 = weights.get('b2', self.biases2)
                self.weights3 = weights.get('w3', self.weights3)
                self.biases3 = weights.get('b3', self.biases3)
            
            print(f"[NeuralNet] Loaded weights (v{self.version}, {self.positions_trained} positions)")
            return True
            
        except Exception as e:
            print(f"[NeuralNet] Error loading weights: {e}")
            return False
    
    def reset_weights(self) -> None:
        """Reset network to random weights."""
        self.weights1 = self._xavier_init(self.input_size, self.hidden1_size)
        self.biases1 = [0.0] * self.hidden1_size
        self.weights2 = self._xavier_init(self.hidden1_size, self.hidden2_size)
        self.biases2 = [0.0] * self.hidden2_size
        self.weights3 = self._xavier_init(self.hidden2_size, self.output_size)
        self.biases3 = [0.0] * self.output_size
        
        self.games_trained = 0
        self.positions_trained = 0
        self.avg_loss = 0.0
        self.loss_history.clear()
        self.version = 0
        self.last_modified = datetime.now().isoformat()
        
        print("[NeuralNet] Weights reset to random initialization")
