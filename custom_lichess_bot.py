"""
Lichess bot integration module.
Handles connection to Lichess API and game management.
"""

import os
import time
import logging
import threading
import requests
import json
from queue import Queue, Empty
from typing import Dict, Any, Optional, Callable
import chess
from dotenv import load_dotenv
from config import ChessConfig, DEFAULT_CONFIG, PIECE_VALUES, MOBILITY_WEIGHT, PAWN_STRUCTURE_BONUS, KING_SAFETY_PENALTY, SEARCH_DEPTH, get_current_config
from search import ChessSearchEngine
from evaluation import get_evaluation_breakdown
from analytics import GameLogger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for API requests to respect Lichess API limits."""
    
    def __init__(self, max_requests: int = 60, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        with self.lock:
            now = time.time()
            # Remove old requests outside the time window
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = min(self.requests)
                wait_time = self.time_window - (now - oldest_request) + 1
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                    time.sleep(wait_time)
            
            self.requests.append(now)


class RequestQueue:
    """Queue for managing API requests with priority."""
    
    def __init__(self):
        self.queue = Queue()
        self.processing = False
        self.worker_thread = None
        self.rate_limiter = RateLimiter()
    
    def add_request(self, func: Callable, *args, **kwargs) -> None:
        """Add a request to the queue."""
        self.queue.put((func, args, kwargs))
        if not self.processing:
            self.start_processing()
    
    def start_processing(self) -> None:
        """Start processing requests in a separate thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self.processing = True
        self.worker_thread = threading.Thread(target=self._process_requests)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def _process_requests(self) -> None:
        """Process requests from the queue."""
        while self.processing:
            try:
                func, args, kwargs = self.queue.get(timeout=1)
                self.rate_limiter.wait_if_needed()
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                self.queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in request processing: {e}")
    
    def stop_processing(self) -> None:
        """Stop processing requests."""
        self.processing = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)


