#!/usr/bin/env python3
"""Main entry point for Chess Bot Studio (self-contained in this folder)."""

import argparse
import subprocess
import sys
from analysis import setup_logging
from custom_lichess_bot import LichessBotClient
from multi_bot_cli import main as multi_bot_main
from wizard import run_wizard


def kill_processes_on_ports(*ports):
    """Kill any processes listening on the specified ports (Windows only)."""
    if sys.platform != 'win32':
        return
    
    for port in ports:
        try:
            # Find PIDs listening on the port
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            pids_to_kill = set()
            for line in result.stdout.splitlines():
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if parts:
                        try:
                            pid = int(parts[-1])
                            if pid != 0:
                                pids_to_kill.add(pid)
                        except ValueError:
                            pass
            
            # Kill each PID
            for pid in pids_to_kill:
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                    )
                except Exception:
                    pass
        except Exception:
            pass


def main():
    """Main function to run Chess Bot Studio."""
    parser = argparse.ArgumentParser(description='Chess Bot Studio')
    parser.add_argument('--mode', choices=['bot', 'analyze', 'test', 'multi-bot', 'wizard'], 
                       default='test', help='Run mode')

    parser.add_argument('--token', help='Lichess API token')
    parser.add_argument('--depth', type=int, default=4, 
                       help='Search depth')
    
    # Use parse_known_args to allow sub-commands for multi-bot mode
    args, remaining = parser.parse_known_args()
    
    # Set up logging
    setup_logging()
    
    if args.mode == 'bot':

        # LichessBotClient will automatically try to load from .env if token is None
        try:
            bot = LichessBotClient(args.token)
            print("Starting Lichess bot...")
            bot.main_loop()
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.mode == 'multi-bot':

        # Delegate to multi-bot CLI with remaining arguments
        print("Starting multi-bot management interface...")
        multi_bot_main(remaining)
    
    elif args.mode == 'test':

        print("Chess Bot Studio - Test Mode")
        print("Project structure created successfully!")
        print("Available modes:")
        print("1. Single bot: python main.py --mode bot --token YOUR_TOKEN")
        print("2. Multi-bot management: python main.py --mode multi-bot bot create <bot-id>")
        print("3. Analysis: python main.py --mode analyze")
        print("4. Wizard (one-click lab): python main.py --mode wizard")

        print("\nFor multi-bot A/B testing:")
        print("- Create bots: python main.py --mode multi-bot bot create <bot-id>")
        print("- Start A/B test: python main.py --mode multi-bot ab-test create <bot1> <bot2>")
    
    elif args.mode == 'analyze':
        print("Analysis mode - coming soon!")

    elif args.mode == 'wizard':
        # Kill any stale processes on our ports before starting
        kill_processes_on_ports(5050, 8000)
        # Interactive launcher that starts UI, config API, and preferred bot
        run_wizard()


if __name__ == '__main__':
    main()