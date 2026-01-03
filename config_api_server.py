"""
Config API Server for Chess Bot Studio.
Provides REST endpoints for the training UI.
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Callable
from urllib.parse import urlparse

from multi_bot_manager import get_bot_manager
from config import DEFAULT_CONFIG


# Global state for supervised training (thread-safe access)
_supervised_training_state = {
    'is_training': False,
    'current_epoch': 0,
    'total_epochs': 0,
    'positions_trained': 0,
    'target_positions': 0,
    'current_loss': 0.0,
    'final_loss': None,
    'phase': 'idle',  # 'idle', 'training', 'complete', 'error'
    'version': None
}
_supervised_training_lock = threading.Lock()


# Global state for hybrid training (combines supervised + RL)
_hybrid_training_state = {
    'is_training': False,
    'phase': 'idle',  # 'idle', 'supervised', 'self_play', 'rl_training', 'complete', 'error'
    'total_games': 0,
    'games_completed': 0,
    'current_game': 0,
    'positions_trained': 0,
    'supervised_positions': 0,
    'rl_positions': 0,
    'current_loss': 0.0,
    'best_loss': float('inf'),
    'games_since_improvement': 0,
    'version': 0,
    'message': ''
}
_hybrid_training_lock = threading.Lock()


def _run_hybrid_training(total_games: int, learning_rate: float, 
                         supervised_ratio: float = 0.3, 
                         search_depth: int = 2,
                         save_interval: int = 100) -> None:
    """
    Run hybrid training combining supervised learning and reinforcement learning.
    
    TRAINS AFTER EVERY MOVE for immediate feedback!
    
    Strategy:
    1. Play self-play games
    2. After EACH MOVE, train on the position with supervised signal (heuristic)
    3. After game ends, replay all positions with RL signal (outcome)
    4. This gives immediate feedback + long-term outcome learning
    
    Training is CUMULATIVE - it continues from existing weights, never resets.
    """
    global _hybrid_training_state
    
    try:
        from nn_trainer import get_nn_trainer, get_material_change
        from evaluation import evaluate_board
        from config import DEFAULT_CONFIG
        import chess
        import random
        
        print(f"[HybridTraining] Starting: {total_games} games, lr={learning_rate}, supervised_ratio={supervised_ratio}")
        print(f"[HybridTraining] Training is CUMULATIVE - continuing from existing weights")
        
        trainer = get_nn_trainer()
        
        # DON'T reset - continue from existing weights
        print(f"[HybridTraining] Starting with {trainer.network.positions_trained} existing positions trained")
        
        original_lr = trainer.network.learning_rate
        trainer.network.learning_rate = learning_rate
        
        # Save initial checkpoint (but don't reset!)
        if trainer.network.positions_trained > 0:
            trainer.network.save_checkpoint(
                f"pre_hybrid_{trainer.network.positions_trained}pos",
                f"Before hybrid training ({total_games} games) - cumulative"
            )
        
        config = DEFAULT_CONFIG
        
        # Track statistics for THIS session (not total)
        session_positions = 0
        session_loss = 0.0
        best_loss = float('inf')
        games_since_improvement = 0
        
        # Common openings for variety
        openings = [
            [],  # Start from initial position
            ["e2e4"], ["d2d4"], ["c2c4"], ["g1f3"],
            ["e2e4", "e7e5"], ["d2d4", "d7d5"], ["e2e4", "c7c5"],
            ["e2e4", "e7e5", "g1f3", "b8c6"], ["d2d4", "g8f6", "c2c4"],
            ["e2e4", "c7c5", "g1f3"], ["d2d4", "g8f6", "c2c4", "e7e6"],
        ]
        
        for game_num in range(total_games):
            # Check if training should stop
            with _hybrid_training_lock:
                if not _hybrid_training_state.get('is_training', True):
                    print(f"[HybridTraining] Stopped by user at game {game_num}")
                    break
                    
                _hybrid_training_state['phase'] = 'self_play'
                _hybrid_training_state['current_game'] = game_num + 1
                _hybrid_training_state['games_completed'] = game_num
                _hybrid_training_state['message'] = f'Playing game {game_num + 1}/{total_games}'
            
            # Create a new game
            board = chess.Board()
            
            # Apply random opening
            opening = random.choice(openings)
            for move_uci in opening:
                try:
                    board.push_uci(move_uci)
                except:
                    break
            
            # Store positions for end-of-game RL training
            game_positions = []
            move_count = 0
            max_moves = 150
            game_loss = 0.0
            
            # Play the game - TRAIN AFTER EVERY MOVE
            while not board.is_game_over() and move_count < max_moves:
                # Get heuristic evaluation
                heuristic_eval = evaluate_board(board, config)
                current_turn = board.turn
                
                # Store position for later RL training
                game_positions.append({
                    'fen': board.fen(),
                    'heuristic_eval': heuristic_eval,
                    'turn': current_turn,
                    'move_number': move_count
                })
                
                # === IMMEDIATE SUPERVISED TRAINING ===
                # Train on this position RIGHT NOW with heuristic as target
                supervised_target = max(-1.0, min(1.0, heuristic_eval / 1500.0))
                
                # Use supervised_ratio to weight this training
                # Higher ratio = more weight on immediate heuristic feedback
                loss = trainer.network.train_on_position(
                    board, 
                    supervised_target, 
                    weight=supervised_ratio * 0.5  # Scale down to not overwhelm
                )
                game_loss += loss
                session_positions += 1
                
                # Select move
                legal_moves = list(board.legal_moves)
                if not legal_moves:
                    break
                
                # Move selection with some exploration
                if random.random() < 0.15:  # 15% random for exploration
                    move = random.choice(legal_moves)
                else:
                    # 1-ply search
                    best_move = None
                    best_score = float('-inf') if board.turn == chess.WHITE else float('inf')
                    
                    for m in legal_moves:
                        board.push(m)
                        score = evaluate_board(board, config)
                        score += random.uniform(-15, 15)  # Noise for variety
                        
                        if board.turn == chess.BLACK:  # Just moved as white
                            if score > best_score:
                                best_score = score
                                best_move = m
                        else:  # Just moved as black
                            if score < best_score:
                                best_score = score
                                best_move = m
                        board.pop()
                    
                    move = best_move if best_move else random.choice(legal_moves)
                
                board.push(move)
                move_count += 1
            
            # Determine game outcome
            if board.is_checkmate():
                outcome = 0.0 if board.turn == chess.WHITE else 1.0
            else:
                outcome = 0.5
            
            # === END-OF-GAME RL TRAINING ===
            # Now replay all positions with the game outcome as additional signal
            with _hybrid_training_lock:
                _hybrid_training_state['phase'] = 'rl_training'
                _hybrid_training_state['message'] = f'RL training game {game_num + 1}'
            
            rl_weight = (1 - supervised_ratio) * 0.5  # Scale to balance with supervised
            
            for pos_data in game_positions:
                try:
                    pos_board = chess.Board(pos_data['fen'])
                    
                    # RL target from game outcome
                    if pos_data['turn'] == chess.WHITE:
                        rl_target = outcome * 2 - 1  # 0->-1, 0.5->0, 1->1
                    else:
                        rl_target = (1 - outcome) * 2 - 1
                    
                    # Train with RL signal
                    loss = trainer.network.train_on_position(pos_board, rl_target, weight=rl_weight)
                    game_loss += loss
                    session_positions += 1
                    
                except Exception:
                    continue
            
            # Update statistics
            avg_game_loss = game_loss / max(1, len(game_positions) * 2)  # *2 for supervised + RL
            session_loss += avg_game_loss
            
            if avg_game_loss < best_loss:
                best_loss = avg_game_loss
                games_since_improvement = 0
            else:
                games_since_improvement += 1
            
            # Update state
            with _hybrid_training_lock:
                _hybrid_training_state['positions_trained'] = session_positions
                _hybrid_training_state['current_loss'] = avg_game_loss
                _hybrid_training_state['best_loss'] = best_loss
                _hybrid_training_state['games_since_improvement'] = games_since_improvement
            
            # Log progress
            if (game_num + 1) % 10 == 0:
                avg_loss = session_loss / (game_num + 1)
                total_trained = trainer.network.positions_trained
                print(f"[HybridTraining] Game {game_num + 1}/{total_games} - "
                      f"Session: {session_positions} pos, Total: {total_trained} pos, "
                      f"Loss: {avg_loss:.6f}, Best: {best_loss:.6f}")
            
            # Save periodically AND hot-reload for Lichess
            if (game_num + 1) % save_interval == 0:
                trainer.network.save_weights()
                trainer.network.save_checkpoint(
                    f"hybrid_g{game_num + 1}_{trainer.network.positions_trained}pos",
                    f"Game {game_num + 1}, {trainer.network.positions_trained} total positions"
                )
                
                # Hot-reload for Lichess bot to use updated weights
                try:
                    from hybrid_evaluator import get_hybrid_evaluator
                    from search import set_neural_evaluation
                    evaluator = get_hybrid_evaluator()
                    evaluator.reload_neural_network()
                    # Enable neural evaluation if not already
                    if evaluator.neural_blend > 0:
                        set_neural_evaluation(True)
                    print(f"[HybridTraining] Checkpoint saved & hot-reloaded at game {game_num + 1}")
                except Exception as reload_err:
                    print(f"[HybridTraining] Checkpoint saved at game {game_num + 1} (hot-reload failed: {reload_err})")
        
        # Final save
        trainer.network.learning_rate = original_lr
        trainer.network.save_weights()
        
        final_total = trainer.network.positions_trained
        trainer.network.save_checkpoint(
            f"hybrid_final_{total_games}g_{final_total}pos",
            f"Final: {total_games} games this session, {final_total} total positions trained"
        )
        
        # Hot-reload final weights for Lichess
        try:
            from hybrid_evaluator import get_hybrid_evaluator
            from search import set_neural_evaluation
            evaluator = get_hybrid_evaluator()
            evaluator.reload_neural_network()
            print(f"[HybridTraining] Final weights hot-reloaded for Lichess")
        except Exception as reload_err:
            print(f"[HybridTraining] Could not hot-reload final weights: {reload_err}")
        
        with _hybrid_training_lock:
            _hybrid_training_state['phase'] = 'complete'
            _hybrid_training_state['is_training'] = False
            _hybrid_training_state['games_completed'] = total_games
            _hybrid_training_state['version'] = trainer.network.version
            _hybrid_training_state['message'] = f'Complete! {session_positions} positions this session, {final_total} total'
        
        print(f"[HybridTraining] Complete: {total_games} games, {session_positions} positions this session")
        print(f"[HybridTraining] Total positions trained (cumulative): {final_total}")
        
    except Exception as e:
        print(f"[HybridTraining] Error: {e}")
        import traceback
        traceback.print_exc()
        
        with _hybrid_training_lock:
            _hybrid_training_state['phase'] = 'error'
            _hybrid_training_state['is_training'] = False
            _hybrid_training_state['message'] = str(e)


def _run_supervised_training(num_positions: int, learning_rate: float, epochs: int) -> None:
    """Run supervised training in background thread.
    
    IMPORTANT: This uses a much lower effective learning rate and generates
    more realistic positions to avoid catastrophically overwriting RL learning.
    Auto-saves a checkpoint before training starts.
    """
    global _supervised_training_state
    
    try:
        from nn_trainer import get_nn_trainer
        from evaluation import evaluate_board
        from config import DEFAULT_CONFIG
        import chess
        import random
        
        print(f"[SupervisedTraining] Starting: {num_positions} positions, {epochs} epochs, lr={learning_rate}")
        
        trainer = get_nn_trainer()
        
        # AUTO-CHECKPOINT: Save current state before supervised training
        # This allows recovery if supervised training damages the model
        if trainer.network.positions_trained > 0:
            checkpoint_name = f"pre_supervised_{trainer.network.positions_trained}pos"
            trainer.network.save_checkpoint(
                checkpoint_name, 
                f"Auto-saved before supervised training ({num_positions} positions, {epochs} epochs)"
            )
            print(f"[SupervisedTraining] Auto-saved checkpoint: {checkpoint_name}")
        
        # CRITICAL: Use a much lower learning rate for supervised training
        # to avoid catastrophically forgetting RL learning
        # Scale down by factor of 10-20x from user-specified rate
        effective_lr = learning_rate * 0.05  # 5% of specified rate
        original_lr = trainer.network.learning_rate
        trainer.network.learning_rate = effective_lr
        
        print(f"[SupervisedTraining] Using effective LR: {effective_lr} (scaled from {learning_rate})")
        
        with _supervised_training_lock:
            _supervised_training_state['phase'] = 'training'
        
        positions_trained = 0
        total_loss = 0.0
        config = DEFAULT_CONFIG
        
        # Common opening moves for more realistic positions
        common_openings = [
            ["e2e4"], ["d2d4"], ["c2c4"], ["g1f3"],
            ["e2e4", "e7e5"], ["d2d4", "d7d5"], ["e2e4", "c7c5"],
            ["e2e4", "e7e5", "g1f3"], ["d2d4", "g8f6", "c2c4"],
            ["e2e4", "e7e5", "g1f3", "b8c6"], ["d2d4", "d7d5", "c2c4"],
        ]
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            positions_per_epoch = num_positions // epochs
            skipped = 0
            
            for pos_idx in range(positions_per_epoch):
                board = chess.Board()
                
                # 30% chance to start from a common opening
                if random.random() < 0.3 and common_openings:
                    opening = random.choice(common_openings)
                    for move_uci in opening:
                        try:
                            board.push_uci(move_uci)
                        except:
                            break
                
                # Play semi-random moves (prefer captures and checks for realism)
                num_moves = random.randint(8, 40)  # More reasonable game length
                
                for _ in range(num_moves):
                    legal_moves = list(board.legal_moves)
                    if not legal_moves or board.is_game_over():
                        break
                    
                    # Bias toward captures and checks for more tactical positions
                    captures = [m for m in legal_moves if board.is_capture(m)]
                    checks = [m for m in legal_moves if board.gives_check(m)]
                    
                    if captures and random.random() < 0.4:
                        move = random.choice(captures)
                    elif checks and random.random() < 0.3:
                        move = random.choice(checks)
                    else:
                        move = random.choice(legal_moves)
                    
                    board.push(move)
                
                if board.is_game_over():
                    skipped += 1
                    continue
                
                # Skip positions with extreme material imbalance (unrealistic)
                heuristic_eval = evaluate_board(board, config)
                if abs(heuristic_eval) > 2000:  # Skip if > 20 pawns advantage
                    skipped += 1
                    continue
                
                # Normalize to [-1, 1] with softer scaling
                # Use tanh-like scaling for smoother gradients
                target = max(-1.0, min(1.0, heuristic_eval / 1500.0))
                
                # Lower weight for supervised samples to preserve RL learning
                loss = trainer.network.train_on_position(board, target, weight=0.3)
                epoch_loss += loss
                positions_trained += 1
                
                # Update state periodically (every 50 positions)
                if positions_trained % 50 == 0:
                    with _supervised_training_lock:
                        _supervised_training_state['positions_trained'] = positions_trained
                        _supervised_training_state['current_loss'] = epoch_loss / max(1, pos_idx + 1 - skipped)
            
            avg_epoch_loss = epoch_loss / max(1, positions_per_epoch - skipped)
            total_loss += avg_epoch_loss
            
            # Update state after each epoch
            with _supervised_training_lock:
                _supervised_training_state['current_epoch'] = epoch + 1
                _supervised_training_state['current_loss'] = avg_epoch_loss
                _supervised_training_state['positions_trained'] = positions_trained
            
            print(f"[SupervisedTraining] Epoch {epoch + 1}/{epochs} - Loss: {avg_epoch_loss:.6f} (skipped {skipped} unrealistic positions)")
        
        # Restore original learning rate
        trainer.network.learning_rate = original_lr
        
        # Save the trained network
        trainer.network.save_weights()
        
        final_loss = total_loss / max(1, epochs)
        
        with _supervised_training_lock:
            _supervised_training_state['phase'] = 'complete'
            _supervised_training_state['final_loss'] = final_loss
            _supervised_training_state['is_training'] = False
            _supervised_training_state['version'] = trainer.network.version
        
        print(f"[SupervisedTraining] Complete: {positions_trained} positions, final loss: {final_loss:.6f}")
        print(f"[SupervisedTraining] Learning rate restored to: {original_lr}")
        
    except Exception as e:
        print(f"[SupervisedTraining] Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to restore learning rate on error
        try:
            trainer.network.learning_rate = original_lr
        except:
            pass
        
        with _supervised_training_lock:
            _supervised_training_state['phase'] = 'error'
            _supervised_training_state['is_training'] = False


class ConfigAPIRequestHandler(BaseHTTPRequestHandler):
    """HTTP API handler for bot configuration and training control."""

    # Suppress default logging to keep console clean
    def log_message(self, format, *args):
        pass  # Override to suppress HTTP logs

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        """Send a JSON response with CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_json_body(self) -> Dict[str, Any]:
        """Read and parse JSON from request body."""
        content_length = self.headers.get("Content-Length")
        if not content_length:
            return {}
        try:
            raw = self.rfile.read(int(content_length))
            return json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            return {}

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        """Route GET requests."""
        path = urlparse(self.path).path.rstrip('/')
        
        # DEBUG: Print to stderr to ensure we see it
        import sys
        print(f"[DEBUG] GET path: '{path}'", file=sys.stderr, flush=True)
        
        routes = {
            "/api/active-bots": self._get_active_bots,
            "/api/training/status": self._get_training_status,
            "/api/training/current-game": self._get_current_game,
            "/api/lab/config": self._get_lab_config,
            "/api/neural/status": self._get_neural_status,
            "/api/neural/evaluate": self._get_neural_evaluate,
            "/api/neural/current-game": self._get_neural_current_game,
            "/api/neural/supervised-status": self._get_neural_supervised_status,
            "/api/neural/checkpoints": self._get_neural_checkpoints,
            "/api/neural/hybrid-status": self._get_neural_hybrid_status,
        }
        
        # DEBUG: Check if path is in routes
        print(f"[DEBUG] Path in routes: {path in routes}", file=sys.stderr, flush=True)
        print(f"[DEBUG] Routes keys: {list(routes.keys())}", file=sys.stderr, flush=True)
        
        # Check exact matches first
        if path in routes:
            try:
                routes[path]()
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return
        
        # Check prefix matches (for /api/get-config/<bot_id>)
        if path.startswith("/api/get-config/"):
            try:
                bot_id = path.split("/")[-1]
                self._get_bot_config(bot_id)
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return
        
        # No route matched
        self._send_json({"ok": False, "error": "Not found"}, 404)

    def do_POST(self) -> None:
        """Route POST requests."""
        path = urlparse(self.path).path.rstrip('/')
        
        routes = {
            "/api/training/start": self._post_training_start,
            "/api/training/stop": self._post_training_stop,
            "/api/training/pause": self._post_training_pause,
            "/api/training/resume": self._post_training_resume,
            "/api/training/reset": self._post_training_reset,
            "/api/lab/config": self._post_lab_config,
            "/api/neural/train": self._post_neural_train,
            "/api/neural/stop": self._post_neural_stop,
            "/api/neural/reset": self._post_neural_reset,
            "/api/neural/learning-rate": self._post_neural_learning_rate,
            "/api/neural/save-and-apply": self._post_neural_save_and_apply,
            "/api/neural/blend": self._post_neural_blend,
            "/api/neural/supervised-train": self._post_neural_supervised_train,
            "/api/neural/live-supervised": self._post_neural_live_supervised,
            "/api/neural/checkpoint/save": self._post_neural_checkpoint_save,
            "/api/neural/checkpoint/load": self._post_neural_checkpoint_load,
            "/api/neural/checkpoint/delete": self._post_neural_checkpoint_delete,
            "/api/neural/hybrid-train": self._post_neural_hybrid_train,
            "/api/neural/hybrid-stop": self._post_neural_hybrid_stop,
        }
        
        if path in routes:
            try:
                routes[path]()
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return
        
        # Check prefix matches (for /api/save-config/<bot_id>)
        if path.startswith("/api/save-config/"):
            try:
                bot_id = path.split("/")[-1]
                self._post_save_config(bot_id)
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return
        
        self._send_json({"ok": False, "error": "Not found"}, 404)

    # ==================== GET Handlers ====================

    def _get_active_bots(self) -> None:
        """Return list of active bot IDs."""
        bot_manager = get_bot_manager()
        active_bots = list(bot_manager.active_bots.keys())
        self._send_json({"ok": True, "active_bots": active_bots})

    def _get_bot_config(self, bot_id: str) -> None:
        """Return configuration for a specific bot."""
        bot_manager = get_bot_manager()
        instance = bot_manager.get_bot_instance(bot_id)
        
        if not instance:
            self._send_json({"ok": False, "error": "Bot not found"}, 404)
            return
        
        conf = instance.config.get_current_config()
        
        # Convert king_safety_penalty dict to slider value for UI
        ks_dict = conf.get("king_safety_penalty", {})
        open_file = ks_dict.get("open_file_near_king", -30)
        try:
            king_safety_slider = int((open_file / -30) * 20)
        except:
            king_safety_slider = 20
        
        response_data = {
            "piece_values": conf.get("piece_values", {}),
            "mobility_weight": conf.get("mobility_weight", 10),
            "search_depth": conf.get("search_depth", 4),
            "king_safety": king_safety_slider
        }
        self._send_json({"ok": True, "config": response_data})

    def _get_training_status(self) -> None:
        """Return current training status."""
        from evolution import get_optimizer, TRAINED_CONFIG_PATH
        optimizer = get_optimizer()
        status = optimizer.get_status()
        
        # Add info about saved config
        status['trained_config_exists'] = TRAINED_CONFIG_PATH.exists()
        if TRAINED_CONFIG_PATH.exists():
            try:
                import json
                with open(TRAINED_CONFIG_PATH, 'r') as f:
                    saved = json.load(f)
                status['trained_config_info'] = {
                    'saved_at': saved.get('saved_at'),
                    'fitness': saved.get('fitness'),
                    'win_rate': saved.get('win_rate'),
                    'generation': saved.get('generation')
                }
            except:
                pass
        
        self._send_json({"ok": True, **status})

    def _get_current_game(self) -> None:
        """Return the current self-play game state."""
        from self_play import get_self_play_engine
        engine = get_self_play_engine()
        game = engine.current_game
        
        if game:
            game_data = {
                'move_count': game.get('move_count', 0),
                'white_id': game.get('white_id', ''),
                'black_id': game.get('black_id', ''),
                'fen': game.get('fen', 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'),
                'last_move': game.get('last_move', '')
            }
            self._send_json({"ok": True, "game": game_data})
        else:
            self._send_json({"ok": True, "game": None})

    def _get_lab_config(self) -> None:
        """Return the current lab configuration (persisted to disk)."""
        from pathlib import Path
        
        lab_config_path = Path(__file__).parent / "configs" / "lab_config.json"
        
        # Try to load saved lab config
        if lab_config_path.exists():
            try:
                with open(lab_config_path, 'r') as f:
                    data = json.load(f)
                config = data.get('config', {})
                
                # Convert to UI format
                ks_dict = config.get("king_safety_penalty", DEFAULT_CONFIG["king_safety_penalty"])
                open_file = ks_dict.get("open_file_near_king", -30)
                king_safety_slider = int((open_file / -30) * 20)
                
                response_data = {
                    "piece_values": config.get("piece_values", DEFAULT_CONFIG["piece_values"]),
                    "mobility_weight": config.get("mobility_weight", DEFAULT_CONFIG["mobility_weight"]),
                    "search_depth": config.get("search_depth", DEFAULT_CONFIG["search_depth"]),
                    "king_safety": king_safety_slider
                }
                self._send_json({"ok": True, "config": response_data})
                return
            except Exception as e:
                print(f"[ConfigAPI] Error loading lab config: {e}")
        
        # Fall back to defaults
        response_data = {
            "piece_values": DEFAULT_CONFIG["piece_values"],
            "mobility_weight": DEFAULT_CONFIG["mobility_weight"],
            "search_depth": DEFAULT_CONFIG["search_depth"],
            "king_safety": 20  # Default slider value
        }
        self._send_json({"ok": True, "config": response_data})

    # ==================== POST Handlers ====================

    def _post_training_start(self) -> None:
        """Start evolutionary training."""
        from evolution import get_optimizer
        
        body = self._read_json_body()
        optimizer = get_optimizer()
        
        if optimizer._is_running:
            self._send_json({"ok": False, "error": "Training already in progress"}, 400)
            return
        
        optimizer.population_size = body.get("population_size", 8)
        optimizer.games_per_match = body.get("games_per_match", 4)
        optimizer.start_async(body.get("max_generations", 10))
        
        self._send_json({"ok": True, "message": "Training started"})

    def _post_training_stop(self) -> None:
        """Stop training."""
        from evolution import get_optimizer
        get_optimizer().stop()
        self._send_json({"ok": True, "message": "Training stopped"})

    def _post_training_pause(self) -> None:
        """Pause training."""
        from evolution import get_optimizer
        get_optimizer().pause()
        self._send_json({"ok": True, "message": "Training paused"})

    def _post_training_resume(self) -> None:
        """Resume training."""
        from evolution import get_optimizer
        get_optimizer().resume()
        self._send_json({"ok": True, "message": "Training resumed"})

    def _post_training_reset(self) -> None:
        """Reset training state."""
        from evolution import get_optimizer
        get_optimizer().reset()
        self._send_json({"ok": True, "message": "Training reset"})

    def _post_lab_config(self) -> None:
        """Save lab configuration to disk."""
        from pathlib import Path
        from datetime import datetime
        
        body = self._read_json_body()
        ui_config = body.get("config")
        
        if not isinstance(ui_config, dict):
            self._send_json({"ok": False, "error": "Missing or invalid 'config'"}, 400)
            return
        
        # Build full config from UI values
        config: Dict[str, Any] = {}
        
        if "piece_values" in ui_config:
            config["piece_values"] = {
                **DEFAULT_CONFIG["piece_values"],
                **(ui_config["piece_values"] or {})
            }
        else:
            config["piece_values"] = DEFAULT_CONFIG["piece_values"]
        
        if "mobility_weight" in ui_config:
            config["mobility_weight"] = ui_config["mobility_weight"]
        else:
            config["mobility_weight"] = DEFAULT_CONFIG["mobility_weight"]
        
        if "search_depth" in ui_config:
            config["search_depth"] = ui_config["search_depth"]
        else:
            config["search_depth"] = DEFAULT_CONFIG["search_depth"]
        
        if "king_safety" in ui_config:
            slider = ui_config["king_safety"]
            try:
                scale = max(0.25, min(4.0, float(slider) / 20.0))
            except:
                scale = 1.0
            config["king_safety_penalty"] = {
                k: int(v * scale) for k, v in DEFAULT_CONFIG["king_safety_penalty"].items()
            }
        else:
            config["king_safety_penalty"] = DEFAULT_CONFIG["king_safety_penalty"]
        
        # Save to disk
        lab_config_path = Path(__file__).parent / "configs" / "lab_config.json"
        lab_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        save_data = {
            "config": config,
            "saved_at": datetime.now().isoformat(),
            "source": "lab_ui"
        }
        
        try:
            with open(lab_config_path, 'w') as f:
                json.dump(save_data, f, indent=2)
            print(f"[ConfigAPI] Lab config saved to {lab_config_path}")
            self._send_json({"ok": True, "message": "Configuration saved", "config": config})
        except Exception as e:
            self._send_json({"ok": False, "error": f"Failed to save: {e}"}, 500)

    def _post_save_config(self, bot_id: str) -> None:
        """Save configuration for a bot."""
        bot_manager = get_bot_manager()
        body = self._read_json_body()
        ui_config = body.get("config")
        
        if not isinstance(ui_config, dict):
            self._send_json({"ok": False, "error": "Missing or invalid 'config'"}, 400)
            return
        
        updates: Dict[str, Any] = {}
        
        if "piece_values" in ui_config:
            updates["piece_values"] = {
                **DEFAULT_CONFIG["piece_values"],
                **(ui_config["piece_values"] or {})
            }
        
        if "mobility_weight" in ui_config:
            updates["mobility_weight"] = ui_config["mobility_weight"]
        
        if "search_depth" in ui_config:
            updates["search_depth"] = ui_config["search_depth"]
        
        if "king_safety" in ui_config:
            slider = ui_config["king_safety"]
            try:
                scale = max(0.25, min(4.0, float(slider) / 20.0))
            except:
                scale = 1.0
            updates["king_safety_penalty"] = {
                k: int(v * scale) for k, v in DEFAULT_CONFIG["king_safety_penalty"].items()
            }
        
        if not updates:
            self._send_json({"ok": False, "error": "No recognized parameters"}, 400)
            return
        
        success = bot_manager.update_bot_configuration(bot_id, updates)
        
        if not success:
            self._send_json({"ok": False, "error": f"Failed to update bot '{bot_id}'"}, 400)
            return
        
        instance = bot_manager.get_bot_instance(bot_id)
        applied = instance.config.get_current_config() if instance else {}
        self._send_json({"ok": True, "bot_id": bot_id, "applied_config": applied})

    # ==================== Neural Network Handlers ====================

    def _get_neural_status(self) -> None:
        """Return neural network training status."""
        from nn_trainer import get_nn_trainer, _nn_trainer
        trainer = get_nn_trainer()
        
        # Debug: check if trainer instance is the same
        if _nn_trainer is not trainer:
            print(f"[DEBUG] WARNING: Trainer instance mismatch!")
        
        status = trainer.get_status()
        self._send_json({"ok": True, **status})

    def _get_neural_evaluate(self) -> None:
        """Evaluate a position using the neural network."""
        from urllib.parse import parse_qs
        from nn_trainer import get_nn_trainer
        
        query = parse_qs(urlparse(self.path).query)
        fen = query.get('fen', ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'])[0]
        
        trainer = get_nn_trainer()
        result = trainer.evaluate_position(fen)
        self._send_json(result)

    def _get_neural_current_game(self) -> None:
        """Return the current self-play game state for live preview."""
        from nn_trainer import get_nn_trainer
        trainer = get_nn_trainer()
        game = trainer.get_current_game()
        
        if game:
            self._send_json({"ok": True, "game": game})
        else:
            self._send_json({"ok": True, "game": None})

    def _post_neural_train(self) -> None:
        """Start neural network training."""
        from nn_trainer import get_nn_trainer
        
        body = self._read_json_body()
        trainer = get_nn_trainer()
        
        result = trainer.start_training(
            epochs=body.get('epochs', 10),
            batch_size=body.get('batch_size', 32),
            learning_rate=body.get('learning_rate', 0.01),
            include_self_play=body.get('include_self_play', True),
            self_play_games=body.get('self_play_games', 50)
        )
        
        self._send_json(result)

    def _post_neural_stop(self) -> None:
        """Stop neural network training."""
        from nn_trainer import get_nn_trainer
        trainer = get_nn_trainer()
        result = trainer.stop_training_session()
        self._send_json(result)

    def _post_neural_reset(self) -> None:
        """Reset neural network to random weights."""
        from nn_trainer import get_nn_trainer
        trainer = get_nn_trainer()
        result = trainer.reset_network()
        self._send_json(result)

    def _post_neural_learning_rate(self) -> None:
        """Update neural network learning rate."""
        from nn_trainer import get_nn_trainer
        
        body = self._read_json_body()
        rate = body.get('learning_rate', 0.01)
        
        trainer = get_nn_trainer()
        result = trainer.set_learning_rate(rate)
        self._send_json(result)

    def _post_neural_save_and_apply(self) -> None:
        """Save neural network weights and apply to bot."""
        from nn_trainer import get_nn_trainer
        from hybrid_evaluator import get_hybrid_evaluator
        from search import set_neural_evaluation
        from pathlib import Path
        import json
        
        body = self._read_json_body()
        neural_blend = body.get('neural_blend', 0.5)
        
        trainer = get_nn_trainer()
        
        # Save the network weights
        trainer.network.save_weights()
        trainer.data_collector.save_training_data()
        
        # Save the neural blend setting for persistence
        neural_config_path = Path(__file__).parent / "configs" / "neural_config.json"
        neural_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(neural_config_path, 'w') as f:
            json.dump({
                'neural_blend': neural_blend,
                'enabled': True,
                'version': trainer.network.version
            }, f)
        
        # Update the hybrid evaluator blend
        evaluator = get_hybrid_evaluator()
        evaluator.set_neural_blend(neural_blend)
        evaluator.reload_neural_network()
        
        # Enable neural evaluation in the search engine
        set_neural_evaluation(True)
        
        print(f"[ConfigAPI] Neural network saved and enabled with {neural_blend:.0%} blend")
        
        self._send_json({
            'ok': True,
            'message': f'Neural network saved and applied with {neural_blend:.0%} blend',
            'neural_blend': neural_blend,
            'network_version': trainer.network.version,
            'positions_trained': trainer.network.positions_trained
        })

    def _post_neural_blend(self) -> None:
        """Update the neural network blend ratio."""
        from hybrid_evaluator import get_hybrid_evaluator
        from search import set_neural_evaluation
        
        body = self._read_json_body()
        neural_blend = body.get('neural_blend', 0.5)
        
        evaluator = get_hybrid_evaluator()
        evaluator.set_neural_blend(neural_blend)
        
        # Enable/disable neural evaluation based on blend
        if neural_blend > 0:
            set_neural_evaluation(True)
        else:
            set_neural_evaluation(False)
        
        self._send_json({
            'ok': True,
            'neural_blend': neural_blend
        })

    def _post_neural_supervised_train(self) -> None:
        """Start supervised learning in a background thread."""
        import threading
        
        body = self._read_json_body()
        num_positions = body.get('num_positions', 5000)
        learning_rate = body.get('learning_rate', 0.01)
        epochs = body.get('epochs', 10)
        
        # Check if supervised training is already running
        global _supervised_training_state
        if _supervised_training_state.get('is_training', False):
            self._send_json({
                'ok': False,
                'error': 'Supervised training already in progress'
            })
            return
        
        # Initialize training state
        _supervised_training_state['is_training'] = True
        _supervised_training_state['current_epoch'] = 0
        _supervised_training_state['total_epochs'] = epochs
        _supervised_training_state['positions_trained'] = 0
        _supervised_training_state['target_positions'] = num_positions
        _supervised_training_state['current_loss'] = 0.0
        _supervised_training_state['phase'] = 'starting'
        
        # Start training in background thread
        training_thread = threading.Thread(
            target=_run_supervised_training,
            args=(num_positions, learning_rate, epochs),
            daemon=True
        )
        training_thread.start()
        
        print(f"[ConfigAPI] Started supervised training thread: {num_positions} positions, {epochs} epochs, lr={learning_rate}")
        
        self._send_json({
            'ok': True,
            'message': f'Supervised training started: {num_positions} positions, {epochs} epochs'
        })

    def _get_neural_supervised_status(self) -> None:
        """Get supervised training status."""
        global _supervised_training_state, _supervised_training_lock
        with _supervised_training_lock:
            state_copy = dict(_supervised_training_state)
        self._send_json({
            'ok': True,
            **state_copy
        })

    def _post_neural_live_supervised(self) -> None:
        """Toggle live supervised learning during Lichess games."""
        from pathlib import Path
        import json
        
        body = self._read_json_body()
        enabled = body.get('enabled', True)
        
        # Load existing config or create new
        neural_config_path = Path(__file__).parent / "configs" / "neural_config.json"
        neural_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config = {}
        if neural_config_path.exists():
            try:
                with open(neural_config_path, 'r') as f:
                    config = json.load(f)
            except Exception:
                pass
        
        # Update the live supervised learning setting
        config['live_supervised_learning'] = enabled
        
        with open(neural_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        status = "ENABLED" if enabled else "DISABLED"
        print(f"[ConfigAPI] Live supervised learning {status}")
        
        self._send_json({
            'ok': True,
            'live_supervised_learning': enabled,
            'message': f'Live supervised learning {status}'
        })

    # ==================== Checkpoint Management ====================

    def _get_neural_checkpoints(self) -> None:
        """List all available neural network checkpoints."""
        from nn_trainer import get_nn_trainer
        trainer = get_nn_trainer()
        checkpoints = trainer.network.list_checkpoints()
        self._send_json({
            'ok': True,
            'checkpoints': checkpoints
        })

    def _post_neural_checkpoint_save(self) -> None:
        """Save current network as a checkpoint."""
        from nn_trainer import get_nn_trainer
        
        body = self._read_json_body()
        name = body.get('name', 'checkpoint')
        description = body.get('description', '')
        
        if not name:
            self._send_json({'ok': False, 'error': 'Checkpoint name required'}, 400)
            return
        
        trainer = get_nn_trainer()
        result = trainer.network.save_checkpoint(name, description)
        self._send_json(result)

    def _post_neural_checkpoint_load(self) -> None:
        """Load a checkpoint."""
        from nn_trainer import get_nn_trainer
        
        body = self._read_json_body()
        filename = body.get('filename')
        
        if not filename:
            self._send_json({'ok': False, 'error': 'Checkpoint filename required'}, 400)
            return
        
        trainer = get_nn_trainer()
        result = trainer.network.load_checkpoint(filename)
        self._send_json(result)

    def _post_neural_checkpoint_delete(self) -> None:
        """Delete a checkpoint."""
        from nn_trainer import get_nn_trainer
        
        body = self._read_json_body()
        filename = body.get('filename')
        
        if not filename:
            self._send_json({'ok': False, 'error': 'Checkpoint filename required'}, 400)
            return
        
        trainer = get_nn_trainer()
        result = trainer.network.delete_checkpoint(filename)
        self._send_json(result)

    # ==================== Hybrid Training ====================

    def _get_neural_hybrid_status(self) -> None:
        """Get hybrid training status."""
        global _hybrid_training_state, _hybrid_training_lock
        with _hybrid_training_lock:
            state_copy = dict(_hybrid_training_state)
        self._send_json({
            'ok': True,
            **state_copy
        })

    def _post_neural_hybrid_train(self) -> None:
        """Start hybrid training (supervised + RL)."""
        import threading
        
        body = self._read_json_body()
        total_games = body.get('total_games', 1000)
        learning_rate = body.get('learning_rate', 0.01)
        supervised_ratio = body.get('supervised_ratio', 0.3)
        save_interval = body.get('save_interval', 100)
        
        global _hybrid_training_state, _hybrid_training_lock
        
        with _hybrid_training_lock:
            if _hybrid_training_state.get('is_training', False):
                self._send_json({
                    'ok': False,
                    'error': 'Hybrid training already in progress'
                })
                return
            
            _hybrid_training_state['is_training'] = True
            _hybrid_training_state['phase'] = 'starting'
            _hybrid_training_state['total_games'] = total_games
            _hybrid_training_state['games_completed'] = 0
            _hybrid_training_state['positions_trained'] = 0
            _hybrid_training_state['message'] = 'Initializing...'
        
        # Start training in background thread
        training_thread = threading.Thread(
            target=_run_hybrid_training,
            args=(total_games, learning_rate, supervised_ratio, 2, save_interval),
            daemon=True
        )
        training_thread.start()
        
        print(f"[ConfigAPI] Started hybrid training: {total_games} games, lr={learning_rate}, supervised_ratio={supervised_ratio}")
        
        self._send_json({
            'ok': True,
            'message': f'Hybrid training started: {total_games} games'
        })

    def _post_neural_hybrid_stop(self) -> None:
        """Stop hybrid training and save progress."""
        global _hybrid_training_state, _hybrid_training_lock
        
        with _hybrid_training_lock:
            _hybrid_training_state['is_training'] = False
            _hybrid_training_state['phase'] = 'stopping'
            _hybrid_training_state['message'] = 'Stopping and saving progress...'
        
        # Save current progress immediately
        try:
            from nn_trainer import get_nn_trainer
            trainer = get_nn_trainer()
            
            # Save weights
            trainer.network.save_weights()
            
            # Save a checkpoint with current progress
            games_done = _hybrid_training_state.get('games_completed', 0)
            positions = trainer.network.positions_trained
            trainer.network.save_checkpoint(
                f"hybrid_stopped_g{games_done}_{positions}pos",
                f"Stopped at game {games_done}, {positions} total positions"
            )
            
            # Hot-reload for Lichess
            try:
                from hybrid_evaluator import get_hybrid_evaluator
                evaluator = get_hybrid_evaluator()
                evaluator.reload_neural_network()
            except Exception:
                pass
            
            with _hybrid_training_lock:
                _hybrid_training_state['phase'] = 'stopped'
                _hybrid_training_state['message'] = f'Stopped & saved at game {games_done} ({positions} positions)'
            
            print(f"[HybridTraining] Stopped and saved: {games_done} games, {positions} positions")
            
            self._send_json({
                'ok': True,
                'message': f'Training stopped and saved ({games_done} games, {positions} positions)',
                'games_completed': games_done,
                'positions_trained': positions
            })
        except Exception as e:
            with _hybrid_training_lock:
                _hybrid_training_state['phase'] = 'stopped'
                _hybrid_training_state['message'] = f'Stopped (save error: {e})'
            
            self._send_json({
                'ok': True,
                'message': 'Training stopped (save may have failed)',
                'error': str(e)
            })


def run_server(port: int = 5050) -> None:
    """Run the config API server standalone."""
    server = HTTPServer(("localhost", port), ConfigAPIRequestHandler)
    print(f"[ConfigAPI] Listening on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
