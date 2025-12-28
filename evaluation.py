"""
Chess position evaluation module.

This module provides functions to evaluate chess board positions numerically,
with positive scores favoring White and negative scores favoring Black.
"""

import chess
import logging
from typing import Dict, Any

# Handle imports for both module and standalone execution
try:
    from config import PIECE_VALUES, MOBILITY_WEIGHT, PAWN_STRUCTURE_BONUS, KING_SAFETY_PENALTY
except ImportError:
    from config import PIECE_VALUES, MOBILITY_WEIGHT, PAWN_STRUCTURE_BONUS, KING_SAFETY_PENALTY

# Set up logging for evaluation decisions
logger = logging.getLogger(__name__)


def evaluate_board(board: chess.Board) -> float:
    """
    Main evaluation function that takes a chess.Board and returns a numerical score.
    
    Args:
        board: chess.Board object representing the current position
        
    Returns:
        float: Position evaluation score (positive favors White, negative favors Black)
    """
    if board.is_checkmate():
        # Return extreme values for checkmate
        if board.turn == chess.WHITE:
            # White is checkmated, Black wins
            logger.info("Position evaluation: White is checkmated")
            return -10000.0
        else:
            # Black is checkmated, White wins
            logger.info("Position evaluation: Black is checkmated")
            return 10000.0
    
    if board.is_stalemate() or board.is_insufficient_material():
        logger.info("Position evaluation: Draw (stalemate or insufficient material)")
        return 0.0
    
    # Calculate material balance
    material_score = calculate_material_balance(board)
    
    # Calculate mobility assessment
    mobility_score = assess_mobility(board)
    
    # Calculate pawn structure evaluation
    pawn_structure_score = evaluate_pawn_structure(board)
    
    # Calculate king safety assessment
    king_safety_score = assess_king_safety(board)
    
    # Log the evaluation components
    logger.debug(f"Material balance: {material_score}")
    logger.debug(f"Mobility assessment: {mobility_score}")
    logger.debug(f"Pawn structure: {pawn_structure_score}")
    logger.debug(f"King safety: {king_safety_score}")
    
    total_score = material_score + mobility_score + pawn_structure_score + king_safety_score
    
    logger.debug(f"Total position evaluation: {total_score}")
    return total_score


def get_evaluation_breakdown(board: chess.Board) -> Dict[str, float]:
    """
    Get detailed breakdown of position evaluation components.
    
    Args:
        board: chess.Board object representing the current position
        
    Returns:
        Dict[str, float]: Dictionary with evaluation component scores
    """
    if board.is_checkmate():
        # Return extreme values for checkmate
        if board.turn == chess.WHITE:
            return {
                'total': -10000.0,
                'material': 0.0,
                'mobility': 0.0,
                'pawn_structure': 0.0,
                'king_safety': 0.0,
                'checkmate': -10000.0
            }
        else:
            return {
                'total': 10000.0,
                'material': 0.0,
                'mobility': 0.0,
                'pawn_structure': 0.0,
                'king_safety': 0.0,
                'checkmate': 10000.0
            }
    
    if board.is_stalemate() or board.is_insufficient_material():
        return {
            'total': 0.0,
            'material': 0.0,
            'mobility': 0.0,
            'pawn_structure': 0.0,
            'king_safety': 0.0,
            'draw': 0.0
        }
    
    # Calculate individual components
    material_score = calculate_material_balance(board)
    mobility_score = assess_mobility(board)
    pawn_structure_score = evaluate_pawn_structure(board)
    king_safety_score = assess_king_safety(board)
    
    total_score = material_score + mobility_score + pawn_structure_score + king_safety_score
    
    return {
        'total': total_score,
        'material': material_score,
        'mobility': mobility_score,
        'pawn_structure': pawn_structure_score,
        'king_safety': king_safety_score
    }


