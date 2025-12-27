"""Interactive wizard launcher for Chess Bot Studio.

Run with:

    python main.py --mode wizard

from inside the chess_bot_studio folder.
"""

import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from http.server import HTTPServer
from pathlib import Path
from typing import Optional

from .analysis import setup_logging
from .config_api_server import ConfigAPIRequestHandler
from .multi_bot_manager import get_bot_manager


PROJECT_ROOT = Path(__file__).resolve().parent
USER_PROFILE_PATH = PROJECT_ROOT / "configs" / "user_profile.json"


@dataclass
class UserProfile:
    lichess_token: Optional[str] = None
    preferred_bot_id: str = "aggressive_v1"
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


def _ensure_lichess_token(profile: UserProfile) -> UserProfile:
    if profile.lichess_token:
        return profile

    print("\n=== Step 1: Lichess Bot Token ===")
    print("A Lichess API token is required for the bot to play games.")
    print("Create one at: https://lichess.org/account/oauth/token (bot scope)")
    token = input("Paste your Lichess bot API token here (or leave blank to skip for now): ").strip()

    if token:
        profile.lichess_token = token
        _save_user_profile(profile)
        print("Saved Lichess token to local user profile.\n")
    else:
        print("No token provided. You can still use the UI for offline tuning, but the bot will not connect to Lichess.\n")

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
    if not profile.lichess_token:
        print("[Wizard] No Lichess token stored; skipping bot startup.")
        return

    manager = get_bot_manager()
    bot_id = profile.preferred_bot_id

    print(f"[Wizard] Starting bot instance '{bot_id}' with stored token...")
    success = manager.start_bot(bot_id, profile.lichess_token)

    if success:
        print(f"[Wizard] Bot '{bot_id}' started. It will join games on Lichess when challenged.")
    else:
        print(f"[Wizard] Failed to start bot '{bot_id}'. Check its config in configs/bots/{bot_id}.json.")


def run_wizard() -> None:
    print("\n=== Chess Bot Studio Wizard ===")

    profile = _load_user_profile()
    profile = _ensure_lichess_token(profile)

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
