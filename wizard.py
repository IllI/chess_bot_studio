"""Interactive wizard launcher for Chess Bot Studio."""

import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from http.server import HTTPServer
from pathlib import Path
from typing import Optional

from analysis import setup_logging
from config_api_server import ConfigAPIRequestHandler
from multi_bot_manager import get_bot_manager


PROJECT_ROOT = Path(__file__).resolve().parent
USER_PROFILE_PATH = PROJECT_ROOT / "configs" / "user_profile.json"


@dataclass
class UserProfile:
    lichess_token: Optional[str] = None
    preferred_bot_id: str = "aggressive_v1"
    strategy: str = "aggressive"
    ui_port: int = 8000
    api_port: int = 5050


def _load_user_profile() -> UserProfile:
    if USER_PROFILE_PATH.exists():
        try:
            with USER_PROFILE_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return UserProfile(**{**UserProfile().__dict__, **data})
        except Exception:
            return UserProfile()
    return UserProfile()


def _save_user_profile(profile: UserProfile) -> None:
    USER_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_PROFILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, indent=2)


def _ensure_user_profile(profile: UserProfile) -> UserProfile:
    # Just save defaults if they don't exist, don't prompt in console
    if not profile.preferred_bot_id:
        profile.preferred_bot_id = "aggressive_v1"
    
    _save_user_profile(profile)
    return profile


def _start_config_api_server(port: int) -> HTTPServer:
    setup_logging()
    server = HTTPServer(("localhost", port), ConfigAPIRequestHandler)

    def _serve() -> None:
        server.serve_forever()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    print(f"[Wizard] Config API server running at http://localhost:{port}")
    return server


def _start_ui_server(port: int) -> subprocess.Popen:
    ui_dir = PROJECT_ROOT
    cmd = [sys.executable, "-m", "http.server", str(port)]
    proc = subprocess.Popen(cmd, cwd=str(ui_dir))
    print(f"[Wizard] UI server running at http://localhost:{port}")
    return proc


def _start_preferred_bot(profile: UserProfile) -> None:
    manager = get_bot_manager()
    bot_id = profile.preferred_bot_id
    
    # Ensure bot exists with selected strategy
    existing = manager.get_bot_instance(bot_id)
    if not existing:
        print(f"[Wizard] Creating new bot '{bot_id}' with {profile.strategy} strategy...")
        
        # Define templates
        aggressive_config = {
            'piece_values': {'pawn': 100, 'knight': 320, 'bishop': 330, 'rook': 500, 'queen': 900, 'king': 0},
            'mobility_weight': 10.0,
            'search_depth': 4
        }
        defensive_config = {
            'piece_values': {'pawn': 100, 'knight': 310, 'bishop': 320, 'rook': 520, 'queen': 900, 'king': 0},
            'mobility_weight': 5.0,
            'search_depth': 4,
            'king_safety_penalty': {'open_file_near_king': -40, 'weak_pawn_shield': -30, 'king_in_center': -50, 'enemy_pieces_near_king': -20}
        }
        
        config = defensive_config if profile.strategy == "defensive" else aggressive_config
        success = manager.create_bot_instance(bot_id, config, f"{profile.strategy.capitalize()} Bot created via Wizard")
        if not success:
            print(f"[Wizard] Failed to create bot {bot_id}. Exiting.")
            return

    if not profile.lichess_token:
        print("[Wizard] No Lichess token stored; skipping bot startup.")
        print("[Wizard] To connect to Lichess, add your token to configs/user_profile.json")
        return

    print(f"[Wizard] Starting bot instance '{bot_id}' with Lichess connection...")
    try:
        success = manager.start_bot(bot_id, profile.lichess_token)

        if success:
            print(f"[Wizard] ✓ Bot '{bot_id}' started and connected to Lichess!")
            print(f"[Wizard] The bot will automatically accept challenges.")
        else:
            print(f"[Wizard] ✗ Failed to start bot '{bot_id}'.")
            print(f"[Wizard] Check that your Lichess token is valid and the account is a BOT account.")
    except Exception as e:
        print(f"[Wizard] ✗ Error starting bot: {e}")
        import traceback
        traceback.print_exc()


def run_wizard() -> None:
    print("\n=== Chess Bot Studio Wizard ===")

    profile = _load_user_profile()
    profile = _ensure_user_profile(profile)

    print("=== Step 2: Starting Services ===")
    api_server = _start_config_api_server(profile.api_port)
    ui_proc = _start_ui_server(profile.ui_port)
    _start_preferred_bot(profile)

    print("\nServices are up:")
    print(f"  • Architect UI:  http://localhost:{profile.ui_port}")
    print(f"  • Config API:    http://localhost:{profile.api_port}")
    print(f"  • Bot instance:  {profile.preferred_bot_id} (if token was provided)")
    print("\nOpen the UI, go to the Lab, and use 'Save to Model' to push heuristics into the bot config.")
    print("Press Ctrl+C here to stop all services when you are done.\n")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[Wizard] Shutting down services...")
        try:
            api_server.shutdown()
        except Exception:
            pass
        try:
            ui_proc.terminate()
            ui_proc.wait(timeout=5)
        except Exception:
            pass
        print("[Wizard] All services stopped. Goodbye.")


if __name__ == "__main__":
    run_wizard()