def calculate_material_balance(board: chess.Board) -> float:
    """
    Calculate the material balance using configurable piece values.
    
    Args:
        board: chess.Board object representing the current position
        
    Returns:
        float: Material balance score (positive favors White)
    """
    white_material = 0.0
    black_material = 0.0
    
    # Count pieces for both sides
    piece_counts = {
        chess.WHITE: {'pawn': 0, 'knight': 0, 'bishop': 0, 'rook': 0, 'queen': 0, 'king': 0},
        chess.BLACK: {'pawn': 0, 'knight': 0, 'bishop': 0, 'rook': 0, 'queen': 0, 'king': 0}
    }
    
    # Map chess piece types to our config keys
    piece_type_map = {
        chess.PAWN: 'pawn',
        chess.KNIGHT: 'knight',
        chess.BISHOP: 'bishop',
        chess.ROOK: 'rook',
        chess.QUEEN: 'queen',
        chess.KING: 'king'
    }
    
    # Count all pieces on the board
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            piece_name = piece_type_map[piece.piece_type]
            piece_counts[piece.color][piece_name] += 1
    
    # Calculate material values
    for piece_name, value in PIECE_VALUES.items():
        white_count = piece_counts[chess.WHITE][piece_name]
        black_count = piece_counts[chess.BLACK][piece_name]
        
        white_material += white_count * value
        black_material += black_count * value
        
        if white_count > 0 or black_count > 0:
            logger.debug(f"{piece_name.capitalize()}s - White: {white_count}, Black: {black_count}")
    
    material_balance = white_material - black_material
    logger.debug(f"White material: {white_material}, Black material: {black_material}")
    
    return material_balance


# Placeholder functions for future subtasks
def assess_mobility(board: chess.Board) -> float:
    """
    Assess mobility by counting legal moves and applying weight multipliers.
    
    Args:
        board: chess.Board object representing the current position
        
    Returns:
        float: Mobility score (positive favors White, negative favors Black)
    """
    # Count legal moves for White and Black
    white_moves = 0
    black_moves = 0
    
    # Count moves for the current side to move
    current_moves = len(list(board.legal_moves))
    
    if board.turn == chess.WHITE:
        white_moves = current_moves
        # To count Black's moves, we need to make a move and then count
        # Use a copy to avoid modifying the original board
        temp_board = board.copy()
        legal_moves = list(temp_board.legal_moves)
        if legal_moves:
            temp_board.push(legal_moves[0])  # Make any legal move
            black_moves = len(list(temp_board.legal_moves))
        else:
            black_moves = 0
    else:
        black_moves = current_moves
        # To count White's moves, we need to make a move and then count
        temp_board = board.copy()
        legal_moves = list(temp_board.legal_moves)
        if legal_moves:
            temp_board.push(legal_moves[0])  # Make any legal move
            white_moves = len(list(temp_board.legal_moves))
        else:
            white_moves = 0
    
    # Calculate mobility difference (White - Black)
    mobility_difference = white_moves - black_moves
    
    # Apply the mobility weight from configuration
    mobility_score = mobility_difference * MOBILITY_WEIGHT
    
    logger.debug(f"White moves: {white_moves}, Black moves: {black_moves}")
    logger.debug(f"Mobility difference: {mobility_difference}, Weight: {MOBILITY_WEIGHT}")
    
    return mobility_score


def evaluate_pawn_structure(board: chess.Board) -> float:
    """
    Evaluate pawn structure including doubled, isolated, and passed pawns.
    
    Args:
        board: chess.Board object representing the current position
        
    Returns:
        float: Pawn structure score (positive favors White, negative favors Black)
    """
    white_pawn_score = 0.0
    black_pawn_score = 0.0
    
    # Get pawn positions for both sides
    white_pawns = board.pieces(chess.PAWN, chess.WHITE)
    black_pawns = board.pieces(chess.PAWN, chess.BLACK)
    
    # Evaluate White pawns
    white_pawn_score += _evaluate_side_pawns(board, white_pawns, black_pawns, chess.WHITE)
    
    # Evaluate Black pawns
    black_pawn_score += _evaluate_side_pawns(board, black_pawns, white_pawns, chess.BLACK)
    
    # Return difference (positive favors White)
    total_pawn_score = white_pawn_score - black_pawn_score
    
    logger.debug(f"White pawn structure: {white_pawn_score}, Black pawn structure: {black_pawn_score}")
    
    return total_pawn_score


