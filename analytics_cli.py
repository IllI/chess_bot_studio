#!/usr/bin/env python3
"""
Command-line interface for chess engine analytics and performance comparison.

This module provides a CLI for analyzing game logs, comparing configurations,
and exporting performance data for external analysis.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

try:
    from .analytics import PerformanceAnalyzer, GameLogger
    from .config import ChessConfig
except ImportError:
    from analytics import PerformanceAnalyzer, GameLogger
    from config import ChessConfig


def format_metrics_table(metrics_list, title="Performance Metrics"):
    """Format performance metrics as a readable table."""
    if not metrics_list:
        return f"{title}: No data available"
    
    # Header
    output = [f"\n{title}"]
    output.append("=" * len(title))
    output.append("")
    
    # Table header
    header = f"{'Config ID':<15} {'Games':<6} {'Win Rate':<8} {'Avg Rating':<10} {'Rating Δ':<9} {'Avg Depth':<9}"
    output.append(header)
    output.append("-" * len(header))
    
    # Table rows
    for metrics in metrics_list:
        row = (f"{metrics.config_id:<15} "
               f"{metrics.total_games:<6} "
               f"{metrics.win_rate*100:>6.1f}% "
               f"{metrics.average_opponent_rating:<10} "
               f"{metrics.rating_change_total:>+8} "
               f"{metrics.search_depth_average:>8.1f}")
        output.append(row)
    
    return "\n".join(output)


def format_comparison_result(comparison):
    """Format comparison result as readable text."""
    if not comparison:
        return "No comparison data available"
    
    config_a = comparison['config_a']
    config_b = comparison['config_b']
    comp = comparison['comparison']
    
    output = ["\nConfiguration Comparison"]
    output.append("=" * 24)
    output.append("")
    
    # Basic stats
    output.append(f"Configuration A: {config_a['id']}")
    output.append(f"  Games: {config_a['metrics']['total_games']}")
    output.append(f"  Win Rate: {config_a['metrics']['win_rate']*100:.1f}%")
    output.append(f"  Rating Change: {config_a['metrics']['rating_change_total']:+}")
    output.append("")
    
    output.append(f"Configuration B: {config_b['id']}")
    output.append(f"  Games: {config_b['metrics']['total_games']}")
    output.append(f"  Win Rate: {config_b['metrics']['win_rate']*100:.1f}%")
    output.append(f"  Rating Change: {config_b['metrics']['rating_change_total']:+}")
    output.append("")
    
    # Comparison results
    output.append("Comparison Results:")
    output.append(f"  Win Rate Difference: {comp['win_rate_difference']*100:+.1f}%")
    output.append(f"  Rating Change Difference: {comp['rating_change_difference']:+.1f}")
    output.append(f"  Statistically Significant: {comp['statistically_significant']}")
    output.append(f"  Better Configuration: {comp['better_config']}")
    output.append("")
    
    output.append(f"Recommendation: {comparison['summary']['recommendation']}")
    
    return "\n".join(output)


def cmd_list_configs(args):
    """List all available configurations."""
    analyzer = PerformanceAnalyzer(args.log_dir)
    configs = analyzer.get_all_configurations()
    
    if not configs:
        print("No configurations found in log files.")
        return
    
    print(f"\nFound {len(configs)} configuration(s):")
    for i, config_id in enumerate(configs, 1):
        metrics = analyzer.calculate_performance_metrics(config_id, min_games=1)
        if metrics:
            print(f"{i:2}. {config_id} ({metrics.total_games} games, "
                  f"{metrics.win_rate*100:.1f}% win rate)")
        else:
            print(f"{i:2}. {config_id} (no valid data)")


def cmd_show_metrics(args):
    """Show performance metrics for configurations."""
    analyzer = PerformanceAnalyzer(args.log_dir)
    
    if args.config_id:
        # Show specific configuration
        metrics = analyzer.calculate_performance_metrics(args.config_id, args.min_games)
        if metrics:
            print(format_metrics_table([metrics], f"Metrics for {args.config_id}"))
        else:
            print(f"No sufficient data for configuration '{args.config_id}' "
                  f"(minimum {args.min_games} games required)")
    else:
        # Show all configurations
        configs = analyzer.get_all_configurations()
        metrics_list = []
        
        for config_id in configs:
            metrics = analyzer.calculate_performance_metrics(config_id, args.min_games)
            if metrics:
                metrics_list.append(metrics)
        
        if metrics_list:
            # Sort by win rate descending
            metrics_list.sort(key=lambda m: m.win_rate, reverse=True)
            print(format_metrics_table(metrics_list, "All Configurations"))
        else:
            print(f"No configurations with sufficient data (minimum {args.min_games} games)")


def cmd_compare(args):
    """Compare two configurations."""
    analyzer = PerformanceAnalyzer(args.log_dir)
    
    comparison = analyzer.compare_configurations(args.config_a, args.config_b, args.min_games)
    
    if comparison:
        print(format_comparison_result(comparison))
    else:
        print(f"Cannot compare configurations. Each needs at least {args.min_games} games.")


def cmd_ab_test(args):
    """Run A/B test analysis."""
    analyzer = PerformanceAnalyzer(args.log_dir)
    
    ab_test = analyzer.run_ab_test_analysis(args.config_a, args.config_b, args.target_games)
    
    if not ab_test:
        print("Error running A/B test analysis")
        return
    
    setup = ab_test['test_setup']
    status = ab_test['current_status']
    recs = ab_test['recommendations']
    
    print(f"\nA/B Test Analysis")
    print("=" * 17)
    print(f"Configuration A: {setup['config_a']}")
    print(f"Configuration B: {setup['config_b']}")
    print(f"Target games per config: {setup['target_games_per_config']}")
    print("")
    
    print("Current Progress:")
    print(f"  Config A: {status['games_a']} games ({status['progress_a']*100:.1f}%)")
    print(f"  Config B: {status['games_b']} games ({status['progress_b']*100:.1f}%)")
    print(f"  Overall: {status['overall_progress']*100:.1f}%")
    print("")
    
    if recs['test_complete']:
        print("✓ Test Complete!")
        if ab_test.get('current_results'):
            print(format_comparison_result(ab_test['current_results']))
    else:
        print("Test In Progress:")
        print(f"  Games needed for A: {recs['games_needed_a']}")
        print(f"  Games needed for B: {recs['games_needed_b']}")
        if recs['preliminary_winner']:
            print(f"  Preliminary leader: {recs['preliminary_winner']}")


def cmd_export(args):
    """Export performance data."""
    analyzer = PerformanceAnalyzer(args.log_dir)
    
    config_ids = None
    if args.configs:
        config_ids = args.configs.split(',')
    
    success = analyzer.export_performance_data(args.output, config_ids, args.format)
    
    if success:
        print(f"Performance data exported to {args.output}")
    else:
        print("Export failed. Check logs for details.")


def cmd_summary(args):
    """Show summary of all game data."""
    analyzer = PerformanceAnalyzer(args.log_dir)
    logger = GameLogger(args.log_dir)
    
    # Load basic statistics
    games = logger.load_game_logs()
    summary = analyzer.get_configuration_summary()
    
    print(f"\nGame Log Summary")
    print("=" * 16)
    print(f"Total games logged: {len(games)}")
    print(f"Configurations: {len(summary)}")
    
    if games:
        # Recent activity
        recent_games = games[:5]  # Most recent 5 games
        print(f"\nRecent Games:")
        for i, game in enumerate(recent_games, 1):
            print(f"{i}. {game.config_id} vs {game.opponent_name} "
                  f"({game.opponent_rating}) - {game.outcome}")
        
        # Overall statistics
        total_wins = sum(1 for g in games if g.outcome == 'win')
        total_losses = sum(1 for g in games if g.outcome == 'loss')
        total_draws = sum(1 for g in games if g.outcome == 'draw')
        
        print(f"\nOverall Results:")
        print(f"  Wins: {total_wins} ({total_wins/len(games)*100:.1f}%)")
        print(f"  Losses: {total_losses} ({total_losses/len(games)*100:.1f}%)")
        print(f"  Draws: {total_draws} ({total_draws/len(games)*100:.1f}%)")
    
    # Configuration summary
    if summary:
        print(f"\nConfiguration Performance:")
        for config_id, stats in summary.items():
            print(f"  {config_id}: {stats['total_games']} games, "
                  f"{stats['win_rate']*100:.1f}% win rate")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Chess Engine Analytics CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s summary                           # Show overall summary
  %(prog)s list                             # List all configurations
  %(prog)s metrics                          # Show metrics for all configs
  %(prog)s metrics --config default         # Show metrics for specific config
  %(prog)s compare config1 config2         # Compare two configurations
  %(prog)s ab-test config1 config2 --target 50  # A/B test analysis
  %(prog)s export results.json             # Export all data to JSON
  %(prog)s export results.csv --format csv # Export to CSV
        """
    )
    
    parser.add_argument('--log-dir', default='logs',
                       help='Directory containing log files (default: logs)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Summary command
    subparsers.add_parser('summary', help='Show summary of all game data')
    
    # List configurations command
    subparsers.add_parser('list', help='List all available configurations')
    
    # Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Show performance metrics')
    metrics_parser.add_argument('--config', dest='config_id',
                               help='Show metrics for specific configuration')
    metrics_parser.add_argument('--min-games', type=int, default=1,
                               help='Minimum games required (default: 1)')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two configurations')
    compare_parser.add_argument('config_a', help='First configuration ID')
    compare_parser.add_argument('config_b', help='Second configuration ID')
    compare_parser.add_argument('--min-games', type=int, default=5,
                               help='Minimum games required per config (default: 5)')
    
    # A/B test command
    ab_parser = subparsers.add_parser('ab-test', help='A/B test analysis')
    ab_parser.add_argument('config_a', help='First configuration ID')
    ab_parser.add_argument('config_b', help='Second configuration ID')
    ab_parser.add_argument('--target', dest='target_games', type=int, default=50,
                          help='Target games per configuration (default: 50)')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export performance data')
    export_parser.add_argument('output', help='Output file path')
    export_parser.add_argument('--configs', help='Comma-separated config IDs (default: all)')
    export_parser.add_argument('--format', choices=['json', 'csv'], default='json',
                              help='Export format (default: json)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Verify log directory exists
    log_path = Path(args.log_dir)
    if not log_path.exists():
        print(f"Error: Log directory '{args.log_dir}' does not exist")
        sys.exit(1)
    
    # Execute command
    try:
        if args.command == 'summary':
            cmd_summary(args)
        elif args.command == 'list':
            cmd_list_configs(args)
        elif args.command == 'metrics':
            cmd_show_metrics(args)
        elif args.command == 'compare':
            cmd_compare(args)
        elif args.command == 'ab-test':
            cmd_ab_test(args)
        elif args.command == 'export':
            cmd_export(args)
        else:
            print(f"Unknown command: {args.command}")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()