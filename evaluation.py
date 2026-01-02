"""
Chess position evaluation module.

This module provides functions to evaluate chess board positions numerically,
with positive scores favoring White and negative scores favoring Black.
"""

import chess
import logging
from typing import Dict, Any, Optional

# Default values (used when no config provided)
from config import PIECE_VALUES, MOBILITY_WEIGHT, PAWN_STRUCTURE_BONUS, KING_SAFETY_PENALTY

logger = logging.getLogger(__name__)

# Piece values for threat calculation
THREAT_PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000  # Very high to prioritize king safety
}


def evaluate_board(board: chess.Board, config: Optional[Dict[str, Any]] = None) -> float:
    """
    Main evaluation function that takes a chess.Board and returns a numerical score.
    
    Args:
        board: chess.Board object representing the current position
        config: Optional configuration dict with piece_values, mobility_weight, etc.
        
    Returns:
        float: Position evaluation score (positive favors White, negative favors Black)
    """
    if board.is_checkmate():
        return -10000.0 if board.turn == chess.WHITE else 10000.0
    
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0
    
    # Get config values or use defaults
    piece_values = config.get('piece_values', PIECE_VALUES) if config else PIECE_VALUES
    mobility_weight = config.get('mobility_weight', MOBILITY_WEIGHT) if config else MOBILITY_WEIGHT
    king_safety_penalty = config.get('king_safety_penalty', KING_SAFETY_PENALTY) if config else KING_SAFETY_PENALTY
    
    # Calculate components
    material_score = calculate_material_balance(board, piece_values)
    mobility_score = assess_mobility(board, mobility_weight)
    pawn_structure_score = evaluate_pawn_structure(board)
    king_safety_score = assess_king_safety(board, king_safety_penalty)
    
    # CRITICAL: Add threat detection - penalize hanging pieces heavily
    threat_score = evaluate_threats(board)
    
    return material_score + mobility_score + pawn_structure_score + king_safety_score + threat_score


def evaluate_threats(board: chess.Board) -> float:
    """
    Evaluate tactical threats - hanging pieces and undefended attacks.
    
    This is CRITICAL for avoiding blunders like leaving a queen hanging.
    Returns a score adjustment (negative if we have hanging pieces, positive if opponent does).
    """
    white_threat_score = _evaluate_side_threats(board, chess.WHITE)
    black_threat_score = _evaluate_side_threats(board, chess.BLACK)
    
    # Return from white's perspective
    return white_threat_score - black_threat_score


def _evaluate_side_threats(board: chess.Board, color: chess.Color) -> float:
    """
    Evaluate threats for one side.
    
    Returns negative score for hanging pieces (bad), positive for attacking enemy pieces.
    """
    score = 0.0
    enemy_color = not color
    
    # Check each of our pieces (except king - king safety is handled separately)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != color:
            continue
        
        # Skip king - it's always "attacked" in some sense
        if piece.piece_type == chess.KING:
            continue
        
        piece_value = THREAT_PIECE_VALUES.get(piece.piece_type, 0)
        
        # Is this piece attacked?
        attackers = board.attackers(enemy_color, square)
        if attackers:
            # Is it defended?
            defenders = board.attackers(color, square)
            
            if not defenders:
                # HANGING PIECE - very bad!
                # Penalize based on piece value
                score -= piece_value * 0.9  # Almost full value penalty
            else:
                # Piece is attacked and defended - check if trade is bad
                # Find the least valuable attacker
                min_attacker_value = float('inf')
                for attacker_sq in attackers:
                    attacker = board.piece_at(attacker_sq)
                    if attacker:
                        attacker_value = THREAT_PIECE_VALUES.get(attacker.piece_type, 0)
                        min_attacker_value = min(min_attacker_value, attacker_value)
                
                # If we can be captured by a less valuable piece, that's bad
                if min_attacker_value < piece_value:
                    # Penalty proportional to the value difference
                    score -= (piece_value - min_attacker_value) * 0.5
    
    # Check for attacks on enemy pieces (opportunities)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != enemy_color:
            continue
        
        # Skip king
        if piece.piece_type == chess.KING:
            continue
        
        piece_value = THREAT_PIECE_VALUES.get(piece.piece_type, 0)
        
        # Can we attack this piece?
        our_attackers = board.attackers(color, square)
        if our_attackers:
            # Is it defended?
            their_defenders = board.attackers(enemy_color, square)
            
            if not their_defenders:
                # Enemy has a hanging piece - good for us!
                score += piece_value * 0.3  # Bonus for attacking hanging pieces
            else:
                # Check if we can win material
                min_our_attacker = float('inf')
                for attacker_sq in our_attackers:
                    attacker = board.piece_at(attacker_sq)
                    if attacker:
                        attacker_value = THREAT_PIECE_VALUES.get(attacker.piece_type, 0)
                        min_our_attacker = min(min_our_attacker, attacker_value)
                
                # If we can capture with a less valuable piece, that's good
                if min_our_attacker < piece_value:
                    score += (piece_value - min_our_attacker) * 0.2
    
    return score


def calculate_material_balance(board: chess.Board, piece_values: Dict[str, int] = None) -> float:
    """Calculate the material balance using configurable piece values."""
    if piece_values is None:
        piece_values = PIECE_VALUES
    
    piece_type_map = {
        chess.PAWN: 'pawn',
        chess.KNIGHT: 'knight',
        chess.BISHOP: 'bishop',
        chess.ROOK: 'rook',
        chess.QUEEN: 'queen',
        chess.KING: 'king'
    }
    
    white_material = 0.0
    black_material = 0.0
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            piece_name = piece_type_map[piece.piece_type]
            value = piece_values.get(piece_name, 0)
            if piece.color == chess.WHITE:
                white_material += value
            else:
                black_material += value
    
    return white_material - black_material