def _evaluate_side_pawns(board: chess.Board, own_pawns: chess.SquareSet, 
                        enemy_pawns: chess.SquareSet, color: chess.Color) -> float:
    """
    Evaluate pawn structure for one side.
    
    Args:
        board: chess.Board object
        own_pawns: SquareSet of pawns for the side being evaluated
        enemy_pawns: SquareSet of enemy pawns
        color: Color of the side being evaluated
        
    Returns:
        float: Pawn structure score for this side
    """
    score = 0.0
    
    # Group pawns by file for analysis
    pawn_files = {}
    for square in own_pawns:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if file not in pawn_files:
            pawn_files[file] = []
        pawn_files[file].append((square, rank))
    
    # Check for doubled pawns
    for file, pawns_on_file in pawn_files.items():
        if len(pawns_on_file) > 1:
            # Multiple pawns on same file = doubled pawns
            doubled_count = len(pawns_on_file) - 1  # First pawn is normal, rest are doubled
            score += doubled_count * PAWN_STRUCTURE_BONUS['doubled_pawn']
            logger.debug(f"{'White' if color == chess.WHITE else 'Black'} doubled pawns on file {chess.FILE_NAMES[file]}: {doubled_count}")
    
    # Check each pawn for isolation, backward status, and passed status
    for square in own_pawns:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        
        # Check for isolated pawns
        if _is_isolated_pawn(own_pawns, file):
            score += PAWN_STRUCTURE_BONUS['isolated_pawn']
            logger.debug(f"{'White' if color == chess.WHITE else 'Black'} isolated pawn on {chess.square_name(square)}")
        
        # Check for passed pawns
        if _is_passed_pawn(square, own_pawns, enemy_pawns, color):
            score += PAWN_STRUCTURE_BONUS['passed_pawn']
            logger.debug(f"{'White' if color == chess.WHITE else 'Black'} passed pawn on {chess.square_name(square)}")
        
        # Check for backward pawns
        if _is_backward_pawn(square, own_pawns, enemy_pawns, color):
            score += PAWN_STRUCTURE_BONUS['backward_pawn']
            logger.debug(f"{'White' if color == chess.WHITE else 'Black'} backward pawn on {chess.square_name(square)}")
    
    # Check for connected pawns
    connected_bonus = _count_connected_pawns(own_pawns) * PAWN_STRUCTURE_BONUS['connected_pawns']
    score += connected_bonus
    if connected_bonus > 0:
        logger.debug(f"{'White' if color == chess.WHITE else 'Black'} connected pawns bonus: {connected_bonus}")
    
    return score


def _is_isolated_pawn(own_pawns: chess.SquareSet, file: int) -> bool:
    """Check if a pawn is isolated (no friendly pawns on adjacent files)."""
    adjacent_files = []
    if file > 0:
        adjacent_files.append(file - 1)
    if file < 7:
        adjacent_files.append(file + 1)
    
    for square in own_pawns:
        pawn_file = chess.square_file(square)
        if pawn_file in adjacent_files:
            return False
    
    return True


def _is_passed_pawn(square: chess.Square, own_pawns: chess.SquareSet, 
                   enemy_pawns: chess.SquareSet, color: chess.Color) -> bool:
    """Check if a pawn is passed (no enemy pawns can stop its advance)."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    # Define the files that could block this pawn (same file and adjacent files)
    blocking_files = [file]
    if file > 0:
        blocking_files.append(file - 1)
    if file < 7:
        blocking_files.append(file + 1)
    
    # Define the ranks that matter for blocking
    if color == chess.WHITE:
        # White pawn: check ranks ahead (higher rank numbers)
        blocking_ranks = range(rank + 1, 8)
    else:
        # Black pawn: check ranks ahead (lower rank numbers)
        blocking_ranks = range(0, rank)
    
    # Check if any enemy pawn can block this pawn's advance
    for enemy_square in enemy_pawns:
        enemy_file = chess.square_file(enemy_square)
        enemy_rank = chess.square_rank(enemy_square)
        
        if enemy_file in blocking_files and enemy_rank in blocking_ranks:
            return False
    
    return True


def _is_backward_pawn(square: chess.Square, own_pawns: chess.SquareSet, 
                     enemy_pawns: chess.SquareSet, color: chess.Color) -> bool:
    """Check if a pawn is backward (cannot advance safely and has no pawn support)."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    # Check if pawn can advance one square
    if color == chess.WHITE:
        advance_square = chess.square(file, rank + 1) if rank < 7 else None
    else:
        advance_square = chess.square(file, rank - 1) if rank > 0 else None
    
    if advance_square is None:
        return False  # Pawn is on the last rank
    
    # Check if the advance square is attacked by enemy pawns
    for enemy_square in enemy_pawns:
        enemy_file = chess.square_file(enemy_square)
        enemy_rank = chess.square_rank(enemy_square)
        
        # Check if enemy pawn attacks the advance square
        if color == chess.WHITE:
            # Enemy is Black, attacks diagonally down
            if enemy_rank == rank + 2 and abs(enemy_file - file) == 1:
                # Check if this pawn has support from friendly pawns
                if not _has_pawn_support(square, own_pawns, color):
                    return True
        else:
            # Enemy is White, attacks diagonally up
            if enemy_rank == rank and abs(enemy_file - file) == 1:
                # Check if this pawn has support from friendly pawns
                if not _has_pawn_support(square, own_pawns, color):
                    return True
    
    return False


