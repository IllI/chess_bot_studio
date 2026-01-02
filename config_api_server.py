"""
Config API Server for Chess Bot Studio.
Provides REST endpoints for the training UI.
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Callable
from urllib.parse import urlparse

from multi_bot_manager import get_bot_manager
from config import DEFAULT_CONFIG


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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
            "/api/neural/bootstrap": self._post_neural_bootstrap,
            "/api/neural/learning-rate": self._post_neural_learning_rate,
            "/api/neural/save-and-apply": self._post_neural_save_and_apply,
            "/api/neural/blend": self._post_neural_blend,
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

    def _post_neural_bootstrap(self) -> None:
        """Bootstrap neural network with supervised learning from heuristic."""
        from nn_trainer import get_nn_trainer
        
        body = self._read_json_body()
        num_positions = body.get('num_positions', 2000)
        
        trainer = get_nn_trainer()
        
        # Run supervised training
        result = trainer.network.train_supervised_from_heuristic(num_positions)
        
        # Also train on tactical positions
        tactical_result = trainer.network.train_on_tactical_positions()
        
        self._send_json({
            'ok': True,
            'supervised': result,
            'tactical': tactical_result,
            'message': f'Bootstrapped network with {result["positions_trained"]} positions'
        })

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


def run_server(port: int = 5050) -> None:
    """Run the config API server standalone."""
    server = HTTPServer(("localhost", port), ConfigAPIRequestHandler)
    print(f"[ConfigAPI] Listening on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
