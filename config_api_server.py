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
        from evolution import get_optimizer
        optimizer = get_optimizer()
        status = optimizer.get_status()
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


def run_server(port: int = 5050) -> None:
    """Run the config API server standalone."""
    server = HTTPServer(("localhost", port), ConfigAPIRequestHandler)
    print(f"[ConfigAPI] Listening on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
