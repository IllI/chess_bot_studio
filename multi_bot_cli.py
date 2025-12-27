import argparse
import sys
import json
import logging
from typing import Dict, Any, Optional
from .multi_bot_manager import get_bot_manager
from .ab_testing import get_ab_test_manager

class MultiBotCLI:
    """CLI for managing multiple bot instances and A/B testing."""
    
    def __init__(self):
        self.bot_manager = get_bot_manager()
        self.ab_manager = get_ab_test_manager()
        self.logger = logging.getLogger("MultiBotCLI")

    def create_bot(self, args) -> None:
        """Create a new bot instance."""
        config = None
        if args.config_file:
            try:
                with open(args.config_file, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Error loading config file: {e}")
                return
        
        success = self.bot_manager.create_bot_instance(
            bot_id=args.bot_id,
            config=config,
            description=args.description or ""
        )
        
        if success:
            print(f"Successfully created bot instance: {args.bot_id}")
        else:
            print(f"Failed to create bot instance: {args.bot_id}")
    
    def list_bots(self, args) -> None:
        """List all bot instances."""
        instances = self.bot_manager.list_bot_instances()
        
        if not instances:
            print("No bot instances found.")
            return
        
        print(f"{'Bot ID':<20} {'Status':<10} {'Description':<30}")
        print("-" * 65)
        
        for instance in instances:
            status = "Active" if instance['is_active'] else "Inactive"
            description = instance['description'][:27] + "..." if len(instance['description']) > 30 else instance['description']
            print(f"{instance['bot_id']:<20} {status:<10} {description:<30}")
    
    def start_bot(self, args) -> None:
        """Start a bot instance."""
        # LichessBotClient will automatically try to load from .env if token is None
        success = self.bot_manager.start_bot(args.bot_id, args.token)
        
        if success:
            print(f"Successfully started bot: {args.bot_id}")
        else:
            print(f"Failed to start bot: {args.bot_id}")
    
    def stop_bot(self, args) -> None:
        """Stop a bot instance."""
        success = self.bot_manager.stop_bot(args.bot_id)
        
        if success:
            print(f"Successfully stopped bot: {args.bot_id}")
        else:
            print(f"Failed to stop bot: {args.bot_id}")
    
    def delete_bot(self, args) -> None:
        """Delete a bot instance."""
        if not args.force:
            response = input(f"Are you sure you want to delete bot '{args.bot_id}'? (y/N): ")
            if response.lower() != 'y':
                print("Deletion cancelled.")
                return
        
        success = self.bot_manager.delete_bot_instance(args.bot_id)
        
        if success:
            print(f"Successfully deleted bot: {args.bot_id}")
        else:
            print(f"Failed to delete bot: {args.bot_id}")
    
    def update_bot_config(self, args) -> None:
        """Update bot configuration."""
        try:
            with open(args.config_file, 'r') as f:
                updates = json.load(f)
        except Exception as e:
            print(f"Error loading config file: {e}")
            return
        
        success = self.bot_manager.update_bot_configuration(args.bot_id, updates)
        
        if success:
            print(f"Successfully updated configuration for bot: {args.bot_id}")
        else:
            print(f"Failed to update configuration for bot: {args.bot_id}")
    
    def show_bot_config(self, args) -> None:
        """Show bot configuration."""
        bot_instance = self.bot_manager.get_bot_instance(args.bot_id)
        
        if not bot_instance:
            print(f"Bot instance not found: {args.bot_id}")
            return
        
        config = bot_instance.config.get_current_config()
        print(f"Configuration for bot '{args.bot_id}':")
        print(json.dumps(config, indent=2))
    
    def check_conflicts(self, args) -> None:
        """Check for configuration conflicts."""
        conflicts = self.bot_manager.prevent_configuration_conflicts()
        
        if not conflicts:
            print("No configuration conflicts detected.")
        else:
            print("Configuration conflicts detected:")
            for conflict in conflicts:
                print(f"  - {conflict}")
    
    def create_ab_test(self, args) -> None:
        """Create an A/B test suite."""
        time_control = None
        if args.time_control:
            try:
                time_control = json.loads(args.time_control)
            except Exception as e:
                print(f"Error parsing time control: {e}")
                return
        
        suite_id = self.ab_manager.create_test_suite(
            bot1_id=args.bot1_id,
            bot2_id=args.bot2_id,
            num_games=args.num_games,
            time_control=time_control,
            description=args.description or ""
        )
        
        if suite_id:
            print(f"Successfully created A/B test suite: {suite_id}")
        else:
            print("Failed to create A/B test suite")
    
    def start_ab_test(self, args) -> None:
        """Start an A/B test suite."""
        success = self.ab_manager.start_test_suite(args.suite_id)
        
        if success:
            print(f"Successfully started A/B test suite: {args.suite_id}")
        else:
            print(f"Failed to start A/B test suite: {args.suite_id}")
    
    def stop_ab_test(self, args) -> None:
        """Stop an A/B test suite."""
        success = self.ab_manager.stop_test_suite(args.suite_id)
        
        if success:
            print(f"Successfully stopped A/B test suite: {args.suite_id}")
        else:
            print(f"Failed to stop A/B test suite: {args.suite_id}")
    
    def list_ab_tests(self, args) -> None:
        """List A/B test suites."""
        suites = self.ab_manager.list_test_suites()
        
        if not suites:
            print("No A/B test suites found.")
            return
        
        print(f"{'Suite ID':<30} {'Status':<12} {'Progress':<10} {'Bots':<25}")
        print("-" * 80)
        
        for suite in suites:
            progress = f"{suite['progress']:.0%}"
            bots = f"{suite['bot1_id']} vs {suite['bot2_id']}"
            if len(bots) > 22:
                bots = bots[:19] + "..."
            
            print(f"{suite['suite_id']:<30} {suite['status']:<12} {progress:<10} {bots:<25}")
    
    def show_ab_test_results(self, args) -> None:
        """Show A/B test results."""
        status = self.ab_manager.get_test_suite_status(args.suite_id)
        
        if not status:
            print(f"A/B test suite not found: {args.suite_id}")
            return
        
        print(f"A/B Test Suite: {args.suite_id}")
        print(f"Status: {status['status']}")
        print(f"Progress: {status['completed_matches']}/{status['total_matches']} matches")
        print(f"Bots: {status['bot1_id']} vs {status['bot2_id']}")
        
        if status['results_summary']:
            results = status['results_summary']
            print("\nResults:")
            print(f"  {status['bot1_id']}: {results['bot1_wins']} wins, {results['bot1_score']:.1f} points ({results['bot1_win_rate']:.1%})")
            print(f"  {status['bot2_id']}: {results['bot2_wins']} wins, {results['bot2_score']:.1f} points ({results['bot2_win_rate']:.1%})")
            print(f"  Draws: {results['draws']}")
            print(f"  Performance difference: {results['performance_difference']:.1%}")
            print(f"  Statistical significance: {results['statistical_significance']}")
            print(f"  Winner: {results['winner']}")
    
    def export_bot_config(self, args) -> None:
        """Export bot configuration to file."""
        bot_instance = self.bot_manager.get_bot_instance(args.bot_id)
        
        if not bot_instance:
            print(f"Bot instance not found: {args.bot_id}")
            return
        
        success = bot_instance.config.export_config(args.output_file)
        
        if success:
            print(f"Successfully exported configuration to: {args.output_file}")
        else:
            print(f"Failed to export configuration")
    
    def import_bot_config(self, args) -> None:
        """Import bot configuration from file."""
        bot_instance = self.bot_manager.get_bot_instance(args.bot_id)
        
        if not bot_instance:
            print(f"Bot instance not found: {args.bot_id}")
            return
        
        success = bot_instance.config.import_config(args.config_file)
        
        if success:
            print(f"Successfully imported configuration from: {args.config_file}")
        else:
            print(f"Failed to import configuration")

    def challenge_user(self, args) -> None:
        """Challenge a user from a bot instance."""
        active_bots = self.bot_manager.active_bots
        if args.bot_id not in active_bots:
            print(f"Error: Bot '{args.bot_id}' is not currently active. Start it first.")
            return
            
        bot_client = active_bots[args.bot_id]
        time_control = None
        if args.time_control:
            try:
                time_control = json.loads(args.time_control)
            except Exception as e:
                print(f"Error parsing time control JSON: {e}")
                return
                
        success = bot_client.create_challenge(args.username, time_control)
        if success:
            print(f"Successfully sent challenge to {args.username} from {args.bot_id}")
        else:
            print(f"Failed to send challenge to {args.username}")


def main(args_list=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Multi-Bot Chess Engine Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Bot management commands
    bot_parser = subparsers.add_parser('bot', help='Bot management commands')
    bot_subparsers = bot_parser.add_subparsers(dest='bot_command')
    
    # Create bot
    create_parser = bot_subparsers.add_parser('create', help='Create a new bot instance')
    create_parser.add_argument('bot_id', help='Unique bot identifier')
    create_parser.add_argument('--config-file', help='JSON configuration file')
    create_parser.add_argument('--description', help='Bot description')
    
    # List bots
    bot_subparsers.add_parser('list', help='List all bot instances')
    
    # Start bot
    start_parser = bot_subparsers.add_parser('start', help='Start a bot instance')
    start_parser.add_argument('bot_id', help='Bot identifier')
    start_parser.add_argument('--token', help='Lichess API token')
    
    # Stop bot
    stop_parser = bot_subparsers.add_parser('stop', help='Stop a bot instance')
    stop_parser.add_argument('bot_id', help='Bot identifier')
    
    # Delete bot
    delete_parser = bot_subparsers.add_parser('delete', help='Delete a bot instance')
    delete_parser.add_argument('bot_id', help='Bot identifier')
    delete_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    # Update bot config
    update_parser = bot_subparsers.add_parser('update', help='Update bot configuration')
    update_parser.add_argument('bot_id', help='Bot identifier')
    update_parser.add_argument('config_file', help='JSON configuration updates file')
    
    # Show bot config
    show_config_parser = bot_subparsers.add_parser('config', help='Show bot configuration')
    show_config_parser.add_argument('bot_id', help='Bot identifier')
    
    # Check conflicts
    bot_subparsers.add_parser('conflicts', help='Check for configuration conflicts')
    
    # Export config
    export_parser = bot_subparsers.add_parser('export', help='Export bot configuration')
    export_parser.add_argument('bot_id', help='Bot identifier')
    export_parser.add_argument('output_file', help='Output file path')
    
    # Import config
    import_parser = bot_subparsers.add_parser('import', help='Import bot configuration')
    import_parser.add_argument('bot_id', help='Bot identifier')
    import_parser.add_argument('config_file', help='Configuration file to import')

    # Challenge user
    challenge_parser = bot_subparsers.add_parser('challenge', help='Send a challenge to a user')
    challenge_parser.add_argument('bot_id', help='Bot identifier')
    challenge_parser.add_argument('username', help='Username to challenge')
    challenge_parser.add_argument('--time-control', help='Time control JSON (e.g., {"limit": 300, "increment": 3})')
    
    # A/B testing commands
    ab_parser = subparsers.add_parser('ab-test', help='A/B testing commands')
    ab_subparsers = ab_parser.add_subparsers(dest='ab_command')
    
    # Create A/B test
    ab_create_parser = ab_subparsers.add_parser('create', help='Create A/B test suite')
    ab_create_parser.add_argument('bot1_id', help='First bot identifier')
    ab_create_parser.add_argument('bot2_id', help='Second bot identifier')
    ab_create_parser.add_argument('--num-games', type=int, default=10, help='Number of games')
    ab_create_parser.add_argument('--time-control', help='Time control JSON (e.g., {"limit": 300, "increment": 3})')
    ab_create_parser.add_argument('--description', help='Test description')
    
    # Start A/B test
    ab_start_parser = ab_subparsers.add_parser('start', help='Start A/B test suite')
    ab_start_parser.add_argument('suite_id', help='Test suite identifier')
    
    # Stop A/B test
    ab_stop_parser = ab_subparsers.add_parser('stop', help='Stop A/B test suite')
    ab_stop_parser.add_argument('suite_id', help='Test suite identifier')
    
    # List A/B tests
    ab_subparsers.add_parser('list', help='List A/B test suites')
    
    # Show A/B test results
    ab_results_parser = ab_subparsers.add_parser('results', help='Show A/B test results')
    ab_results_parser.add_argument('suite_id', help='Test suite identifier')
    
    args = parser.parse_args(args_list)
    
    if not args.command:
        parser.print_help()
        return
    
    cli = MultiBotCLI()
    
    try:
        if args.command == 'bot':
            if args.bot_command == 'create':
                cli.create_bot(args)
            elif args.bot_command == 'list':
                cli.list_bots(args)
            elif args.bot_command == 'start':
                cli.start_bot(args)
            elif args.bot_command == 'stop':
                cli.stop_bot(args)
            elif args.bot_command == 'delete':
                cli.delete_bot(args)
            elif args.bot_command == 'update':
                cli.update_bot_config(args)
            elif args.bot_command == 'config':
                cli.show_bot_config(args)
            elif args.bot_command == 'conflicts':
                cli.check_conflicts(args)
            elif args.bot_command == 'export':
                cli.export_bot_config(args)
            elif args.bot_command == 'import':
                cli.import_bot_config(args)
            elif args.bot_command == 'challenge':
                cli.challenge_user(args)
            else:
                bot_parser.print_help()
        
        elif args.command == 'ab-test':
            if args.ab_command == 'create':
                cli.create_ab_test(args)
            elif args.ab_command == 'start':
                cli.start_ab_test(args)
            elif args.ab_command == 'stop':
                cli.stop_ab_test(args)
            elif args.ab_command == 'list':
                cli.list_ab_tests(args)
            elif args.ab_command == 'results':
                cli.show_ab_test_results(args)
            else:
                ab_parser.print_help()
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()