def _has_pawn_support(square: chess.Square, own_pawns: chess.SquareSet, color: chess.Color) -> bool:
    """Check if a pawn has support from friendly pawns on adjacent files."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    # Check adjacent files for supporting pawns
    for own_square in own_pawns:
        own_file = chess.square_file(own_square)
        own_rank = chess.square_rank(own_square)
        
        # Check if this is a supporting pawn (on adjacent file, behind or same rank)
        if abs(own_file - file) == 1:
            if color == chess.WHITE:
                # For White, support comes from same or lower ranks
                if own_rank <= rank:
                    return True
            else:
                # For Black, support comes from same or higher ranks
                if own_rank >= rank:
                    return True
    
    return False


def _count_connected_pawns(own_pawns: chess.SquareSet) -> int:
    """Count the number of connected pawn pairs."""
    connected_count = 0
    
    for square in own_pawns:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        
        # Check for pawns on adjacent files and same rank (horizontally connected)
        for other_square in own_pawns:
            if other_square == square:
                continue
                
            other_file = chess.square_file(other_square)
            other_rank = chess.square_rank(other_square)
            
            # Check if pawns are connected (adjacent files, same rank)
            if abs(other_file - file) == 1 and other_rank == rank:
                connected_count += 1
    
    # Each connection is counted twice (once for each pawn), so divide by 2
    return connected_count // 2


def assess_king_safety(board: chess.Board) -> float:
    """
    Assess king safety factors including open files and nearby threats.
    
    Args:
        board: chess.Board object representing the current position
        
    Returns:
        float: King safety score (positive favors White, negative favors Black)
    """
    white_king_safety = 0.0
    black_king_safety = 0.0
    
    # Find king positions
    white_king_square = board.king(chess.WHITE)
    black_king_square = board.king(chess.BLACK)
    
    if white_king_square is not None:
        white_king_safety += _evaluate_king_safety(board, white_king_square, chess.WHITE)
    
    if black_king_square is not None:
        black_king_safety += _evaluate_king_safety(board, black_king_square, chess.BLACK)
    
    # Return difference (positive favors White)
    total_king_safety = white_king_safety - black_king_safety
    
    logger.debug(f"White king safety: {white_king_safety}, Black king safety: {black_king_safety}")
    
    return total_king_safety


def _evaluate_king_safety(board: chess.Board, king_square: chess.Square, color: chess.Color) -> float:
    """
    Evaluate king safety for one side.
    
    Args:
        board: chess.Board object
        king_square: Square where the king is located
        color: Color of the king being evaluated
        
    Returns:
        float: King safety score for this side (higher is safer)
    """
    safety_score = 0.0
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    
    # Check if king is in the center (dangerous)
    if _is_king_in_center(king_square):
        safety_score += KING_SAFETY_PENALTY['king_in_center']
        logger.debug(f"{'White' if color == chess.WHITE else 'Black'} king in center penalty")
    
    # Check for open files near the king
    open_file_penalty = _check_open_files_near_king(board, king_square, color)
    safety_score += open_file_penalty
    
    # Check for weak pawn shield
    weak_shield_penalty = _check_weak_pawn_shield(board, king_square, color)
    safety_score += weak_shield_penalty
    
    # Check for enemy pieces near the king
    enemy_pieces_penalty = _check_enemy_pieces_near_king(board, king_square, color)
    safety_score += enemy_pieces_penalty
    
    return safety_score


def _is_king_in_center(king_square: chess.Square) -> bool:
    """Check if the king is in the center files (d, e)."""
    king_file = chess.square_file(king_square)
    return king_file in [3, 4]  # d-file = 3, e-file = 4


def _check_open_files_near_king(board: chess.Board, king_square: chess.Square, color: chess.Color) -> float:
    """Check for open files near the king."""
    penalty = 0.0
    king_file = chess.square_file(king_square)
    
    # Check the king's file and adjacent files
    files_to_check = [king_file]
    if king_file > 0:
        files_to_check.append(king_file - 1)
    if king_file < 7:
        files_to_check.append(king_file + 1)
    
    for file in files_to_check:
        if _is_file_open(board, file):
            penalty += KING_SAFETY_PENALTY['open_file_near_king']
            logger.debug(f"{'White' if color == chess.WHITE else 'Black'} king has open file {chess.FILE_NAMES[file]} nearby")
    
    return penalty


def _is_file_open(board: chess.Board, file: int) -> bool:
    """Check if a file has no pawns on it."""
    for rank in range(8):
        square = chess.square(file, rank)
        piece = board.piece_at(square)
        if piece is not None and piece.piece_type == chess.PAWN:
            return False
    return True


def _check_weak_pawn_shield(board: chess.Board, king_square: chess.Square, color: chess.Color) -> float:
    """Check for weak pawn shield in front of the king."""
    penalty = 0.0
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    
    # Define the ranks to check for pawn shield
    if color == chess.WHITE:
        # For White king, check ranks in front (higher rank numbers)
        shield_ranks = [king_rank + 1, king_rank + 2] if king_rank < 6 else [king_rank + 1] if king_rank < 7 else []
    else:
        # For Black king, check ranks in front (lower rank numbers)
        shield_ranks = [king_rank - 1, king_rank - 2] if king_rank > 1 else [king_rank - 1] if king_rank > 0 else []
    
    # Check files around the king for pawn shield
    files_to_check = [king_file]
    if king_file > 0:
        files_to_check.append(king_file - 1)
    if king_file < 7:
        files_to_check.append(king_file + 1)
    
    missing_shield_count = 0
    for file in files_to_check:
        has_shield_pawn = False
        for rank in shield_ranks:
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece is not None and piece.piece_type == chess.PAWN and piece.color == color:
                has_shield_pawn = True
                break
        
        if not has_shield_pawn:
            missing_shield_count += 1
    
    if missing_shield_count > 0:
        penalty += missing_shield_count * KING_SAFETY_PENALTY['weak_pawn_shield']
        logger.debug(f"{'White' if color == chess.WHITE else 'Black'} king has weak pawn shield: {missing_shield_count} missing")
    
    return penalty


def _check_enemy_pieces_near_king(board: chess.Board, king_square: chess.Square, color: chess.Color) -> float:
    """Check for enemy pieces near the king."""
    penalty = 0.0
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    enemy_color = not color
    
    # Check squares around the king (3x3 area plus extended area)
    danger_squares = []
    
    # Add immediate squares around king
    for file_offset in [-1, 0, 1]:
        for rank_offset in [-1, 0, 1]:
            if file_offset == 0 and rank_offset == 0:
                continue  # Skip the king's own square
            
            new_file = king_file + file_offset
            new_rank = king_rank + rank_offset
            
            if 0 <= new_file <= 7 and 0 <= new_rank <= 7:
                danger_squares.append(chess.square(new_file, new_rank))
    
    # Add extended area (2 squares away)
    for file_offset in [-2, -1, 0, 1, 2]:
        for rank_offset in [-2, -1, 0, 1, 2]:
            if abs(file_offset) <= 1 and abs(rank_offset) <= 1:
                continue  # Already added immediate squares
            
            new_file = king_file + file_offset
            new_rank = king_rank + rank_offset
            
            if 0 <= new_file <= 7 and 0 <= new_rank <= 7:
                danger_squares.append(chess.square(new_file, new_rank))
    
    # Count enemy pieces in danger area
    enemy_pieces_count = 0
    for square in danger_squares:
        piece = board.piece_at(square)
        if piece is not None and piece.color == enemy_color and piece.piece_type != chess.PAWN:
            enemy_pieces_count += 1
    
    if enemy_pieces_count > 0:
        penalty += enemy_pieces_count * KING_SAFETY_PENALTY['enemy_pieces_near_king']
        logger.debug(f"{'White' if color == chess.WHITE else 'Black'} king has {enemy_pieces_count} enemy pieces nearby")
    
    return penalty


if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.DEBUG)
    
    print("Testing evaluation function...")
    
    # Test 1: Starting position
    board = chess.Board()
    score = evaluate_board(board)
    print(f"Starting position evaluation: {score}")
    print()
    
    # Test 2: After some moves
    board.push_san("e4")
    board.push_san("e5")
    score = evaluate_board(board)
    print(f"After 1.e4 e5 evaluation: {score}")
    print()
    
    # Test 3: Position with material imbalance
    board = chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 4 4")
    score = evaluate_board(board)
    print(f"Symmetric development position evaluation: {score}")
    print()
    
    # Test 4: Position with passed pawn
    board = chess.Board("8/8/8/3P4/8/8/8/8 w - - 0 1")
    score = evaluate_board(board)
    print(f"White passed pawn position evaluation: {score}")
    print()
    
    print("Comprehensive evaluation framework test completed!")