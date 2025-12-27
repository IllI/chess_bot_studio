import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from .multi_bot_manager import get_bot_manager
from .config import DEFAULT_CONFIG


class ConfigAPIRequestHandler(BaseHTTPRequestHandler):
    """Minimal HTTP API for updating bot configurations from the UI.

    Endpoints:
      - POST /api/save-config/<bot_id>
        Body: { "config": { ...ui_config... } }
    """

    bot_manager = get_bot_manager()

    def _set_common_headers(self, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "OPTIONS, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._set_common_headers(200)

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path.startswith("/api/save-config/"):
                bot_id = self.path.rsplit("/", 1)[-1]
                self._handle_save_config(bot_id)
            else:
                self._set_common_headers(404)
                self.wfile.write(json.dumps({"ok": False, "error": "Not found"}).encode("utf-8"))
        except Exception as exc:
            self._set_common_headers(500)
            self.wfile.write(json.dumps({"ok": False, "error": f"Internal error: {exc}"}).encode("utf-8"))

    def _read_json_body(self) -> Dict[str, Any]:
        length_header = self.headers.get("Content-Length")
        if not length_header:
            return {}
        length = int(length_header)
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _handle_save_config(self, bot_id: str) -> None:
        body = self._read_json_body()
        ui_config = body.get("config")

        if not isinstance(ui_config, dict):
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
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"ok": False, "error": "No recognized parameters in config"}).encode("utf-8"))
            return

        success = self.bot_manager.update_bot_configuration(bot_id, updates)

        if not success:
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"ok": False, "error": f"Failed to update configuration for bot '{bot_id}'"}).encode("utf-8"))
            return

        bot_instance = self.bot_manager.get_bot_instance(bot_id)
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
