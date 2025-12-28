"""
Chess search algorithm module.

This module implements the minimax search algorithm with alpha-beta pruning
for move selection in chess positions.
"""

import chess
import logging
import time
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass

# Handle imports for both module and standalone execution
from evaluation import evaluate_board
from config import ChessConfig, SEARCH_DEPTH, PIECE_VALUES

# Set up logging for search decisions
logger = logging.getLogger(__name__)


@dataclass
class SearchStats:
    """Statistics tracking for search algorithm performance."""
    nodes_evaluated: int = 0
    positions_evaluated: int = 0
    search_depth_reached: int = 0
    time_elapsed: float = 0.0
    best_move: Optional[chess.Move] = None
    best_score: float = 0.0
    alpha_beta_cutoffs: int = 0
    move_ordering_hits: int = 0
    
    def reset(self):
        """Reset all statistics to initial values."""
        self.nodes_evaluated = 0
        self.positions_evaluated = 0
        self.search_depth_reached = 0
        self.time_elapsed = 0.0
        self.best_move = None
        self.best_score = 0.0
        self.alpha_beta_cutoffs = 0
        self.move_ordering_hits = 0


class ChessSearchEngine:
    """Chess search engine implementing minimax with alpha-beta pruning."""
    
    def __init__(self, config: Optional[ChessConfig] = None):
        """Initialize the search engine with configuration."""
        self.config = config or ChessConfig()
        self.stats = SearchStats()
        self.logger = logging.getLogger(f"ChessSearchEngine")
        self.search_cancelled = False
        
    def find_best_move(self, board: chess.Board, depth: Optional[int] = None, 
                      time_limit: Optional[float] = None, 
                      game_id: Optional[str] = None) -> chess.Move:
        """
        Find the best move for the current position using minimax search.
        
        Args:
            board: chess.Board object representing the current position
            depth: Maximum search depth (uses config default if None)
            time_limit: Maximum time in seconds for search (None for no limit)
            
        Returns:
            chess.Move: The best move found by the search
            
        Raises:
            ValueError: If no legal moves are available
        """
        start_time = time.time()
        self.stats.reset()
        self.search_cancelled = False
        
        # Use configured depth if not specified
        if depth is None:
            depth = self.config.get_parameter('search_depth')
        
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("No legal moves available")
        
        self.logger.info(f"Starting search: depth={depth}, time_limit={time_limit}, moves={len(legal_moves)}")
        
        # If only one legal move, return it immediately
        if len(legal_moves) == 1:
            self.stats.best_move = legal_moves[0]
            self.stats.time_elapsed = time.time() - start_time
            self.logger.info(f"Only one legal move: {legal_moves[0]}")
            return legal_moves[0]
        
        # Use iterative deepening if time limit is specified
        if time_limit is not None:
            return self._iterative_deepening_search(board, depth, time_limit, start_time, game_id)
        else:
            return self._fixed_depth_search(board, depth, start_time, time_limit, game_id)
    
    def _fixed_depth_search(self, board: chess.Board, depth: int, start_time: float, 
                           time_limit: Optional[float], game_id: Optional[str] = None) -> chess.Move:
        """
        Perform a fixed-depth search without iterative deepening.
        
        Args:
            board: Current board position
            depth: Search depth
            start_time: Search start time
            time_limit: Time limit for search
            
        Returns:
            chess.Move: Best move found
        """
        legal_moves = list(board.legal_moves)
        
        # Order moves for better alpha-beta pruning
        ordered_moves = self._order_moves(board, legal_moves)
        
        best_move = None
        best_score = float('-inf') if board.turn == chess.WHITE else float('inf')
        
        # Search each legal move
        for move in ordered_moves:
            # Check time limit
            if time_limit and (time.time() - start_time) > time_limit:
                self.search_cancelled = True
                self.logger.warning("Search cancelled due to time limit")
                break
            
            # Make the move
            board.push(move)
            
            # Search the resulting position
            score = self._minimax(board, depth - 1, float('-inf'), float('inf'), 
                                not board.turn, start_time, time_limit)
            
            # Undo the move
            board.pop()
            
            self.logger.debug(f"Move {move}: score = {score}")
            
            # Update best move based on whose turn it is
            if board.turn == chess.WHITE:
                if score > best_score:
                    best_score = score
                    best_move = move
            else:
                if score < best_score:
                    best_score = score
                    best_move = move
        
        # Ensure we have a move to return
        if best_move is None:
            best_move = legal_moves[0]
            self.logger.warning("No best move found, using first legal move")
        
        # Update statistics
        self.stats.best_move = best_move
        self.stats.best_score = best_score
        self.stats.search_depth_reached = depth
        self.stats.time_elapsed = time.time() - start_time
        
        self.logger.info(f"Search completed: move={best_move}, score={best_score:.2f}, "
                        f"nodes={self.stats.nodes_evaluated}, time={self.stats.time_elapsed:.3f}s, "
                        f"cutoffs={self.stats.alpha_beta_cutoffs}")
        
        # Log search statistics if game_id is provided
        if game_id:
            try:
                from analytics import log_search_statistics
                log_search_statistics(game_id, board.fen(), self.get_search_stats())
            except ImportError:
                pass  # Analytics module not available
        
        return best_move
    
    def _iterative_deepening_search(self, board: chess.Board, max_depth: int, 
                                   time_limit: float, start_time: float, game_id: Optional[str] = None) -> chess.Move:
        """
        Perform iterative deepening search with time management.
        
        Args:
            board: Current board position
            max_depth: Maximum search depth
            time_limit: Time limit for search
            start_time: Search start time
            
        Returns:
            chess.Move: Best move found within time limit
        """
        legal_moves = list(board.legal_moves)
        best_move = legal_moves[0]  # Fallback move
        best_score = 0.0
        
        # Reserve some time for move execution and network latency
        search_time_limit = time_limit * 0.9  # Use 90% of available time
        
        self.logger.info(f"Starting iterative deepening: max_depth={max_depth}, "
                        f"time_limit={time_limit:.3f}s, search_limit={search_time_limit:.3f}s")
        
        # Iterative deepening loop
        for current_depth in range(1, max_depth + 1):
            # Check if we have enough time for this depth
            elapsed_time = time.time() - start_time
            if elapsed_time >= search_time_limit:
                self.logger.info(f"Time limit reached before depth {current_depth}")
                break
            
            # Estimate time needed for this depth (rough heuristic)
            if current_depth > 1:
                time_per_depth = elapsed_time / (current_depth - 1)
                estimated_time = time_per_depth * 4  # Assume 4x branching factor
                if elapsed_time + estimated_time > search_time_limit:
                    self.logger.info(f"Skipping depth {current_depth} due to time estimate")
                    break
            
            self.logger.debug(f"Searching at depth {current_depth}")
            
            # Reset search cancellation for this depth
            depth_cancelled = False
            
            # Order moves for better alpha-beta pruning
            ordered_moves = self._order_moves(board, legal_moves)
            
            current_best_move = None
            current_best_score = float('-inf') if board.turn == chess.WHITE else float('inf')
            
            # Search each legal move at current depth
            for move in ordered_moves:
                # Check time limit more frequently during iterative deepening
                if (time.time() - start_time) >= search_time_limit:
                    self.search_cancelled = True
                    depth_cancelled = True
                    self.logger.debug(f"Time limit reached during depth {current_depth}")
                    break
                
                # Make the move
                board.push(move)
                
                # Search the resulting position
                score = self._minimax(board, current_depth - 1, float('-inf'), float('inf'), 
                                    not board.turn, start_time, search_time_limit)
                
                # Undo the move
                board.pop()
                
                # If search was cancelled during this move, don't use the result
                if self.search_cancelled:
                    depth_cancelled = True
                    break
                
                self.logger.debug(f"Depth {current_depth}, Move {move}: score = {score}")
                
                # Update best move for current depth
                if board.turn == chess.WHITE:
                    if score > current_best_score:
                        current_best_score = score
                        current_best_move = move
                else:
                    if score < current_best_score:
                        current_best_score = score
                        current_best_move = move
            
            # If we completed this depth without cancellation, update the best move
            if not depth_cancelled and current_best_move is not None:
                best_move = current_best_move
                best_score = current_best_score
                self.stats.search_depth_reached = current_depth
                
                elapsed = time.time() - start_time
                self.logger.info(f"Completed depth {current_depth}: move={best_move}, "
                                f"score={best_score:.2f}, time={elapsed:.3f}s")
            else:
                self.logger.info(f"Depth {current_depth} incomplete due to time limit")
                break
        
        # Update final statistics
        self.stats.best_move = best_move
        self.stats.best_score = best_score
        self.stats.time_elapsed = time.time() - start_time
        
        self.logger.info(f"Iterative deepening completed: move={best_move}, score={best_score:.2f}, "
                        f"final_depth={self.stats.search_depth_reached}, "
                        f"nodes={self.stats.nodes_evaluated}, time={self.stats.time_elapsed:.3f}s, "
                        f"cutoffs={self.stats.alpha_beta_cutoffs}")
        
        # Log search statistics if game_id is provided
        if game_id:
            try:
                from analytics import log_search_statistics
                log_search_statistics(game_id, board.fen(), self.get_search_stats())
            except ImportError:
                pass  # Analytics module not available
        
        return best_move
    
    def _minimax(self, board: chess.Board, depth: int, alpha: float, beta: float,
                maximizing_player: bool, start_time: float, time_limit: Optional[float]) -> float:
        """
        Minimax algorithm with alpha-beta pruning.
        
        Args:
            board: Current board position
            depth: Remaining search depth
            alpha: Alpha value for pruning
            beta: Beta value for pruning
            maximizing_player: True if maximizing player (White), False if minimizing (Black)
            start_time: Search start time for time management
            time_limit: Maximum search time
            
        Returns:
            float: Evaluation score of the position
        """
        self.stats.nodes_evaluated += 1
        
        # Check time limit more frequently at higher depths
        if time_limit and (self.stats.nodes_evaluated % 100 == 0):  # Check every 100 nodes
            if (time.time() - start_time) > time_limit:
                self.search_cancelled = True
                return evaluate_board(board)
        
        # Terminal conditions
        if depth == 0 or board.is_game_over():
            self.stats.positions_evaluated += 1
            return evaluate_board(board)
        
        legal_moves = list(board.legal_moves)
        
        # Order moves for better alpha-beta pruning
        ordered_moves = self._order_moves(board, legal_moves)
        
        if maximizing_player:
            max_eval = float('-inf')
            for move in ordered_moves:
                board.push(move)
                eval_score = self._minimax(board, depth - 1, alpha, beta, False, start_time, time_limit)
                board.pop()
                
                # If search was cancelled, return current best
                if self.search_cancelled:
                    return max(max_eval, eval_score) if max_eval != float('-inf') else eval_score
                
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                
                # Alpha-beta pruning
                if beta <= alpha:
                    self.stats.alpha_beta_cutoffs += 1
                    break
            
            return max_eval
        else:
            min_eval = float('inf')
            for move in ordered_moves:
                board.push(move)
                eval_score = self._minimax(board, depth - 1, alpha, beta, True, start_time, time_limit)
                board.pop()
                
                # If search was cancelled, return current best
                if self.search_cancelled:
                    return min(min_eval, eval_score) if min_eval != float('inf') else eval_score
                
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                
                # Alpha-beta pruning
                if beta <= alpha:
                    self.stats.alpha_beta_cutoffs += 1
                    break
            
            return min_eval
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get current search statistics."""
        return {
            'nodes_evaluated': self.stats.nodes_evaluated,
            'positions_evaluated': self.stats.positions_evaluated,
            'search_depth_reached': self.stats.search_depth_reached,
            'time_elapsed': self.stats.time_elapsed,
            'best_move': str(self.stats.best_move) if self.stats.best_move else None,
            'best_score': self.stats.best_score,
            'alpha_beta_cutoffs': self.stats.alpha_beta_cutoffs,
            'move_ordering_hits': self.stats.move_ordering_hits,
            'search_cancelled': self.search_cancelled
        }
    
    def set_config(self, config: ChessConfig):
        """Update the configuration used by the search engine."""
        self.config = config
        self.logger.info("Search engine configuration updated")
    
    def _order_moves(self, board: chess.Board, moves: List[chess.Move]) -> List[chess.Move]:
        """
        Order moves for better alpha-beta pruning efficiency.
        
        Move ordering heuristics (in priority order):
        1. Captures (ordered by Most Valuable Victim - Least Valuable Attacker)
        2. Checks
        3. Castling moves
        4. Promotions
        5. Other moves (ordered by piece value of moving piece)
        
        Args:
            board: Current board position
            moves: List of legal moves to order
            
        Returns:
            List[chess.Move]: Ordered list of moves
        """
        def move_priority(move: chess.Move) -> Tuple[int, int, int]:
            """Calculate move priority for sorting (higher values = higher priority)."""
            priority = 0
            secondary = 0
            tertiary = 0
            
            # Get piece values for calculations
            piece_values = self.config.get_parameter('piece_values')
            
            # Check if move is a capture
            if board.is_capture(move):
                captured_piece = board.piece_at(move.to_square)
                moving_piece = board.piece_at(move.from_square)
                
                if captured_piece and moving_piece:
                    # MVV-LVA: Most Valuable Victim - Least Valuable Attacker
                    victim_value = self._get_piece_value(captured_piece.piece_type, piece_values)
                    attacker_value = self._get_piece_value(moving_piece.piece_type, piece_values)
                    
                    priority = 1000  # High priority for captures
                    secondary = victim_value  # Prefer capturing valuable pieces
                    tertiary = -attacker_value  # Prefer using less valuable pieces
                    self.stats.move_ordering_hits += 1
                    return (priority, secondary, tertiary)
            
            # Check for checks
            board.push(move)
            if board.is_check():
                priority = 900  # High priority for checks
                self.stats.move_ordering_hits += 1
            board.pop()
            
            # Check for castling
            if board.is_castling(move):
                priority = max(priority, 800)  # High priority for castling
                self.stats.move_ordering_hits += 1
            
            # Check for promotions
            if move.promotion:
                promotion_value = self._get_piece_value(move.promotion, piece_values)
                priority = max(priority, 700)  # High priority for promotions
                secondary = max(secondary, promotion_value)  # Prefer queen promotions
                self.stats.move_ordering_hits += 1
            
            # For other moves, order by piece value (move valuable pieces first)
            if priority == 0:
                moving_piece = board.piece_at(move.from_square)
                if moving_piece:
                    piece_value = self._get_piece_value(moving_piece.piece_type, piece_values)
                    secondary = piece_value
            
            return (priority, secondary, tertiary)
        
        # Sort moves by priority (descending order)
        ordered_moves = sorted(moves, key=move_priority, reverse=True)
        
        return ordered_moves
    
    def _get_piece_value(self, piece_type: chess.PieceType, piece_values: Dict[str, int]) -> int:
        """Get the value of a piece type from the configuration."""
        piece_map = {
            chess.PAWN: 'pawn',
            chess.KNIGHT: 'knight',
            chess.BISHOP: 'bishop',
            chess.ROOK: 'rook',
            chess.QUEEN: 'queen',
            chess.KING: 'king'
        }
        
        piece_name = piece_map.get(piece_type, 'pawn')
        return piece_values.get(piece_name, 0)


# Backward compatibility functions
_global_search_engine = ChessSearchEngine()

def find_best_move(board: chess.Board, depth: Optional[int] = None, 
                  time_limit: Optional[float] = None, 
                  game_id: Optional[str] = None) -> chess.Move:
    """Find the best move using the global search engine."""
    return _global_search_engine.find_best_move(board, depth, time_limit, game_id)

def get_search_stats() -> Dict[str, Any]:
    """Get search statistics from the global search engine."""
    return _global_search_engine.get_search_stats()


if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.DEBUG)
    
    print("Testing search algorithm...")
    
    # Test 1: Starting position
    board = chess.Board()
    search_engine = ChessSearchEngine()
    
    print("Searching starting position (depth 3)...")
    best_move = search_engine.find_best_move(board, depth=3)
    stats = search_engine.get_search_stats()
    
    print(f"Best move: {best_move}")
    print(f"Search stats: {stats}")
    print()
    
    # Test 2: Position with tactical opportunity
    print("Testing tactical position...")
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    
    best_move = search_engine.find_best_move(board, depth=4)
    stats = search_engine.get_search_stats()
    
    print(f"Best move: {best_move}")
    print(f"Search stats: {stats}")
    print()
    
    # Test 3: Time-limited search with iterative deepening
    print("Testing time-limited search with iterative deepening...")
    board = chess.Board()
    
    best_move = search_engine.find_best_move(board, depth=8, time_limit=2.0)
    stats = search_engine.get_search_stats()
    
    print(f"Best move: {best_move}")
    print(f"Search stats: {stats}")
    print()
    
    # Test 4: Quick time-limited search
    print("Testing quick time-limited search...")
    board = chess.Board()
    
    best_move = search_engine.find_best_move(board, depth=6, time_limit=0.5)
    stats = search_engine.get_search_stats()
    
    print(f"Best move: {best_move}")
    print(f"Search stats: {stats}")
    print()
    
    # Test 5: Fixed depth search (no time limit)
    print("Testing fixed depth search...")
    board = chess.Board()
    
    best_move = search_engine.find_best_move(board, depth=3, time_limit=None)
    stats = search_engine.get_search_stats()
    
    print(f"Best move: {best_move}")
    print(f"Search stats: {stats}")
    print()
    
    print("Search algorithm with time management test completed!")