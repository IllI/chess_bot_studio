import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from multi_bot_manager import get_bot_manager
from config import DEFAULT_CONFIG


class ConfigAPIRequestHandler(BaseHTTPRequestHandler):
    """Minimal HTTP API for updating bot configurations from the UI.

    Endpoints:
      - POST /api/save-config/<bot_id>
        Body: { "config": { ...ui_config... } }
    """

    def _set_common_headers(self, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._set_common_headers(200)

    def do_GET(self) -> None:  # noqa: N802
        print(f"[ConfigAPI] Received GET {self.path}")
        try:
            if self.path == "/api/active-bots":
                print("[ConfigAPI] retrieving bot manager...")
                try:
                    bot_manager = get_bot_manager()
                    print(f"[ConfigAPI] manager retrieved: {id(bot_manager)}")
                except Exception as e:
                    print(f"[ConfigAPI] Failed to get manager: {e}")
                    raise
                
                print("[ConfigAPI] accessing active_bots...")
                active_bots = list(bot_manager.active_bots.keys())
                print(f"[ConfigAPI] active_bots: {active_bots}")
                
                self._set_common_headers(200)
                self.wfile.write(json.dumps({"ok": True, "active_bots": active_bots}).encode("utf-8"))
                print("[ConfigAPI] Response sent")
            elif self.path.startswith("/api/get-config/"):
                bot_id = self.path.rsplit("/", 1)[-1]
                print(f"[ConfigAPI] Retrieving config for {bot_id}...")
                bot_manager = get_bot_manager()
                instance = bot_manager.get_bot_instance(bot_id)
                if instance:
                    conf = instance.config.get_current_config()
                    # Flatten/adapt for UI if necessary, but UI seems to expect raw structure mostly
                    # UI expects: piece_values, mobility_weight, king_safety (derived), search_depth
                    
                    # Convert internal king_safety_penalty dict back to a single scalar for UI if possible
                    # or just send the raw config and let UI handle it. 
                    # The UI currently expects 'king_safety' as a number [0-200].
                    # We can roughly estimate it or just send what we have.
                    # For now, let's send the text config.
                    
                    # NOTE: UI expects 'king_safety' property which is not in our internal config (we have king_safety_penalty dict)
                    # We should derive it.
                    # Heuristic: Take penalty of 'open_file_near_king' and divide by approximate scale factor from saving
                    # Saving logic: scaled_penalty = base * (slider / 20.0) -> slider = (penalty / base) * 20
                    # base for open_file is -30. 
                    # If current is -30, slider is 20. If current is -60, slider is 40.
                    
                    ks_dict = conf.get("king_safety_penalty", {})
                    open_file = ks_dict.get("open_file_near_king", -30) # default -30
                    # Inverse of: scaled = int(v * scale), scale = slider/20
                    # Using open_file (-30 base) as proxy
                    # scale = current / base
                    # slider = scale * 20
                    
                    try:
                        base = -30
                        scale = open_file / base
                        estimated_slider = int(scale * 20)
                    except:
                        estimated_slider = 20

                    response_data = {
                        "piece_values": conf.get("piece_values", {}),
                        "mobility_weight": conf.get("mobility_weight", 10),
                        "search_depth": conf.get("search_depth", 4),
                        "king_safety": estimated_slider
                    }
                    
                    self._set_common_headers(200)
                    self.wfile.write(json.dumps({"ok": True, "config": response_data}).encode("utf-8"))
                else:
                    self._set_common_headers(404)
                    self.wfile.write(json.dumps({"ok": False, "error": "Bot not found"}).encode("utf-8"))
            else:
                self._set_common_headers(404)
                self.wfile.write(json.dumps({"ok": False, "error": "Not found"}).encode("utf-8"))
        except Exception as e:
            print(f"[ConfigAPI] Error in do_GET: {e}")
            import traceback
            traceback.print_exc()
            self._set_common_headers(500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path.startswith("/api/save-config/"):
                bot_id = self.path.rsplit("/", 1)[-1]
                self._handle_save_config(bot_id)
            else:
                self._set_common_headers(404)
                self.wfile.write(json.dumps({"ok": False, "error": "Not found"}).encode("utf-8"))
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._set_common_headers(500)
            self.wfile.write(json.dumps({"ok": False, "error": f"Internal error: {exc}"}).encode("utf-8"))

    def _read_json_body(self) -> Dict[str, Any]:
        length_header = self.headers.get("Content-Length")
        if not length_header:
            return {}
        try:
            length = int(length_header)
            raw = self.rfile.read(length)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(f"[ConfigAPI] JSON parse error: {e}")
            return {}

    def _handle_save_config(self, bot_id: str) -> None:
        # Get manager dynamically
        bot_manager = get_bot_manager()
        print(f"[ConfigAPI] Handling save for bot '{bot_id}'. Manager ID: {id(bot_manager)}")
        print(f"[ConfigAPI] Known bots: {list(bot_manager.bot_instances.keys())}")
        
        body = self._read_json_body()
        ui_config = body.get("config")

        if not isinstance(ui_config, dict):
            print(f"[ConfigAPI] Invalid body or config: {body}")
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"ok": False, "error": "Missing or invalid 'config' in request body"}).encode("utf-8"))
            return

        # Map the lightweight UI config into full engine parameters expected by BotInstanceManager.
        updates: Dict[str, Any] = {}

        # 1) Piece values
        if "piece_values" in ui_config:
            default_pieces = DEFAULT_CONFIG["piece_values"]
            incoming_pieces = ui_config["piece_values"] or {}
            merged_pieces = {**default_pieces, **incoming_pieces}
            updates["piece_values"] = merged_pieces

        # 2) Mobility weight
        if "mobility_weight" in ui_config:
            updates["mobility_weight"] = ui_config["mobility_weight"]

        # 3) Search depth
        if "search_depth" in ui_config:
            updates["search_depth"] = ui_config["search_depth"]

        # 4) King safety slider -> expanded king_safety_penalty dict
        if "king_safety" in ui_config:
            slider_value = ui_config["king_safety"]
            base_penalty = DEFAULT_CONFIG["king_safety_penalty"]

            try:
                scale = float(slider_value) / 20.0 if slider_value is not None else 1.0
            except (TypeError, ValueError):
                scale = 1.0

            if scale < 0.25:
                scale = 0.25
            if scale > 4.0:
                scale = 4.0

            scaled_penalty = {k: int(v * scale) for k, v in base_penalty.items()}
            updates["king_safety_penalty"] = scaled_penalty

        if not updates:
            print(f"[ConfigAPI] No updates found in ui_config: {ui_config}")
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"ok": False, "error": "No recognized parameters in config"}).encode("utf-8"))
            return

        success = bot_manager.update_bot_configuration(bot_id, updates)
        
        if not success:
            error_msg = f"Failed to update configuration for bot '{bot_id}'"
            print(f"[ConfigAPI] Error: {error_msg}")
            # Try to see if bot exists
            if bot_id not in bot_manager.bot_instances:
                 print(f"[ConfigAPI] Reason: Bot ID '{bot_id}' not found in loaded instances: {list(bot_manager.bot_instances.keys())}")
            
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"ok": False, "error": error_msg}).encode("utf-8"))
            return

        bot_instance = bot_manager.get_bot_instance(bot_id)
        applied_config: Dict[str, Any] = bot_instance.config.get_current_config() if bot_instance else {}

        self._set_common_headers(200)
        self.wfile.write(json.dumps({"ok": True, "bot_id": bot_id, "applied_config": applied_config}).encode("utf-8"))


def run_server(port: int = 5050) -> None:
    """Run the config API server.

    Typically invoked indirectly by the wizard, but can be run on its own:

        python -m chess_bot_studio.config_api_server
    """

    server_address = ("localhost", port)
    httpd = HTTPServer(server_address, ConfigAPIRequestHandler)
    print(f"[ConfigAPI] Listening on http://{server_address[0]}:{server_address[1]}")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
