#!/usr/bin/env python3
"""
Main entry point for Chess Engine Tuner.
"""

import argparse
import sys
from chess_engine_tuner.analysis import setup_logging
from chess_engine_tuner.custom_lichess_bot import LichessBotClient
from chess_engine_tuner.multi_bot_cli import main as multi_bot_main


def main():
    """Main function to run the chess engine tuner."""
    parser = argparse.ArgumentParser(description='Chess Engine Tuner')
    parser.add_argument('--mode', choices=['bot', 'analyze', 'test', 'multi-bot'], 
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
        print("Chess Engine Tuner - Test Mode")
        print("Project structure created successfully!")
        print("Available modes:")
        print("1. Single bot: python main.py --mode bot --token YOUR_TOKEN")
        print("2. Multi-bot management: python main.py --mode multi-bot bot create <bot-id>")
        print("3. Analysis: python main.py --mode analyze")
        print("\nFor multi-bot A/B testing:")
        print("- Create bots: python main.py --mode multi-bot bot create <bot-id>")
        print("- Start A/B test: python main.py --mode multi-bot ab-test create <bot1> <bot2>")
    
    elif args.mode == 'analyze':
        print("Analysis mode - coming soon!")


if __name__ == '__main__':
    main()