class LichessBotClient:
    """
    Lichess bot client for connecting to Lichess API and playing games.
    """
    
    def __init__(self, token: str = None, enable_logging: bool = True):
        """
        Initialize the Lichess bot client.
        
        Args:
            token: Lichess API token (loads from environment if None)
            enable_logging: Whether to enable comprehensive game logging
        """
        load_dotenv()
        self.token = token or os.getenv('LICHESS_TOKEN')
        if not self.token:
            raise ValueError("Lichess token not provided and not found in environment")
        
        # Initialize connection components
        self.client = None
        self.session = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        
        # Request management
        self.request_queue = RequestQueue()
        
        # Connection callbacks
        self.on_connect_callback = None
        self.on_disconnect_callback = None
        self.on_error_callback = None
        
        # Game logging
        self.enable_logging = enable_logging
        if self.enable_logging:
            self.game_logger = GameLogger()
        else:
            self.game_logger = None

        # Component Initialization
        # We initialize the search engine heavily in connect() or lazily 
        # because 'self.config' might be injected after __init__ but before connect.
        self.config = None 
        self.search_engine = None
    
    def connect(self) -> bool:
        """
        Establish connection to Lichess API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create requests session with authentication
            logger.info("Creating Lichess session...")
            self.session = requests.Session()
            self.session.headers.update({
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            })
            logger.info("Session created successfully")
            
            # Test the connection by getting account info
            logger.info("Testing connection with account info request...")
            response = self.session.get('https://lichess.org/api/account')
            
            if response.status_code == 200:
                account_info = response.json()
                logger.info(f"Connected to Lichess as {account_info['username']}")
                
                # Verify this is a bot account
                if not account_info.get('title') == 'BOT':
                    logger.warning("Account is not a bot account. Some features may not work.")
                
                self.connected = True
                self.client = account_info
                self.reconnect_attempts = 0
                
                if self.on_connect_callback:
                    self.on_connect_callback(account_info)
                
                return True
            else:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                if response.status_code == 401:
                    logger.error("Authentication failed. Check your Lichess token.")
                elif response.status_code == 429:
                    logger.error("Rate limited. Waiting before retry.")
                    time.sleep(60)
                self._handle_connection_error(Exception(f"HTTP {response.status_code}: {response.text}"))
                return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during connection: {e}")
            self._handle_connection_error(e)
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._handle_connection_error(e)
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Lichess API and cleanup resources."""
        logger.info("Disconnecting from Lichess")
        self.connected = False
        
        # Stop request processing
        self.request_queue.stop_processing()
        
        # Cleanup session
        if self.session:
            try:
                # Close any open connections
                if hasattr(self.session, 'close'):
                    self.session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
        
        self.client = None
        self.session = None
        
        if self.on_disconnect_callback:
            self.on_disconnect_callback()
    
    def is_connected(self) -> bool:
        """Check if currently connected to Lichess."""
        return self.connected and self.session is not None
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to Lichess with exponential backoff.
        
        Returns:
            True if reconnection successful, False otherwise
        """
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return False
        
        self.reconnect_attempts += 1
        wait_time = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))
        
        logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} "
                   f"in {wait_time} seconds")
        time.sleep(wait_time)
        
        # Cleanup current connection
        self.disconnect()
        
        # Attempt new connection
        return self.connect()
    
    def _handle_connection_error(self, error: Exception) -> None:
        """Handle connection errors with appropriate logging and callbacks."""
        self.connected = False
        logger.error(f"Connection error: {error}")
        
        if self.on_error_callback:
            self.on_error_callback(error)
    
    def set_callbacks(self, 
                     on_connect: Optional[Callable] = None,
                     on_disconnect: Optional[Callable] = None,
                     on_error: Optional[Callable] = None) -> None:
        """
        Set callback functions for connection events.
        
        Args:
            on_connect: Called when connection is established
            on_disconnect: Called when connection is lost
            on_error: Called when connection error occurs
        """
        self.on_connect_callback = on_connect
        self.on_disconnect_callback = on_disconnect
        self.on_error_callback = on_error
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current account information.
        
        Returns:
            Account info dict or None if not connected
        """
        if not self.is_connected():
            logger.warning("Not connected to Lichess")
            return None
        
        try:
            response = self.session.get('https://lichess.org/api/account')
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get account info: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            self._handle_connection_error(e)
            return None
    
    def handle_challenge(self, challenge_event: Dict[str, Any]) -> None:
        """
        Handle incoming game challenges.
        
        Args:
            challenge_event: Challenge event data from Lichess
        """
        try:
            challenge = challenge_event.get('challenge', {})
            challenger = challenge.get('challenger', {})
            challenger_name = challenger.get('name', 'Unknown')
            time_control = challenge.get('timeControl', {})
            variant = challenge.get('variant', {}).get('key', 'standard')
            
            logger.info(f"Received challenge from {challenger_name}")
            logger.info(f"Time control: {time_control}")
            logger.info(f"Variant: {variant}")
            
            # Check if we should accept the challenge
            should_accept = self._should_accept_challenge(challenge)
            
            if should_accept:
                self._accept_challenge(challenge.get('id'))
            else:
                self._decline_challenge(challenge.get('id'))
                
        except Exception as e:
            logger.error(f"Error handling challenge: {e}")
    
    def _should_accept_challenge(self, challenge: Dict[str, Any]) -> bool:
        """
        Determine if a challenge should be accepted based on configurable criteria.
        
        Args:
            challenge: Challenge data from Lichess
            
        Returns:
            True if challenge should be accepted, False otherwise
        """
        try:
            # Get challenge details
            variant = challenge.get('variant', {}).get('key', 'standard')
            time_control = challenge.get('timeControl', {})
            challenger = challenge.get('challenger', {})
            challenger_rating = challenger.get('rating', 0)
            
            # Check variant - only accept standard chess
            if variant != 'standard':
                logger.info(f"Declining challenge: unsupported variant '{variant}'")
                return False
            
            # Check time control type
            tc_type = time_control.get('type', '')
            
            # Accept correspondence and unlimited games
            if tc_type in ['correspondence', 'unlimited']:
                logger.info(f"Accepting {tc_type} challenge from {challenger.get('name', 'Unknown')}")
                return True
            
            # For clock-based games, check minimum time
            if tc_type == 'clock':
                limit = time_control.get('limit', 0)
                min_time_seconds = 60  # Minimum 1 minute per side
                if limit < min_time_seconds:
                    logger.info(f"Declining challenge: time control too fast ({limit}s)")
                    return False
                logger.info(f"Accepting timed challenge from {challenger.get('name', 'Unknown')}")
                return True
            
            # Accept other types by default
            logger.info(f"Accepting challenge from {challenger.get('name', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating challenge: {e}")
            return False
    
    def _accept_challenge(self, challenge_id: str) -> bool:
        """
        Accept a challenge.
        
        Args:
            challenge_id: ID of the challenge to accept
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_connected():
                logger.error("Cannot accept challenge: not connected")
                return False
            
            url = f'https://lichess.org/api/challenge/{challenge_id}/accept'
            response = self.session.post(url)
            
            if response.status_code == 200:
                logger.info(f"Successfully accepted challenge {challenge_id}")
                return True
            else:
                logger.error(f"Failed to accept challenge: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error accepting challenge: {e}")
            return False
    
    def _decline_challenge(self, challenge_id: str) -> bool:
        """
        Decline a challenge.
        
        Args:
            challenge_id: ID of the challenge to decline
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_connected():
                logger.error("Cannot decline challenge: not connected")
                return False
            
            url = f'https://lichess.org/api/challenge/{challenge_id}/decline'
            response = self.session.post(url)
            
            if response.status_code == 200:
                logger.info(f"Successfully declined challenge {challenge_id}")
                return True
            else:
                logger.error(f"Failed to decline challenge: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error declining challenge: {e}")
            return False
    
    def handle_game_state(self, game_state_event: Dict[str, Any]) -> None:
        """
        Handle game state updates.
        
        Args:
            game_state_event: Game state event data from Lichess
        """
        try:
            game_id = game_state_event.get('id')
            game_state = game_state_event.get('state', {})
            
            logger.info(f"Game state update for game {game_id}")
            
            # Handle different game states
            status = game_state.get('status')
            moves = game_state.get('moves', '')
            
            logger.info(f"Status: {status}, Moves: '{moves}'")
            
            # Always update the board with the latest moves first
            if hasattr(self, 'active_games') and game_id in self.active_games:
                game_info = self.active_games[game_id]
                moves_list = moves.split() if moves else []
                
                # Reconstruct board from scratch with all moves from Lichess
                # This ensures our board is always in sync with Lichess
                board = chess.Board()
                for move_str in moves_list:
                    try:
                        move = chess.Move.from_uci(move_str)
                        if move in board.legal_moves:
                            board.push(move)
                        else:
                            logger.error(f"Move {move_str} not legal in position {board.fen()}")
                    except ValueError as e:
                        logger.error(f"Invalid move format: {move_str} - {e}")
                
                game_info['board'] = board
                game_info['move_count'] = len(moves_list)
                logger.info(f"[BoardSync] Reconstructed board: {board.fen()}")
                logger.info(f"[BoardSync] {len(moves_list)} moves played, turn: {'white' if board.turn else 'black'}")
            else:
                logger.warning(f"Game {game_id} not in active_games!")
            
            if status in ['mate', 'resign', 'stalemate', 'timeout', 'draw', 'outoftime', 'aborted']:
                self._handle_game_end(game_id, status)
            else:
                # Game is ongoing, handle move if it's our turn
                logger.info(f"Calling _handle_game_move for game {game_id}")
                self._handle_game_move(game_id, game_state)
                
        except Exception as e:
            logger.error(f"Error handling game state: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_game_start(self, game_id: str, game_full_event: Dict[str, Any]) -> None:
        """
        Handle game start event.
        
        Args:
            game_id: Game ID
            game_full_event: Full game event data
        """
        try:
            logger.info(f"Game {game_id} started")
            logger.info(f"Game full event: {game_full_event}")
            
            # Extract game information
            white_player = game_full_event.get('white', {})
            black_player = game_full_event.get('black', {})
            
            logger.info(f"White player: {white_player}")
            logger.info(f"Black player: {black_player}")
            
            # Determine our color - try multiple fields
            account_info = self.get_account_info()
            our_username = account_info.get('username') if account_info else None
            our_id = account_info.get('id') if account_info else None
            
            logger.info(f"Our username: {our_username}, our id: {our_id}")
            
            our_color = None
            
            # Check by name or id
            white_name = white_player.get('name') or white_player.get('id')
            black_name = black_player.get('name') or black_player.get('id')
            
            if white_name and (white_name == our_username or white_name == our_id):
                our_color = 'white'
            elif black_name and (black_name == our_username or black_name == our_id):
                our_color = 'black'
            
            logger.info(f"Playing as {our_color} in game {game_id}")
            
            if our_color is None:
                logger.error(f"Could not determine our color! white={white_name}, black={black_name}, us={our_username}")
            
            # Store game information for later use
            if not hasattr(self, 'active_games'):
                self.active_games = {}
            
            self.active_games[game_id] = {
                'color': our_color,
                'white': white_player,
                'black': black_player,
                'board': chess.Board(),
                'started_at': time.time(),
                'move_count': 0
            }
            
            # Start neural network data collection (non-blocking)
            try:
                from nn_trainer import get_nn_trainer
                trainer = get_nn_trainer()
                trainer.data_collector.start_game(game_id)
                logger.info(f"[NNTrainer] Started collecting data for game {game_id}")
            except Exception as e:
                logger.warning(f"Could not start NN data collection: {e}")
            
            # Try to enable neural evaluation if weights exist (non-blocking)
            try:
                from neural_network import NN_WEIGHTS_PATH
                from search import set_neural_evaluation
                from hybrid_evaluator import get_hybrid_evaluator
                from pathlib import Path
                
                if NN_WEIGHTS_PATH.exists():
                    evaluator = get_hybrid_evaluator()
                    # Reload to get latest weights
                    evaluator.reload_neural_network()
                    if evaluator.neural_network is not None and evaluator.neural_network.positions_trained > 0:
                        # Load saved neural config if exists
                        neural_config_path = Path(__file__).parent / "configs" / "neural_config.json"
                        if neural_config_path.exists():
                            try:
                                with open(neural_config_path, 'r') as f:
                                    neural_config = json.load(f)
                                saved_blend = neural_config.get('neural_blend', 0.5)
                                evaluator.set_neural_blend(saved_blend)
                                logger.info(f"[NeuralNet] Loaded saved blend: {saved_blend:.0%}")
                            except Exception:
                                evaluator.set_neural_blend(0.5)
                        elif evaluator.neural_blend == 0:
                            evaluator.set_neural_blend(0.5)
                        
                        set_neural_evaluation(True)
                        logger.info(f"[NeuralNet] Using neural evaluation (v{evaluator.neural_network.version}, blend: {evaluator.neural_blend:.0%})")
            except Exception as e:
                logger.warning(f"Could not enable neural evaluation: {e}")
            
            # Start game logging
            if self.game_logger:
                opponent_name = black_player.get('name', 'Unknown') if our_color == 'white' else white_player.get('name', 'Unknown')
                opponent_rating = black_player.get('rating', 0) if our_color == 'white' else white_player.get('rating', 0)
                time_control = game_full_event.get('clock', {})
                
                self.game_logger.start_game_logging(
                    game_id=game_id,
                    our_color=our_color,
                    opponent_name=opponent_name,
                    opponent_rating=opponent_rating,
                    time_control=time_control
                )
            
            # If we're white, make the first move
            if our_color == 'white':
                self._make_engine_move(game_id)
                
        except Exception as e:
            logger.error(f"Error handling game start: {e}")
    
    def _handle_game_move(self, game_id: str, game_state: Dict[str, Any]) -> None:
        """
        Handle move in an ongoing game.
        
        Args:
            game_id: Game ID
            game_state: Current game state
        """
        try:
            logger.info(f"_handle_game_move called for game {game_id}")
            
            if not hasattr(self, 'active_games') or game_id not in self.active_games:
                logger.warning(f"Received move for unknown game {game_id}")
                return
            
            game_info = self.active_games[game_id]
            board = game_info['board']
            our_color = game_info['color']
            
            logger.info(f"Our color: {our_color}, Board turn: {'white' if board.turn else 'black'}")
            
            # Check if it's our turn
            is_our_turn = (board.turn == chess.WHITE and our_color == 'white') or \
                         (board.turn == chess.BLACK and our_color == 'black')
            
            logger.info(f"Is our turn: {is_our_turn}, Game over: {board.is_game_over()}")
            
            if is_our_turn and not board.is_game_over():
                logger.info(f"It's our turn in game {game_id}, making move...")
                self._make_engine_move(game_id)
            else:
                logger.info(f"Waiting for opponent's move in game {game_id}")
                
        except Exception as e:
            logger.error(f"Error handling game move: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_game_end(self, game_id: str, status: str) -> None:
        """
        Handle game end event.
        
        Args:
            game_id: Game ID
            status: Game end status
        """
        try:
            logger.info(f"Game {game_id} ended with status: {status}")
            
            # Clean up game data and finish logging
            if hasattr(self, 'active_games') and game_id in self.active_games:
                game_info = self.active_games[game_id]
                logger.info(f"Game duration: {time.time() - game_info['started_at']:.1f} seconds")
                
                # Determine outcome from our perspective
                our_color = game_info['color']
                board = game_info['board']
                
                # Debug logging
                logger.info(f"Our color: {our_color}, Board turn: {'white' if board.turn == chess.WHITE else 'black'}")
                logger.info(f"Board is_checkmate: {board.is_checkmate()}, is_game_over: {board.is_game_over()}")
                
                outcome = self._determine_game_outcome(status, our_color, board)
                logger.info(f"Determined outcome: {outcome}")
                
                # Neural network training - finish game and train
                try:
                    from nn_trainer import get_nn_trainer
                    trainer = get_nn_trainer()
                    
                    # Convert outcome to neural network format
                    if outcome == 'win':
                        nn_outcome = 'white_win' if our_color == 'white' else 'black_win'
                    elif outcome == 'loss':
                        nn_outcome = 'black_win' if our_color == 'white' else 'white_win'
                    else:
                        nn_outcome = 'draw'
                    
                    # Finish data collection and get game data
                    game_data = trainer.data_collector.finish_game(game_id, nn_outcome, source='lichess')
                    
                    if game_data and len(game_data.moves) > 0:
                        # Train on this game immediately using the new material-aware training
                        from neural_network import MoveRecord
                        moves = []
                        for m in game_data.moves:
                            try:
                                # Handle both old and new format
                                if 'fen_before' not in m and 'fen' in m:
                                    m = {
                                        'fen_before': m.get('fen', ''),
                                        'fen_after': m.get('fen', ''),
                                        'move_uci': m.get('move_uci', ''),
                                        'material_change': 0.0,
                                        'game_outcome': m.get('game_outcome', 0.5),
                                        'move_number': m.get('move_number', 1),
                                        'game_id': m.get('game_id', ''),
                                        'is_capture': False,
                                        'captured_piece_value': 0
                                    }
                                moves.append(MoveRecord(**m))
                            except Exception as e:
                                logger.warning(f"Skipping malformed move record: {e}")
                                continue
                        
                        if moves:
                            # CRITICAL: Learn MORE aggressively from losses
                            # If we lost, we need to strongly punish the moves that led to the loss
                            if outcome == 'loss':
                                # Temporarily increase learning rate for losses
                                original_lr = trainer.network.learning_rate
                                trainer.network.learning_rate = min(0.05, original_lr * 3)  # 3x learning rate for losses
                                logger.info(f"[NNTrainer] LOSS detected - using aggressive learning rate: {trainer.network.learning_rate}")
                            
                            result = trainer.network.train_on_game(moves)
                            
                            # Restore original learning rate
                            if outcome == 'loss':
                                trainer.network.learning_rate = original_lr
                            
                            trainer.network.save_weights()
                            trainer.data_collector.save_training_data()
                            logger.info(f"[NNTrainer] Trained on {len(moves)} positions from {outcome}, loss: {result['loss']:.6f}")
                            
                            # HOT-RELOAD: Update the hybrid evaluator with new weights
                            # This ensures the next game uses the updated neural network
                            try:
                                from hybrid_evaluator import get_hybrid_evaluator
                                evaluator = get_hybrid_evaluator()
                                evaluator.reload_neural_network()
                                logger.info(f"[NNTrainer] Hot-reloaded neural network (v{trainer.network.version})")
                            except Exception as reload_err:
                                logger.warning(f"Could not hot-reload neural network: {reload_err}")
                except Exception as e:
                    logger.warning(f"Error with neural network training: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Online learning - record game result
                try:
                    from online_learning import get_online_learner
                    learner = get_online_learner()
                    
                    # Get opponent rating if available
                    opponent_key = 'black' if our_color == 'white' else 'white'
                    opponent_rating = game_info.get(opponent_key, {}).get('rating', 0)
                    
                    learner.record_game(
                        game_id=game_id,
                        outcome=outcome,
                        our_color=our_color,
                        opponent_rating=opponent_rating,
                        move_count=game_info.get('move_count', 0)
                    )
                    logger.info(f"[OnlineLearning] Recorded {outcome} for learning")
                except Exception as e:
                    logger.warning(f"Error recording game for online learning: {e}")
                
                # Finish game logging
                if self.game_logger:
                    try:
                        self.game_logger.finish_game_logging(
                            game_id=game_id,
                            outcome=outcome,
                            termination=status,
                            final_position_fen=game_info['board'].fen()
                        )
                    except Exception as e:
                        logger.warning(f"Error finishing game logging: {e}")
                
                del self.active_games[game_id]
                
        except Exception as e:
            logger.error(f"Error handling game end: {e}")
    
    def _make_engine_move(self, game_id: str) -> None:
        """
        Make a move using the chess engine.
        
        Args:
            game_id: Game ID
        """
        try:
            if not hasattr(self, 'active_games') or game_id not in self.active_games:
                logger.error(f"Cannot make engine move: game {game_id} not found")
                return
            
            game_info = self.active_games[game_id]
            
            # CRITICAL: Get a fresh copy of the board to avoid state issues
            # The search engine modifies the board during search, so we need a copy
            board = game_info['board'].copy()
            
            logger.info(f"[Engine] Board state: {board.fen()}")
            logger.info(f"[Engine] Turn: {'white' if board.turn else 'black'}, Legal moves: {len(list(board.legal_moves))}")
            
            if board.is_game_over():
                logger.info(f"Game {game_id} is over, no move needed")
                return
            
            logger.info(f"Calculating best move for game {game_id}...")
            
            # Initialize search engine with best available config
            if not self.search_engine:
                config = None
                
                # Priority: 1) Online learned, 2) Lab config, 3) Trained from evolution, 4) Default
                try:
                    from online_learning import get_online_learner
                    learner = get_online_learner()
                    online_config = learner.get_config()
                    if online_config:
                        logger.info("Using online-learned configuration")
                        config = ChessConfig("online_learned")
                        for key, value in online_config.items():
                            config.update_parameter(key, value)
                except Exception as e:
                    logger.warning(f"Could not load online config: {e}")
                
                if config is None:
                    # Try lab config
                    from pathlib import Path
                    lab_config_path = Path(__file__).parent / "configs" / "lab_config.json"
                    if lab_config_path.exists():
                        try:
                            with open(lab_config_path, 'r') as f:
                                data = json.load(f)
                            lab_config = data.get('config')
                            if lab_config:
                                logger.info("Using lab configuration")
                                config = ChessConfig("lab")
                                for key, value in lab_config.items():
                                    config.update_parameter(key, value)
                        except Exception as e:
                            logger.warning(f"Could not load lab config: {e}")
                
                if config is None:
                    # Try trained config from evolution
                    from evolution import EvolutionaryOptimizer
                    trained_config = EvolutionaryOptimizer.load_trained_config()
                    if trained_config:
                        logger.info("Using trained configuration from evolution")
                        config = ChessConfig("trained")
                        for key, value in trained_config.items():
                            config.update_parameter(key, value)
                
                if config is None:
                    logger.info("Using default configuration")
                    config = ChessConfig("default")
                
                self.config = config
                self.search_engine = ChessSearchEngine(self.config)
                logger.info(f"Initialized search engine with config: {self.config.config_id}")
                
                # Check if neural network weights exist and enable neural evaluation
                try:
                    from neural_network import NN_WEIGHTS_PATH
                    from search import set_neural_evaluation
                    from hybrid_evaluator import get_hybrid_evaluator
                    
                    if NN_WEIGHTS_PATH.exists():
                        evaluator = get_hybrid_evaluator(self.config)
                        if evaluator.neural_network is not None and evaluator.neural_network.positions_trained > 0:
                            set_neural_evaluation(True)
                            logger.info(f"[NeuralNet] Enabled neural evaluation (v{evaluator.neural_network.version}, {evaluator.neural_network.positions_trained} positions trained)")
                        else:
                            logger.info("[NeuralNet] Neural weights exist but network not trained, using heuristic")
                    else:
                        logger.info("[NeuralNet] No neural weights found, using heuristic evaluation")
                except Exception as e:
                    logger.warning(f"Could not initialize neural evaluation: {e}")

            # Get time control information for move timing
            time_limit = self._get_move_time_limit(game_id)
            
            logger.info(f"Finding best move with time_limit={time_limit}...")
            
            # Use the chess engine to find the best move
            try:
                best_move = self.search_engine.find_best_move(board, depth=None, time_limit=time_limit, game_id=game_id)
                
                logger.info(f"Engine returned move: {best_move}")
                
                if best_move and best_move in board.legal_moves:
                    logger.info(f"Engine selected move: {best_move.uci()}")
                    
                    # Submit the move to Lichess
                    if self.make_move(game_id, best_move):
                        # Update our local board state (the original, not the copy)
                        game_info['board'].push(best_move)
                        
                        # Log the move
                        if self.game_logger:
                            self.game_logger.log_move_played(game_id, best_move.uci())
                        
                        logger.info(f"Move {best_move.uci()} played successfully")
                    else:
                        logger.error(f"Failed to submit move {best_move.uci()}")
                else:
                    logger.error(f"Engine returned invalid move: {best_move}, legal moves: {[m.uci() for m in board.legal_moves][:10]}")
                    # Fallback: make a random legal move
                    self._make_random_move(game_id)
                    
            except Exception as e:
                logger.error(f"Engine error: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: make a random legal move
                self._make_random_move(game_id)
                
        except Exception as e:
            logger.error(f"Error making engine move: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_move_time_limit(self, game_id: str) -> float:
        """
        Calculate appropriate time limit for move calculation.
        
        Args:
            game_id: Game ID
            
        Returns:
            Time limit in seconds
        """
        try:
            # Default time limit
            default_limit = 5.0  # 5 seconds
            
            # In a real implementation, this would consider:
            # - Remaining time on clock
            # - Time increment
            # - Game phase (opening/middlegame/endgame)
            # - Move complexity
            
            # For now, return a conservative default
            return default_limit
            
        except Exception as e:
            logger.error(f"Error calculating time limit: {e}")
            return 5.0
    
    def _make_random_move(self, game_id: str) -> None:
        """
        Make a random legal move as fallback.
        
        Args:
            game_id: Game ID
        """
        try:
            if not hasattr(self, 'active_games') or game_id not in self.active_games:
                return
            
            game_info = self.active_games[game_id]
            board = game_info['board']
            
            logger.info(f"[RandomMove] Board state: {board.fen()}")
            
            legal_moves = list(board.legal_moves)
            logger.info(f"[RandomMove] Legal moves: {[m.uci() for m in legal_moves][:10]}...")
            
            if legal_moves:
                import random
                random_move = random.choice(legal_moves)
                logger.warning(f"Making random move as fallback: {random_move.uci()}")
                
                if self.make_move(game_id, random_move):
                    # Update the original board in game_info
                    game_info['board'].push(random_move)
                    logger.info(f"Random move {random_move.uci()} played successfully")
                else:
                    logger.error(f"Failed to submit random move {random_move.uci()}")
            else:
                logger.error(f"No legal moves available for random fallback!")
                    
        except Exception as e:
            logger.error(f"Error making random move: {e}")
            import traceback
            traceback.print_exc()
    
    def make_move(self, game_id: str, move: chess.Move) -> bool:
        """
        Submit a move to Lichess.
        
        Args:
            game_id: Lichess game ID
            move: Chess move to submit
            
        Returns:
            True if move was submitted successfully, False otherwise
        """
        try:
            if not self.is_connected():
                logger.error("Cannot make move: not connected")
                return False
            
            # Convert move to UCI format
            move_uci = move.uci()
            
            # Submit move to Lichess
            url = f'https://lichess.org/api/bot/game/{game_id}/move/{move_uci}'
            response = self.session.post(url)
            
            if response.status_code == 200:
                logger.info(f"Successfully made move {move_uci} in game {game_id}")
                return True
            else:
                logger.error(f"Failed to make move: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error making move: {e}")
            return False
    
    def main_loop(self) -> None:
        """
        Main event loop for processing Lichess events.
        """
        if not self.is_connected():
            logger.error("Cannot start main loop: not connected to Lichess")
            return
        
        logger.info("Starting main event loop...")
        
        try:
            # Start listening for events
            self._listen_for_events()
        except KeyboardInterrupt:
            logger.info("Main loop interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            logger.info("Main loop ended")
    
    def _listen_for_events(self) -> None:
        """
        Listen for events from Lichess using Server-Sent Events (SSE).
        """
        try:
            # Connect to the event stream
            url = 'https://lichess.org/api/stream/event'
            
            logger.info("Connecting to Lichess event stream...")
            
            with self.session.get(url, stream=True) as response:
                if response.status_code != 200:
                    logger.error(f"Failed to connect to event stream: {response.status_code}")
                    return
                
                logger.info("Connected to event stream, listening for events...")
                
                for line in response.iter_lines():
                    if line:
                        try:
                            # Parse the JSON event
                            event_data = json.loads(line.decode('utf-8'))
                            self._process_event(event_data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse event JSON: {e}")
                        except Exception as e:
                            logger.error(f"Error processing event: {e}")
                            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error in event stream: {e}")
            # Try to reconnect
            if self.connected:
                logger.info("Attempting to reconnect...")
                time.sleep(5)
                self.reconnect()
        except Exception as e:
            logger.error(f"Unexpected error in event stream: {e}")
    
    def _process_event(self, event: Dict[str, Any]) -> None:
        """
        Process a single event from Lichess.
        
        Args:
            event: Event data from Lichess
        """
        try:
            event_type = event.get('type')
            
            if event_type == 'challenge':
                self.handle_challenge(event)
            elif event_type == 'gameStart':
                game_id = event.get('game', {}).get('id')
                if game_id:
                    logger.info(f"Game {game_id} starting, connecting to game stream...")
                    # Start a separate thread to handle this game
                    game_thread = threading.Thread(
                        target=self._handle_game_stream,
                        args=(game_id,),
                        daemon=True
                    )
                    game_thread.start()
            elif event_type == 'gameFinish':
                game_id = event.get('game', {}).get('id')
                logger.info(f"Game {game_id} finished")
            else:
                logger.debug(f"Unhandled event type: {event_type}")
                
        except Exception as e:
            logger.error(f"Error processing event: {e}")
    
    def _handle_game_stream(self, game_id: str) -> None:
        """
        Handle the game stream for a specific game.
        
        Args:
            game_id: Game ID to stream
        """
        try:
            url = f'https://lichess.org/api/bot/game/stream/{game_id}'
            
            logger.info(f"Connecting to game stream for {game_id}")
            
            with self.session.get(url, stream=True) as response:
                if response.status_code != 200:
                    logger.error(f"Failed to connect to game stream: {response.status_code}")
                    return
                
                logger.info(f"Connected to game stream for {game_id}")
                
                for line in response.iter_lines():
                    if line:
                        try:
                            event_data = json.loads(line.decode('utf-8'))
                            
                            # Handle different game event types
                            if 'type' in event_data:
                                if event_data['type'] == 'gameFull':
                                    # Initial game state
                                    self._handle_game_start(game_id, event_data)
                                elif event_data['type'] == 'gameState':
                                    # Game state update
                                    self.handle_game_state({
                                        'id': game_id,
                                        'state': event_data
                                    })
                            else:
                                # This might be a game state update without explicit type
                                self.handle_game_state({
                                    'id': game_id,
                                    'state': event_data
                                })
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse game event JSON: {e}")
                        except Exception as e:
                            logger.error(f"Error processing game event: {e}")
                            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error in game stream: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in game stream: {e}")
        finally:
            logger.info(f"Game stream ended for {game_id}")
    
    def get_active_games(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently active games.
        
        Returns:
            Dictionary of active games
        """
        return getattr(self, 'active_games', {})
    
    def create_challenge(self, username: str, time_control: Dict[str, Any] = None) -> bool:
        """
        Create a challenge to another user.
        
        Args:
            username: Username to challenge
            time_control: Time control settings
            
        Returns:
            True if challenge created successfully, False otherwise
        """
        try:
            if not self.is_connected():
                logger.error("Cannot create challenge: not connected")
                return False
            
            url = f'https://lichess.org/api/challenge/{username}'
            
            # Default time control if none provided
            if time_control is None:
                time_control = {
                    'limit': 300,  # 5 minutes
                    'increment': 3  # 3 second increment
                }
            
            data = {
                'rated': False,  # Unrated games for testing
                'clock.limit': time_control.get('limit', 300),
                'clock.increment': time_control.get('increment', 3),
                'variant': 'standard'
            }
            
            response = self.session.post(url, data=data)
            
            if response.status_code == 200:
                logger.info(f"Successfully created challenge to {username}")
                return True
            else:
                logger.error(f"Failed to create challenge: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            return False
    
    def resign_game(self, game_id: str) -> bool:
        """
        Resign from a game.
        
        Args:
            game_id: Game ID to resign from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_connected():
                logger.error("Cannot resign: not connected")
                return False
            
            url = f'https://lichess.org/api/bot/game/{game_id}/resign'
            response = self.session.post(url)
            
            if response.status_code == 200:
                logger.info(f"Successfully resigned from game {game_id}")
                return True
            else:
                logger.error(f"Failed to resign: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error resigning from game: {e}")
            return False
    
    def set_challenge_criteria(self, 
                               accepted_variants: list = None,
                               min_time_seconds: int = 60,
                               max_time_seconds: int = 3600,
                               max_rating_diff: int = 500) -> None:
        """
        Set criteria for accepting challenges.
        
        Args:
            accepted_variants: List of accepted game variants
            min_time_seconds: Minimum time control in seconds
            max_time_seconds: Maximum time control in seconds
            max_rating_diff: Maximum rating difference to accept
        """
        if accepted_variants is None:
            accepted_variants = ['standard', 'blitz', 'rapid']
        
        self.challenge_criteria = {
            'accepted_variants': accepted_variants,
            'min_time_seconds': min_time_seconds,
            'max_time_seconds': max_time_seconds,
            'max_rating_diff': max_rating_diff
        }
        
        logger.info(f"Updated challenge criteria: {self.challenge_criteria}")
    
    def validate_uci_move(self, board: chess.Board, move_uci: str) -> Optional[chess.Move]:
        """
        Validate and convert UCI move string to chess.Move object.
        
        Args:
            board: Current board position
            move_uci: Move in UCI format (e.g., 'e2e4')
            
        Returns:
            chess.Move object if valid, None otherwise
        """
        try:
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                return move
            else:
                logger.warning(f"Move {move_uci} is not legal in current position")
                return None
        except ValueError:
            logger.error(f"Invalid UCI move format: {move_uci}")
            return None
    
    def get_game_status(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a game.
        
        Args:
            game_id: Game ID
            
        Returns:
            Game status information or None if game not found
        """
        try:
            if not hasattr(self, 'active_games') or game_id not in self.active_games:
                return None
            
            game_info = self.active_games[game_id]
            board = game_info['board']
            
            return {
                'game_id': game_id,
                'our_color': game_info['color'],
                'turn': 'white' if board.turn == chess.WHITE else 'black',
                'is_our_turn': (board.turn == chess.WHITE and game_info['color'] == 'white') or 
                              (board.turn == chess.BLACK and game_info['color'] == 'black'),
                'move_count': board.fullmove_number,
                'is_game_over': board.is_game_over(),
                'result': board.result() if board.is_game_over() else None,
                'fen': board.fen(),
                'legal_moves': [move.uci() for move in board.legal_moves]
            }
            
        except Exception as e:
            logger.error(f"Error getting game status: {e}")
            return None
    
    def send_chat_message(self, game_id: str, message: str, room: str = 'player') -> bool:
        """
        Send a chat message in a game.
        
        Args:
            game_id: Game ID
            message: Message to send
            room: Chat room ('player' or 'spectator')
            
        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            if not self.is_connected():
                logger.error("Cannot send chat message: not connected")
                return False
            
            url = f'https://lichess.org/api/bot/game/{game_id}/chat'
            data = {
                'room': room,
                'text': message
            }
            
            response = self.session.post(url, data=data)
            
            if response.status_code == 200:
                logger.info(f"Chat message sent to game {game_id}: {message}")
                return True
            else:
                logger.error(f"Failed to send chat message: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending chat message: {e}")
            return False
    
    def offer_draw(self, game_id: str) -> bool:
        """
        Offer a draw in a game.
        
        Args:
            game_id: Game ID
            
        Returns:
            True if draw offer sent successfully, False otherwise
        """
        try:
            if not self.is_connected():
                logger.error("Cannot offer draw: not connected")
                return False
            
            url = f'https://lichess.org/api/bot/game/{game_id}/draw/yes'
            response = self.session.post(url)
            
            if response.status_code == 200:
                logger.info(f"Draw offered in game {game_id}")
                return True
            else:
                logger.error(f"Failed to offer draw: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error offering draw: {e}")
            return False
    
    def accept_draw(self, game_id: str) -> bool:
        """
        Accept a draw offer in a game.
        
        Args:
            game_id: Game ID
            
        Returns:
            True if draw accepted successfully, False otherwise
        """
        try:
            if not self.is_connected():
                logger.error("Cannot accept draw: not connected")
                return False
            
            url = f'https://lichess.org/api/bot/game/{game_id}/draw/yes'
            response = self.session.post(url)
            
            if response.status_code == 200:
                logger.info(f"Draw accepted in game {game_id}")
                return True
            else:
                logger.error(f"Failed to accept draw: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error accepting draw: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry."""
        if not self.connect():
            raise ConnectionError("Failed to connect to Lichess")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def test_connection(self) -> bool:
        """
        Test the current connection by making a simple API call.
        
        Returns:
            True if connection is working, False otherwise
        """
        try:
            if not self.is_connected():
                return False
            
            # Simple API call to test connection
            response = self.session.get('https://lichess.org/api/account')
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            self._handle_connection_error(e)
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get detailed connection status information.
        
        Returns:
            Dictionary with connection status details
        """
        return {
            'connected': self.connected,
            'reconnect_attempts': self.reconnect_attempts,
            'max_reconnect_attempts': self.max_reconnect_attempts,
            'has_client': self.client is not None,
            'has_session': self.session is not None,
            'token_configured': bool(self.token),
            'logging_enabled': self.enable_logging
        }
    
    def _determine_game_outcome(self, status: str, our_color: str, board: chess.Board) -> str:
        """
        Determine the game outcome from our perspective.
        
        Args:
            status: Game termination status from Lichess
            our_color: Our color in the game ('white' or 'black')
            board: Final board position
            
        Returns:
            Game outcome: 'win', 'loss', or 'draw'
        """
        try:
            # Draw statuses
            if status in ['draw', 'stalemate', 'insufficient', 'repetition', 'fiftyMoves']:
                return 'draw'
            
            if status == 'mate':
                # In checkmate, the side whose turn it is has lost
                # board.turn tells us who was about to move (and thus got mated)
                mated_color = 'white' if board.turn == chess.WHITE else 'black'
                if our_color == mated_color:
                    logger.info(f"We ({our_color}) got checkmated")
                    return 'loss'
                else:
                    logger.info(f"We ({our_color}) delivered checkmate")
                    return 'win'
            
            if status == 'resign':
                # When someone resigns, the side to move typically resigned
                # But this isn't always reliable - Lichess should provide winner
                # For now, assume if it's our turn, we resigned
                resigned_color = 'white' if board.turn == chess.WHITE else 'black'
                if our_color == resigned_color:
                    return 'loss'
                else:
                    return 'win'
            
            if status == 'timeout':
                # Similar logic for timeout
                timed_out_color = 'white' if board.turn == chess.WHITE else 'black'
                if our_color == timed_out_color:
                    return 'loss'
                else:
                    return 'win'
            
            if status == 'outoftime':
                # Out of time - same as timeout
                timed_out_color = 'white' if board.turn == chess.WHITE else 'black'
                if our_color == timed_out_color:
                    return 'loss'
                else:
                    return 'win'
            
            logger.warning(f"Unknown game status: {status}, defaulting to draw")
            return 'draw'
            
        except Exception as e:
            logger.error(f"Error determining game outcome: {e}")
            return 'draw'


def create_lichess_bot(token: str = None, 
                      on_connect: Optional[Callable] = None,
                      on_disconnect: Optional[Callable] = None,
                      on_error: Optional[Callable] = None,
                      enable_logging: bool = True) -> LichessBotClient:
    """
    Factory function to create and configure a Lichess bot client.
    
    Args:
        token: Lichess API token
        on_connect: Callback for connection events
        on_disconnect: Callback for disconnection events
        on_error: Callback for error events
        enable_logging: Whether to enable comprehensive game logging
    
    Returns:
        Configured LichessBotClient instance
    """
    bot = LichessBotClient(token, enable_logging)
    bot.set_callbacks(on_connect, on_disconnect, on_error)
    return bot


# Example usage and testing functions
if __name__ == "__main__":
    def on_connect(account_info):
        print(f"Connected as: {account_info['username']}")
    
    def on_disconnect():
        print("Disconnected from Lichess")
    
    def on_error(error):
        print(f"Connection error: {error}")
    
    # Test the connection
    try:
        with create_lichess_bot(on_connect=on_connect, 
                               on_disconnect=on_disconnect, 
                               on_error=on_error) as bot:
            print("Connection test successful!")
            status = bot.get_connection_status()
            print(f"Status: {status}")
            
            account = bot.get_account_info()
            if account:
                print(f"Account: {account['username']} (Rating: {account.get('perfs', {}).get('blitz', {}).get('rating', 'N/A')})")
    
    except Exception as e:
        print(f"Connection test failed: {e}")


# Example usage for testing the complete bot functionality
if __name__ == "__main__":
    def on_connect(account_info):
        print(f"Connected as: {account_info['username']}")
    
    def on_disconnect():
        print("Disconnected from Lichess")
    
    def on_error(error):
        print(f"Connection error: {error}")
    
    # Test the complete bot functionality
    try:
        bot = create_lichess_bot(on_connect=on_connect, 
                               on_disconnect=on_disconnect, 
                               on_error=on_error)
        
        if bot.connect():
            print("Bot connected successfully!")
            
            # Set challenge criteria
            bot.set_challenge_criteria(
                accepted_variants=['standard'],
                min_time_seconds=180,  # 3 minutes minimum
                max_time_seconds=1800  # 30 minutes maximum
            )
            
            # Test move validation
            import chess
            test_board = chess.Board()
            test_move = bot.validate_uci_move(test_board, 'e2e4')
            if test_move:
                print(f"Valid move: {test_move.uci()}")
            
            print("Bot is ready for gameplay!")
            print("In a real scenario, you would call bot.main_loop() to start listening for games")
            
            bot.disconnect()
        else:
            print("Failed to connect bot")
    
    except Exception as e:
        print(f"Error testing bot: {e}")
        import traceback
        traceback.print_exc()