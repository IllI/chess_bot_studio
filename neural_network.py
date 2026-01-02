"""
Neural Network Evaluation Module for Chess Bot Studio.

This module provides a neural network position evaluator that learns from:
1. Material differences (immediate feedback)
2. Position quality (learned patterns)
3. Game outcomes (long-term feedback)

Key improvements over basic approach:
- Material-aware input features
- Move-quality scoring (not just game outcome)
- Piece value encoding
- Attack/defense awareness
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

# Standard piece values for material calculation
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0
}


@dataclass
class MoveRecord:
    """Record of a single move for training."""
    fen_before: str  # Position before move
    fen_after: str   # Position after move
    move_uci: str    # Move played
    material_change: float  # Material gained/lost by this move
    game_outcome: float  # 1.0 = win, 0.5 = draw, 0.0 = loss
    move_number: int
    game_id: str
    is_capture: bool
    captured_piece_value: int


class ChessNeuralNetwork:
    """
    Neural network for chess position evaluation with material awareness.
    
    Architecture:
    - Input: 833 features
      - 768: piece positions (12 types × 64 squares)
      - 1: side to move
      - 1: material balance (normalized)
      - 6: piece counts for white
      - 6: piece counts for black
      - 1: is in check
      - 8: castling rights and other flags
      - 52: additional positional features
    - Hidden Layer 1: 512 neurons
    - Hidden Layer 2: 128 neurons  
    - Hidden Layer 3: 32 neurons
    - Output: 1 neuron (evaluation)
    """
    
    PIECE_TO_INDEX = {
        'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
        'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
    }
    
    def __init__(self, learning_rate: float = 0.01):
        """Initialize with moderate learning rate for faster learning."""
        self.learning_rate = learning_rate
        
        # Larger, more expressive architecture
        self.input_size = 833
        self.hidden1_size = 512
        self.hidden2_size = 128
        self.hidden3_size = 32
        self.output_size = 1
        
        # Initialize weights
        self.weights1 = self._he_init(self.input_size, self.hidden1_size)
        self.biases1 = [0.01] * self.hidden1_size  # Small positive bias for ReLU
        
        self.weights2 = self._he_init(self.hidden1_size, self.hidden2_size)
        self.biases2 = [0.01] * self.hidden2_size
        
        self.weights3 = self._he_init(self.hidden2_size, self.hidden3_size)
        self.biases3 = [0.01] * self.hidden3_size
        
        self.weights4 = self._he_init(self.hidden3_size, self.output_size)
        self.biases4 = [0.0] * self.output_size
        
        # Training statistics
        self.games_trained = 0
        self.positions_trained = 0
        self.avg_loss = 0.0
        self.loss_history = deque(maxlen=1000)
        
        # Version tracking
        self.version = 0
        self.last_modified = datetime.now().isoformat()
        
        # Try to load existing weights
        self._load_weights()
    
    def _he_init(self, fan_in: int, fan_out: int) -> List[List[float]]:
        """He initialization - better for ReLU networks."""
        std = math.sqrt(2.0 / fan_in)
        return [[random.gauss(0, std) for _ in range(fan_out)] 
                for _ in range(fan_in)]
    
    def _leaky_relu(self, x: float, alpha: float = 0.01) -> float:
        """Leaky ReLU - prevents dead neurons."""
        return x if x > 0 else alpha * x
    
    def _leaky_relu_derivative(self, x: float, alpha: float = 0.01) -> float:
        """Derivative of Leaky ReLU."""
        return 1.0 if x > 0 else alpha
    
    def _tanh(self, x: float) -> float:
        """Tanh activation for output."""
        x = max(-10, min(10, x))
        return math.tanh(x)
    
    def _tanh_derivative(self, x: float) -> float:
        """Derivative of tanh."""
        t = self._tanh(x)
        return 1.0 - t * t
    
    def encode_position(self, board: chess.Board) -> List[float]:
        """
        Encode position with rich features including material awareness and THREAT DETECTION.
        """
        features = [0.0] * self.input_size
        idx = 0
        
        # 1. Piece positions (768 features)
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                piece_idx = self.PIECE_TO_INDEX.get(piece.symbol())
                if piece_idx is not None:
                    features[piece_idx * 64 + square] = 1.0
        idx = 768
        
        # 2. Side to move (1 feature)
        features[idx] = 1.0 if board.turn == chess.WHITE else -1.0
        idx += 1
        
        # 3. Material balance normalized to [-1, 1] (1 feature)
        white_material = 0
        black_material = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                value = PIECE_VALUES.get(piece.piece_type, 0)
                if piece.color == chess.WHITE:
                    white_material += value
                else:
                    black_material += value
        
        material_diff = white_material - black_material
        # Normalize: queen difference (~900) maps to ~0.5
        features[idx] = max(-1.0, min(1.0, material_diff / 2000.0))
        idx += 1
        
        # 4. Piece counts for white (6 features)
        for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]:
            count = len(board.pieces(piece_type, chess.WHITE))
            features[idx] = count / 8.0  # Normalize
            idx += 1
        
        # 5. Piece counts for black (6 features)
        for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]:
            count = len(board.pieces(piece_type, chess.BLACK))
            features[idx] = count / 8.0
            idx += 1
        
        # 6. Is in check (1 feature)
        features[idx] = 1.0 if board.is_check() else 0.0
        idx += 1
        
        # 7. Castling rights (4 features)
        features[idx] = 1.0 if board.has_kingside_castling_rights(chess.WHITE) else 0.0
        idx += 1
        features[idx] = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
        idx += 1
        features[idx] = 1.0 if board.has_kingside_castling_rights(chess.BLACK) else 0.0
        idx += 1
        features[idx] = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0
        idx += 1
        
        # 8. Game phase (4 features) - opening/middlegame/endgame indicators
        total_pieces = len(board.piece_map())
        features[idx] = 1.0 if total_pieces > 28 else 0.0  # Opening
        idx += 1
        features[idx] = 1.0 if 12 < total_pieces <= 28 else 0.0  # Middlegame
        idx += 1
        features[idx] = 1.0 if total_pieces <= 12 else 0.0  # Endgame
        idx += 1
        features[idx] = total_pieces / 32.0  # Normalized piece count
        idx += 1
        
        # 9. Mobility (legal moves count, normalized) (2 features)
        features[idx] = len(list(board.legal_moves)) / 50.0
        idx += 1
        try:
            board_copy = board.copy()
            board_copy.turn = not board_copy.turn
            features[idx] = len(list(board_copy.legal_moves)) / 50.0
        except:
            features[idx] = 0.0
        idx += 1
        
        # 10. Center control (4 center squares) (2 features)
        center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
        white_center = sum(1 for sq in center_squares if board.piece_at(sq) and board.piece_at(sq).color == chess.WHITE)
        black_center = sum(1 for sq in center_squares if board.piece_at(sq) and board.piece_at(sq).color == chess.BLACK)
        features[idx] = white_center / 4.0
        idx += 1
        features[idx] = black_center / 4.0
        idx += 1
        
        # 11. King safety - distance from center (2 features)
        white_king_sq = board.king(chess.WHITE)
        black_king_sq = board.king(chess.BLACK)
        if white_king_sq:
            wk_file = chess.square_file(white_king_sq)
            wk_rank = chess.square_rank(white_king_sq)
            features[idx] = abs(wk_file - 3.5) / 3.5  # Distance from center file
        idx += 1
        if black_king_sq:
            bk_file = chess.square_file(black_king_sq)
            bk_rank = chess.square_rank(black_king_sq)
            features[idx] = abs(bk_file - 3.5) / 3.5
        idx += 1
        
        # 12. CRITICAL: Threat detection features (12 features)
        # These help the network understand tactical situations
        white_hanging, white_attacked, white_threat_value = self._count_threats(board, chess.WHITE)
        black_hanging, black_attacked, black_threat_value = self._count_threats(board, chess.BLACK)
        
        # Hanging pieces count (normalized)
        features[idx] = white_hanging / 8.0
        idx += 1
        features[idx] = black_hanging / 8.0
        idx += 1
        
        # Attacked pieces count (normalized)
        features[idx] = white_attacked / 16.0
        idx += 1
        features[idx] = black_attacked / 16.0
        idx += 1
        
        # Total threat value (normalized by queen value)
        features[idx] = max(-1.0, min(1.0, white_threat_value / 900.0))
        idx += 1
        features[idx] = max(-1.0, min(1.0, black_threat_value / 900.0))
        idx += 1
        
        # Net threat balance (positive = white has more threats on black)
        net_threat = black_threat_value - white_threat_value  # Threats ON opponent
        features[idx] = max(-1.0, min(1.0, net_threat / 1000.0))
        idx += 1
        
        # Queen safety specifically (very important!)
        white_queen_safe = self._is_queen_safe(board, chess.WHITE)
        black_queen_safe = self._is_queen_safe(board, chess.BLACK)
        features[idx] = 1.0 if white_queen_safe else -1.0
        idx += 1
        features[idx] = 1.0 if black_queen_safe else -1.0
        idx += 1
        
        # Can capture hanging piece this move?
        can_capture_hanging = self._can_capture_hanging(board)
        features[idx] = 1.0 if can_capture_hanging else 0.0
        idx += 1
        
        # Opponent can capture our hanging piece?
        board_copy = board.copy()
        board_copy.turn = not board_copy.turn
        opponent_can_capture = self._can_capture_hanging(board_copy)
        features[idx] = -1.0 if opponent_can_capture else 0.0
        idx += 1
        
        # Fill remaining features with zeros (padding to 833)
        
        return features
    
    def _count_threats(self, board: chess.Board, color: chess.Color) -> Tuple[int, int, float]:
        """
        Count threats against pieces of the given color.
        
        Returns:
            (hanging_count, attacked_count, total_threat_value)
        """
        hanging = 0
        attacked = 0
        threat_value = 0.0
        enemy_color = not color
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None or piece.color != color:
                continue
            
            # Skip king - handled separately
            if piece.piece_type == chess.KING:
                continue
            
            piece_value = PIECE_VALUES.get(piece.piece_type, 0)
            attackers = board.attackers(enemy_color, square)
            
            if attackers:
                attacked += 1
                defenders = board.attackers(color, square)
                
                if not defenders:
                    # Hanging piece!
                    hanging += 1
                    threat_value += piece_value
                else:
                    # Check if trade is unfavorable
                    min_attacker_value = min(
                        PIECE_VALUES.get(board.piece_at(sq).piece_type, 0)
                        for sq in attackers if board.piece_at(sq)
                    )
                    if min_attacker_value < piece_value:
                        threat_value += (piece_value - min_attacker_value) * 0.5
        
        return hanging, attacked, threat_value
    
    def _is_queen_safe(self, board: chess.Board, color: chess.Color) -> bool:
        """Check if the queen is safe (not hanging or attacked by lesser piece)."""
        queens = board.pieces(chess.QUEEN, color)
        if not queens:
            return True  # No queen to worry about
        
        queen_square = list(queens)[0]
        enemy_color = not color
        attackers = board.attackers(enemy_color, queen_square)
        
        if not attackers:
            return True  # Not attacked
        
        defenders = board.attackers(color, queen_square)
        if not defenders:
            return False  # Hanging queen!
        
        # Check if attacked by lesser piece
        for attacker_sq in attackers:
            attacker = board.piece_at(attacker_sq)
            if attacker and PIECE_VALUES.get(attacker.piece_type, 0) < 900:
                return False  # Attacked by piece worth less than queen
        
        return True
    
    def _can_capture_hanging(self, board: chess.Board) -> bool:
        """Check if the side to move can capture a hanging piece."""
        for move in board.legal_moves:
            if board.is_capture(move):
                captured_square = move.to_square
                captured_piece = board.piece_at(captured_square)
                if captured_piece:
                    # Check if the captured piece is defended
                    defenders = board.attackers(captured_piece.color, captured_square)
                    # Exclude the piece itself from defenders
                    if len(defenders) <= 1:  # Only the piece itself or nothing
                        return True
        return False
    
    def forward(self, features: List[float]) -> Tuple[float, Dict[str, Any]]:
        """Forward pass with 4 layers."""
        # Layer 1
        hidden1_pre = []
        hidden1 = []
        for j in range(self.hidden1_size):
            z = self.biases1[j]
            for i in range(self.input_size):
                z += features[i] * self.weights1[i][j]
            hidden1_pre.append(z)
            hidden1.append(self._leaky_relu(z))
        
        # Layer 2
        hidden2_pre = []
        hidden2 = []
        for j in range(self.hidden2_size):
            z = self.biases2[j]
            for i in range(self.hidden1_size):
                z += hidden1[i] * self.weights2[i][j]
            hidden2_pre.append(z)
            hidden2.append(self._leaky_relu(z))
        
        # Layer 3
        hidden3_pre = []
        hidden3 = []
        for j in range(self.hidden3_size):
            z = self.biases3[j]
            for i in range(self.hidden2_size):
                z += hidden2[i] * self.weights3[i][j]
            hidden3_pre.append(z)
            hidden3.append(self._leaky_relu(z))
        
        # Output layer
        output_pre = self.biases4[0]
        for i in range(self.hidden3_size):
            output_pre += hidden3[i] * self.weights4[i][0]
        output = self._tanh(output_pre)
        
        cache = {
            'features': features,
            'hidden1_pre': hidden1_pre, 'hidden1': hidden1,
            'hidden2_pre': hidden2_pre, 'hidden2': hidden2,
            'hidden3_pre': hidden3_pre, 'hidden3': hidden3,
            'output_pre': output_pre, 'output': output
        }
        
        return output, cache
    
    def evaluate(self, board: chess.Board) -> float:
        """Evaluate position from white's perspective."""
        features = self.encode_position(board)
        output, _ = self.forward(features)
        
        # Scale to centipawn-like range for compatibility
        return output * 1000
    
    def backward(self, cache: Dict[str, Any], target: float, weight: float = 1.0) -> float:
        """
        Backpropagation with weighted learning.
        
        Args:
            cache: Forward pass cache
            target: Target evaluation (-1 to 1)
            weight: Learning weight (higher for more important examples)
        """
        output = cache['output']
        loss = (output - target) ** 2
        
        lr = self.learning_rate * weight
        
        # Output gradient
        d_output = 2 * (output - target) * self._tanh_derivative(cache['output_pre'])
        
        # Layer 3 -> Output
        d_hidden3 = [0.0] * self.hidden3_size
        for i in range(self.hidden3_size):
            d_hidden3[i] = d_output * self.weights4[i][0] * self._leaky_relu_derivative(cache['hidden3_pre'][i])
            self.weights4[i][0] -= lr * d_output * cache['hidden3'][i]
        self.biases4[0] -= lr * d_output
        
        # Layer 2 -> Layer 3
        d_hidden2 = [0.0] * self.hidden2_size
        for i in range(self.hidden2_size):
            for j in range(self.hidden3_size):
                d_hidden2[i] += d_hidden3[j] * self.weights3[i][j]
            d_hidden2[i] *= self._leaky_relu_derivative(cache['hidden2_pre'][i])
            for j in range(self.hidden3_size):
                self.weights3[i][j] -= lr * d_hidden3[j] * cache['hidden2'][i]
        for j in range(self.hidden3_size):
            self.biases3[j] -= lr * d_hidden3[j]
        
        # Layer 1 -> Layer 2
        d_hidden1 = [0.0] * self.hidden1_size
        for i in range(self.hidden1_size):
            for j in range(self.hidden2_size):
                d_hidden1[i] += d_hidden2[j] * self.weights2[i][j]
            d_hidden1[i] *= self._leaky_relu_derivative(cache['hidden1_pre'][i])
            for j in range(self.hidden2_size):
                self.weights2[i][j] -= lr * d_hidden2[j] * cache['hidden1'][i]
        for j in range(self.hidden2_size):
            self.biases2[j] -= lr * d_hidden2[j]
        
        # Input -> Layer 1 (sparse update)
        for i in range(self.input_size):
            if abs(cache['features'][i]) > 0.001:
                for j in range(self.hidden1_size):
                    self.weights1[i][j] -= lr * d_hidden1[j] * cache['features'][i]
        for j in range(self.hidden1_size):
            self.biases1[j] -= lr * d_hidden1[j]
        
        return loss
    
    def train_on_position(self, board: chess.Board, target_eval: float, weight: float = 1.0) -> float:
        """
        Train on a position with a target evaluation.
        
        Args:
            board: Chess position
            target_eval: Target evaluation in [-1, 1] range
            weight: Learning weight
        """
        features = self.encode_position(board)
        _, cache = self.forward(features)
        
        loss = self.backward(cache, target_eval, weight)
        
        self.positions_trained += 1
        self.loss_history.append(loss)
        self.avg_loss = sum(self.loss_history) / len(self.loss_history)
        
        return loss
    
    def train_supervised_from_heuristic(self, num_positions: int = 1000) -> Dict[str, float]:
        """
        Train the neural network to match the heuristic evaluation.
        
        This is CRITICAL for the network to learn basic chess knowledge:
        - Material values
        - Piece activity
        - King safety
        - Threat detection
        
        The heuristic already knows these things, so we teach the network
        to replicate this knowledge, then it can improve from there.
        """
        from evaluation import evaluate_board
        import random
        
        print(f"[NeuralNet] Starting supervised training on {num_positions} positions...")
        
        total_loss = 0.0
        positions_trained = 0
        
        # Generate diverse positions by playing random games
        for game_num in range(num_positions // 20):  # ~20 positions per game
            board = chess.Board()
            
            # Play random moves to generate positions
            for move_num in range(random.randint(5, 40)):
                if board.is_game_over():
                    break
                
                legal_moves = list(board.legal_moves)
                if not legal_moves:
                    break
                
                # Get heuristic evaluation for this position
                heuristic_eval = evaluate_board(board)
                
                # Normalize to [-1, 1] range (heuristic is in centipawns)
                # A queen advantage (~900) should map to ~0.9
                target = max(-1.0, min(1.0, heuristic_eval / 1000.0))
                
                # Train on this position
                loss = self.train_on_position(board, target, weight=1.0)
                total_loss += loss
                positions_trained += 1
                
                # Make a random move
                move = random.choice(legal_moves)
                board.push(move)
            
            if (game_num + 1) % 10 == 0:
                avg_loss = total_loss / max(1, positions_trained)
                print(f"[NeuralNet] Supervised training: {positions_trained} positions, avg loss: {avg_loss:.6f}")
        
        # Save weights
        self.save_weights()
        
        avg_loss = total_loss / max(1, positions_trained)
        print(f"[NeuralNet] Supervised training complete: {positions_trained} positions, final avg loss: {avg_loss:.6f}")
        
        return {
            'positions_trained': positions_trained,
            'avg_loss': avg_loss
        }
    
    def train_on_tactical_positions(self) -> Dict[str, float]:
        """
        Train on specific tactical positions where the evaluation is clear.
        
        This teaches the network to recognize:
        - Hanging pieces
        - Material imbalances
        - Checkmate threats
        """
        from evaluation import evaluate_board
        
        print("[NeuralNet] Training on tactical positions...")
        
        # Tactical positions with known evaluations
        tactical_positions = [
            # (FEN, description, expected_eval_sign)
            # Material imbalances
            ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "Starting position", 0),
            ("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "White up a queen", 1),
            ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w Qkq - 0 1", "Black up a queen", -1),
            ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBN1 w Qkq - 0 1", "Black up a rook", -1),
            ("rnbqkbn1/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQq - 0 1", "White up a rook", 1),
            
            # Hanging pieces
            ("rnbqkbnr/pppp1ppp/8/4p3/3Q4/8/PPPP1PPP/RNB1KBNR b KQkq - 0 2", "White queen hanging", -1),
            ("rnb1kbnr/pppp1ppp/8/4q3/3P4/8/PPP2PPP/RNBQKBNR w KQkq - 0 3", "Black queen hanging", 1),
            ("rnbqkbnr/pppp1ppp/8/4R3/8/8/PPPP1PPP/RNBQKBN1 b KQkq - 0 2", "White rook hanging", -1),
            
            # Checkmate patterns
            ("rnb1kbnr/pppp1ppp/4p3/8/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 1", "Scholar's mate threat", -1),
            ("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 4", "White threatens mate", 1),
        ]
        
        total_loss = 0.0
        
        for fen, desc, expected_sign in tactical_positions:
            board = chess.Board(fen)
            heuristic_eval = evaluate_board(board)
            
            # Normalize to [-1, 1]
            target = max(-1.0, min(1.0, heuristic_eval / 1000.0))
            
            # Verify the heuristic agrees with our expectation
            if expected_sign != 0:
                if (expected_sign > 0 and target < 0) or (expected_sign < 0 and target > 0):
                    print(f"[NeuralNet] Warning: {desc} - heuristic disagrees (got {heuristic_eval:.0f})")
            
            # Train multiple times on each tactical position (they're important!)
            for _ in range(10):
                loss = self.train_on_position(board, target, weight=3.0)
                total_loss += loss
        
        self.save_weights()
        
        avg_loss = total_loss / (len(tactical_positions) * 10)
        print(f"[NeuralNet] Tactical training complete, avg loss: {avg_loss:.6f}")
        
        return {'avg_loss': avg_loss, 'positions': len(tactical_positions)}

    def train_on_move(self, fen_before: str, fen_after: str, 
                      material_change: float, game_outcome: float,
                      is_capture: bool, move_number: int) -> float:
        """
        Train on a specific move with immediate and long-term feedback.
        
        This is the key improvement: we learn from BOTH:
        1. Immediate material change (did we lose material?)
        2. Game outcome (did we eventually win?)
        
        Material changes are weighted MORE heavily to teach the network
        that losing a queen for a pawn is BAD immediately.
        """
        try:
            board_before = chess.Board(fen_before)
            board_after = chess.Board(fen_after)
            
            # Calculate target evaluation combining immediate and long-term
            # Material change: normalized to [-1, 1], queen loss = -0.45
            material_signal = max(-1.0, min(1.0, material_change / 2000.0))
            
            # Game outcome: 1.0 = win, 0.0 = loss, 0.5 = draw -> [-1, 1]
            outcome_signal = game_outcome * 2 - 1
            
            # CRITICAL: Weight material changes HEAVILY for captures
            # This teaches the network that bad trades are immediately punished
            if is_capture:
                if material_change < -200:  # Lost significant material (e.g., queen for pawn)
                    # STRONGLY punish bad captures
                    material_weight = 0.9
                    outcome_weight = 0.1
                elif material_change > 200:  # Gained significant material
                    # STRONGLY reward good captures
                    material_weight = 0.85
                    outcome_weight = 0.15
                else:
                    # Normal capture
                    material_weight = 0.7
                    outcome_weight = 0.3
            else:
                # Non-captures: balance material and outcome
                game_phase = min(1.0, move_number / 40.0)  # 0 = opening, 1 = late game
                material_weight = 0.4 - 0.2 * game_phase
                outcome_weight = 1.0 - material_weight
            
            target = material_weight * material_signal + outcome_weight * outcome_signal
            
            # Use higher learning weight for captures to learn faster
            learn_weight = 2.0 if is_capture else 1.0
            
            # Train on position AFTER the move
            loss = self.train_on_position(board_after, target, weight=learn_weight)
            
            return loss
            
        except Exception as e:
            print(f"[NeuralNet] Error training on move: {e}")
            return 0.0
    
    def train_on_game(self, moves: List[MoveRecord]) -> Dict[str, float]:
        """
        Train on all moves from a game with proper feedback.
        
        For losses, we weight later moves more heavily since those are
        closer to the mistake that caused the loss.
        """
        if not moves:
            return {'loss': 0, 'positions': 0}
        
        total_loss = 0.0
        num_moves = len(moves)
        
        # Check if this was a loss (game_outcome close to 0 for the losing side)
        # We look at the first move's outcome since all moves in a game have same outcome
        is_loss = moves[0].game_outcome < 0.3
        
        for i, move in enumerate(moves):
            # For losses, weight later moves more heavily
            # The moves closer to the end are more likely to be the mistakes
            if is_loss:
                # Exponential weighting: later moves get more weight
                position_weight = 1.0 + (i / num_moves) * 2.0  # 1.0 to 3.0
            else:
                position_weight = 1.0
            
            loss = self.train_on_move(
                fen_before=move.fen_before,
                fen_after=move.fen_after,
                material_change=move.material_change,
                game_outcome=move.game_outcome,
                is_capture=move.is_capture,
                move_number=move.move_number
            )
            total_loss += loss * position_weight
        
        self.games_trained += 1
        self.version += 1
        self.last_modified = datetime.now().isoformat()
        
        return {
            'loss': total_loss / max(1, len(moves)),
            'positions': len(moves)
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
                'hidden3': self.hidden3_size,
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
                'hidden2_size': self.hidden2_size,
                'hidden3_size': self.hidden3_size
            },
            'weights': {
                'w1': self.weights1, 'b1': self.biases1,
                'w2': self.weights2, 'b2': self.biases2,
                'w3': self.weights3, 'b3': self.biases3,
                'w4': self.weights4, 'b4': self.biases4
            }
        }
        
        with open(NN_WEIGHTS_PATH, 'w') as f:
            json.dump(data, f)
        
        print(f"[NeuralNet] Saved weights (v{self.version}, {self.positions_trained} positions)")
    
    def _load_weights(self) -> bool:
        """Load network weights from disk."""
        if not NN_WEIGHTS_PATH.exists():
            print("[NeuralNet] No saved weights found, using random initialization")
            return False
        
        try:
            with open(NN_WEIGHTS_PATH, 'r') as f:
                data = json.load(f)
            
            # Check if architecture matches
            hp = data.get('hyperparameters', {})
            if hp.get('hidden3_size') != self.hidden3_size:
                print("[NeuralNet] Architecture mismatch, using random initialization")
                return False
            
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
                self.weights4 = weights.get('w4', self.weights4)
                self.biases4 = weights.get('b4', self.biases4)
            
            print(f"[NeuralNet] Loaded weights (v{self.version}, {self.positions_trained} positions)")
            return True
            
        except Exception as e:
            print(f"[NeuralNet] Error loading weights: {e}")
            return False
    
    def reset_weights(self) -> None:
        """Reset network to random weights."""
        self.weights1 = self._he_init(self.input_size, self.hidden1_size)
        self.biases1 = [0.01] * self.hidden1_size
        self.weights2 = self._he_init(self.hidden1_size, self.hidden2_size)
        self.biases2 = [0.01] * self.hidden2_size
        self.weights3 = self._he_init(self.hidden2_size, self.hidden3_size)
        self.biases3 = [0.01] * self.hidden3_size
        self.weights4 = self._he_init(self.hidden3_size, self.output_size)
        self.biases4 = [0.0] * self.output_size
        
        self.games_trained = 0
        self.positions_trained = 0
        self.avg_loss = 0.0
        self.loss_history.clear()
        self.version = 0
        self.last_modified = datetime.now().isoformat()
        
        print("[NeuralNet] Weights reset to random initialization")