def assess_mobility(board: chess.Board, mobility_weight: float = None) -> float:
    """Assess mobility by counting legal moves."""
    if mobility_weight is None:
        mobility_weight = MOBILITY_WEIGHT
    
    # Count moves for current side
    current_moves = len(list(board.legal_moves))
    
    # Estimate opponent moves (simplified)
    if board.turn == chess.WHITE:
        white_moves = current_moves
        # Make a null move to count black's moves approximately
        board_copy = board.copy()
        board_copy.turn = chess.BLACK
        black_moves = len(list(board_copy.legal_moves))
    else:
        black_moves = current_moves
        board_copy = board.copy()
        board_copy.turn = chess.WHITE
        white_moves = len(list(board_copy.legal_moves))
    
    return (white_moves - black_moves) * mobility_weight


def evaluate_pawn_structure(board: chess.Board) -> float:
    """Evaluate pawn structure including doubled, isolated, and passed pawns."""
    white_pawns = board.pieces(chess.PAWN, chess.WHITE)
    black_pawns = board.pieces(chess.PAWN, chess.BLACK)
    
    white_score = _evaluate_side_pawns(white_pawns, black_pawns, chess.WHITE)
    black_score = _evaluate_side_pawns(black_pawns, white_pawns, chess.BLACK)
    
    return white_score - black_score


def _evaluate_side_pawns(own_pawns: chess.SquareSet, enemy_pawns: chess.SquareSet, 
                         color: chess.Color) -> float:
    """Evaluate pawn structure for one side."""
    score = 0.0
    
    # Group pawns by file
    pawn_files = {}
    for square in own_pawns:
        file = chess.square_file(square)
        if file not in pawn_files:
            pawn_files[file] = []
        pawn_files[file].append(square)
    
    # Check for doubled pawns
    for file, pawns in pawn_files.items():
        if len(pawns) > 1:
            score += (len(pawns) - 1) * PAWN_STRUCTURE_BONUS['doubled_pawn']
    
    # Check each pawn
    for square in own_pawns:
        file = chess.square_file(square)
        
        # Isolated pawn check
        has_neighbor = False
        for adj_file in [file - 1, file + 1]:
            if 0 <= adj_file <= 7 and adj_file in pawn_files:
                has_neighbor = True
                break
        if not has_neighbor:
            score += PAWN_STRUCTURE_BONUS['isolated_pawn']
        
        # Passed pawn check
        if _is_passed_pawn(square, enemy_pawns, color):
            score += PAWN_STRUCTURE_BONUS['passed_pawn']
    
    return score


def _is_passed_pawn(square: chess.Square, enemy_pawns: chess.SquareSet, color: chess.Color) -> bool:
    """Check if a pawn is passed."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    blocking_files = [f for f in [file - 1, file, file + 1] if 0 <= f <= 7]
    
    if color == chess.WHITE:
        blocking_ranks = range(rank + 1, 8)
    else:
        blocking_ranks = range(0, rank)
    
    for enemy_square in enemy_pawns:
        enemy_file = chess.square_file(enemy_square)
        enemy_rank = chess.square_rank(enemy_square)
        if enemy_file in blocking_files and enemy_rank in blocking_ranks:
            return False
    
    return True


def assess_king_safety(board: chess.Board, king_safety_penalty: Dict[str, int] = None) -> float:
    """Assess king safety factors."""
    if king_safety_penalty is None:
        king_safety_penalty = KING_SAFETY_PENALTY
    
    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    
    white_safety = _evaluate_king_safety(board, white_king, chess.WHITE, king_safety_penalty) if white_king else 0
    black_safety = _evaluate_king_safety(board, black_king, chess.BLACK, king_safety_penalty) if black_king else 0
    
    return white_safety - black_safety


def _evaluate_king_safety(board: chess.Board, king_square: chess.Square, 
                          color: chess.Color, penalties: Dict[str, int]) -> float:
    """Evaluate king safety for one side."""
    score = 0.0
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    
    # King in center penalty
    if king_file in [3, 4] and king_rank in [3, 4]:
        score += penalties.get('king_in_center', -50)
    
    # Open files near king
    for f in [king_file - 1, king_file, king_file + 1]:
        if 0 <= f <= 7:
            has_pawn = False
            for r in range(8):
                piece = board.piece_at(chess.square(f, r))
                if piece and piece.piece_type == chess.PAWN:
                    has_pawn = True
                    break
            if not has_pawn:
                score += penalties.get('open_file_near_king', -30)
    
    return score


# For backward compatibility
def get_evaluation_breakdown(board: chess.Board, config: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Get detailed breakdown of position evaluation components."""
    piece_values = config.get('piece_values', PIECE_VALUES) if config else PIECE_VALUES
    mobility_weight = config.get('mobility_weight', MOBILITY_WEIGHT) if config else MOBILITY_WEIGHT
    king_safety_penalty = config.get('king_safety_penalty', KING_SAFETY_PENALTY) if config else KING_SAFETY_PENALTY
    
    material = calculate_material_balance(board, piece_values)
    mobility = assess_mobility(board, mobility_weight)
    pawn_structure = evaluate_pawn_structure(board)
    king_safety = assess_king_safety(board, king_safety_penalty)
    
    return {
        'total': material + mobility + pawn_structure + king_safety,
        'material': material,
        'mobility': mobility,
        'pawn_structure': pawn_structure,
        'king_safety': king_safety
    }
