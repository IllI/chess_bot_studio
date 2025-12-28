"""
A/B testing system for chess engine parameter comparison.
Enables inter-bot challenges and automated testing workflows.
"""

import os
import json
import logging
import threading
import time
import statistics
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from config import ChessConfig
from multi_bot_manager import get_bot_manager, BotInstance, BotInstanceManager
from custom_lichess_bot import LichessBotClient


@dataclass
class TestMatch:
    """Represents a single test match between two bots."""
    match_id: str
    bot1_id: str
    bot2_id: str
    game_id: Optional[str]
    status: str  # 'pending', 'in_progress', 'completed', 'failed'
    result: Optional[str]  # 'bot1_win', 'bot2_win', 'draw'
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    time_control: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class ABTestSuite:
    """Represents a complete A/B test suite between two configurations."""
    suite_id: str
    bot1_id: str
    bot2_id: str
    description: str
    num_games: int
    time_control: Dict[str, Any]
    matches: List[TestMatch]
    status: str  # 'created', 'running', 'completed', 'paused'
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    results_summary: Optional[Dict[str, Any]]


class InterBotChallenger:
    """Manages challenges between bot instances for A/B testing."""
    
    def __init__(self, bot_manager: Optional[BotInstanceManager] = None):
        """
        Initialize the inter-bot challenger.
        
        Args:
            bot_manager: Bot instance manager (uses global if None)
        """
        self.bot_manager = bot_manager or get_bot_manager()
        self.logger = logging.getLogger("InterBotChallenger")
        self.active_challenges = {}  # challenge_id -> challenge_info
        self.challenge_lock = threading.Lock()
    
    def create_challenge(self, 
                        challenger_bot_id: str, 
                        opponent_bot_id: str,
                        time_control: Optional[Dict[str, Any]] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Create a challenge between two bot instances.
        
        Args:
            challenger_bot_id: ID of the challenging bot
            opponent_bot_id: ID of the opponent bot
            time_control: Time control settings for the game
            metadata: Additional metadata for the challenge
            
        Returns:
            Challenge ID if successful, None otherwise
        """
        try:
            # Validate bot instances exist
            challenger_bot = self.bot_manager.get_bot_instance(challenger_bot_id)
            opponent_bot = self.bot_manager.get_bot_instance(opponent_bot_id)
            
            if not challenger_bot or not opponent_bot:
                self.logger.error(f"Bot instances not found: {challenger_bot_id}, {opponent_bot_id}")
                return None
            
            # Check if bots are active
            active_bots = self.bot_manager.get_active_bots()
            if challenger_bot_id not in active_bots or opponent_bot_id not in active_bots:
                self.logger.error(f"Both bots must be active to create challenge")
                return None
            
            # Default time control
            if time_control is None:
                time_control = {
                    'limit': 300,  # 5 minutes
                    'increment': 3  # 3 second increment
                }
            
            # Generate challenge ID
            challenge_id = f"challenge_{challenger_bot_id}_vs_{opponent_bot_id}_{int(time.time())}"
            
            # Create challenge record
            challenge_info = {
                'challenge_id': challenge_id,
                'challenger_bot_id': challenger_bot_id,
                'opponent_bot_id': opponent_bot_id,
                'time_control': time_control,
                'metadata': metadata or {},
                'status': 'created',
                'created_at': datetime.now(),
                'game_id': None,
                'result': None
            }
            
            with self.challenge_lock:
                self.active_challenges[challenge_id] = challenge_info
            
            # Initiate the challenge on Lichess
            success = self._initiate_lichess_challenge(challenge_info)
            
            if success:
                self.logger.info(f"Created challenge: {challenge_id}")
                return challenge_id
            else:
                # Clean up failed challenge
                with self.challenge_lock:
                    if challenge_id in self.active_challenges:
                        del self.active_challenges[challenge_id]
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating challenge: {e}")
            return None
    
    def _initiate_lichess_challenge(self, challenge_info: Dict[str, Any]) -> bool:
        """
        Initiate the actual challenge on Lichess between two bots.
        
        Args:
            challenge_info: Challenge information dictionary
            
        Returns:
            True if challenge initiated successfully, False otherwise
        """
        try:
            challenger_bot_id = challenge_info['challenger_bot_id']
            opponent_bot_id = challenge_info['opponent_bot_id']
            time_control = challenge_info['time_control']
            
            # Get active bot instances
            active_bots = self.bot_manager.get_active_bots()
            challenger_client = self.bot_manager.active_bots.get(challenger_bot_id)
            
            if not challenger_client:
                self.logger.error(f"Challenger bot {challenger_bot_id} not active")
                return False
            
            # Get opponent bot's Lichess username
            opponent_client = self.bot_manager.active_bots.get(opponent_bot_id)
            if not opponent_client:
                self.logger.error(f"Opponent bot {opponent_bot_id} not active")
                return False
            
            # Get opponent's Lichess username
            opponent_account = opponent_client.get_account_info()
            if not opponent_account:
                self.logger.error(f"Could not get account info for opponent bot {opponent_bot_id}")
                return False
            
            opponent_username = opponent_account['username']
            
            # Create challenge using challenger bot
            success = challenger_client.create_challenge(opponent_username, time_control)
            
            if success:
                challenge_info['status'] = 'pending'
                self.logger.info(f"Lichess challenge created: {challenger_bot_id} vs {opponent_username}")
                return True
            else:
                self.logger.error(f"Failed to create Lichess challenge")
                return False
                
        except Exception as e:
            self.logger.error(f"Error initiating Lichess challenge: {e}")
            return False
    
    def get_challenge_status(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a challenge.
        
        Args:
            challenge_id: Challenge identifier
            
        Returns:
            Challenge status information or None if not found
        """
        with self.challenge_lock:
            return self.active_challenges.get(challenge_id)
    
    def list_active_challenges(self) -> List[Dict[str, Any]]:
        """
        List all active challenges.
        
        Returns:
            List of active challenge information
        """
        with self.challenge_lock:
            return list(self.active_challenges.values())
    
    def cancel_challenge(self, challenge_id: str) -> bool:
        """
        Cancel an active challenge.
        
        Args:
            challenge_id: Challenge identifier
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            with self.challenge_lock:
                if challenge_id not in self.active_challenges:
                    self.logger.error(f"Challenge {challenge_id} not found")
                    return False
                
                challenge_info = self.active_challenges[challenge_id]
                challenge_info['status'] = 'cancelled'
                
                # TODO: Cancel the actual Lichess challenge if still pending
                
                del self.active_challenges[challenge_id]
            
            self.logger.info(f"Cancelled challenge: {challenge_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling challenge: {e}")
            return False


class ABTestManager:
    """Manages automated A/B testing workflows between bot configurations."""
    
    def __init__(self, 
                 bot_manager: Optional[BotInstanceManager] = None,
                 results_dir: str = "data/ab_tests"):
        """
        Initialize the A/B test manager.
        
        Args:
            bot_manager: Bot instance manager (uses global if None)
            results_dir: Directory to store test results
        """
        self.bot_manager = bot_manager or get_bot_manager()
        self.challenger = InterBotChallenger(bot_manager)
        self.results_dir = results_dir
        self.active_test_suites = {}  # suite_id -> ABTestSuite
        self.logger = logging.getLogger("ABTestManager")
        
        # Ensure results directory exists
        os.makedirs(results_dir, exist_ok=True)
        
        # Load existing test suites
        self._load_existing_test_suites()
    
    def create_test_suite(self, 
                         bot1_id: str, 
                         bot2_id: str,
                         num_games: int = 10,
                         time_control: Optional[Dict[str, Any]] = None,
                         description: str = "") -> Optional[str]:
        """
        Create a new A/B test suite between two bot configurations.
        
        Args:
            bot1_id: First bot instance ID
            bot2_id: Second bot instance ID
            num_games: Number of games to play in the test
            time_control: Time control for the games
            description: Description of the test suite
            
        Returns:
            Test suite ID if successful, None otherwise
        """
        try:
            # Validate bot instances
            bot1 = self.bot_manager.get_bot_instance(bot1_id)
            bot2 = self.bot_manager.get_bot_instance(bot2_id)
            
            if not bot1 or not bot2:
                self.logger.error(f"Bot instances not found: {bot1_id}, {bot2_id}")
                return None
            
            # Default time control
            if time_control is None:
                time_control = {
                    'limit': 180,  # 3 minutes
                    'increment': 2  # 2 second increment
                }
            
            # Generate suite ID
            suite_id = f"ab_test_{bot1_id}_vs_{bot2_id}_{int(time.time())}"
            
            # Create matches for the test suite
            matches = []
            for i in range(num_games):
                # Alternate colors to ensure fairness
                if i % 2 == 0:
                    challenger_id, opponent_id = bot1_id, bot2_id
                else:
                    challenger_id, opponent_id = bot2_id, bot1_id
                
                match_id = f"{suite_id}_match_{i+1}"
                match = TestMatch(
                    match_id=match_id,
                    bot1_id=bot1_id,
                    bot2_id=bot2_id,
                    game_id=None,
                    status='pending',
                    result=None,
                    started_at=None,
                    completed_at=None,
                    time_control=time_control,
                    metadata={'game_number': i+1, 'challenger': challenger_id}
                )
                matches.append(match)
            
            # Create test suite
            test_suite = ABTestSuite(
                suite_id=suite_id,
                bot1_id=bot1_id,
                bot2_id=bot2_id,
                description=description,
                num_games=num_games,
                time_control=time_control,
                matches=matches,
                status='created',
                created_at=datetime.now(),
                started_at=None,
                completed_at=None,
                results_summary=None
            )
            
            self.active_test_suites[suite_id] = test_suite
            
            # Save test suite to disk
            self._save_test_suite(test_suite)
            
            self.logger.info(f"Created A/B test suite: {suite_id}")
            return suite_id
            
        except Exception as e:
            self.logger.error(f"Error creating test suite: {e}")
            return None
    
    def start_test_suite(self, suite_id: str) -> bool:
        """
        Start executing an A/B test suite.
        
        Args:
            suite_id: Test suite identifier
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            if suite_id not in self.active_test_suites:
                self.logger.error(f"Test suite {suite_id} not found")
                return False
            
            test_suite = self.active_test_suites[suite_id]
            
            if test_suite.status != 'created':
                self.logger.error(f"Test suite {suite_id} is not in created state")
                return False
            
            # Check if both bots are active
            active_bots = self.bot_manager.get_active_bots()
            if test_suite.bot1_id not in active_bots or test_suite.bot2_id not in active_bots:
                self.logger.error(f"Both bots must be active to start test suite")
                return False
            
            # Update test suite status
            test_suite.status = 'running'
            test_suite.started_at = datetime.now()
            
            # Start test execution in separate thread
            test_thread = threading.Thread(
                target=self._execute_test_suite,
                args=(suite_id,),
                daemon=True
            )
            test_thread.start()
            
            self.logger.info(f"Started A/B test suite: {suite_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting test suite: {e}")
            return False
    
    def _execute_test_suite(self, suite_id: str) -> None:
        """
        Execute all matches in a test suite.
        
        Args:
            suite_id: Test suite identifier
        """
        try:
            test_suite = self.active_test_suites[suite_id]
            
            self.logger.info(f"Executing test suite {suite_id} with {len(test_suite.matches)} matches")
            
            for match in test_suite.matches:
                if test_suite.status != 'running':
                    self.logger.info(f"Test suite {suite_id} stopped")
                    break
                
                # Execute individual match
                self._execute_match(test_suite, match)
                
                # Wait between matches to avoid overwhelming Lichess
                time.sleep(30)  # 30 second delay between matches
            
            # Calculate final results
            if test_suite.status == 'running':
                test_suite.status = 'completed'
                test_suite.completed_at = datetime.now()
                test_suite.results_summary = self._calculate_test_results(test_suite)
                
                # Save updated test suite
                self._save_test_suite(test_suite)
                
                self.logger.info(f"Completed A/B test suite: {suite_id}")
                self._log_test_results(test_suite)
            
        except Exception as e:
            self.logger.error(f"Error executing test suite {suite_id}: {e}")
            if suite_id in self.active_test_suites:
                self.active_test_suites[suite_id].status = 'failed'
    
    def _execute_match(self, test_suite: ABTestSuite, match: TestMatch) -> None:
        """
        Execute a single match within a test suite.
        
        Args:
            test_suite: Parent test suite
            match: Match to execute
        """
        try:
            self.logger.info(f"Starting match {match.match_id}")
            
            # Determine challenger and opponent based on metadata
            challenger_id = match.metadata.get('challenger', match.bot1_id)
            opponent_id = match.bot2_id if challenger_id == match.bot1_id else match.bot1_id
            
            # Create challenge
            challenge_id = self.challenger.create_challenge(
                challenger_bot_id=challenger_id,
                opponent_bot_id=opponent_id,
                time_control=match.time_control,
                metadata={'test_suite_id': test_suite.suite_id, 'match_id': match.match_id}
            )
            
            if not challenge_id:
                self.logger.error(f"Failed to create challenge for match {match.match_id}")
                match.status = 'failed'
                return
            
            match.status = 'in_progress'
            match.started_at = datetime.now()
            
            # Wait for match completion (simplified - in practice would monitor game events)
            self._wait_for_match_completion(match, challenge_id)
            
        except Exception as e:
            self.logger.error(f"Error executing match {match.match_id}: {e}")
            match.status = 'failed'
    
    def _wait_for_match_completion(self, match: TestMatch, challenge_id: str, timeout: int = 1800) -> None:
        """
        Wait for a match to complete.
        
        Args:
            match: Match to monitor
            challenge_id: Associated challenge ID
            timeout: Maximum wait time in seconds
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check challenge status
            challenge_status = self.challenger.get_challenge_status(challenge_id)
            
            if challenge_status and challenge_status.get('status') == 'completed':
                match.status = 'completed'
                match.completed_at = datetime.now()
                match.result = challenge_status.get('result', 'draw')
                match.game_id = challenge_status.get('game_id')
                self.logger.info(f"Match {match.match_id} completed: {match.result}")
                return
            
            # Wait before checking again
            time.sleep(10)
        
        # Timeout reached
        self.logger.warning(f"Match {match.match_id} timed out")
        match.status = 'timeout'
        match.completed_at = datetime.now()
    
    def _calculate_test_results(self, test_suite: ABTestSuite) -> Dict[str, Any]:
        """
        Calculate comprehensive results for a completed test suite.
        
        Args:
            test_suite: Completed test suite
            
        Returns:
            Results summary dictionary
        """
        try:
            completed_matches = [m for m in test_suite.matches if m.status == 'completed']
            
            if not completed_matches:
                return {'error': 'No completed matches'}
            
            # Count results
            bot1_wins = sum(1 for m in completed_matches if m.result == 'bot1_win')
            bot2_wins = sum(1 for m in completed_matches if m.result == 'bot2_win')
            draws = sum(1 for m in completed_matches if m.result == 'draw')
            
            total_games = len(completed_matches)
            
            # Calculate statistics
            bot1_score = bot1_wins + (draws * 0.5)
            bot2_score = bot2_wins + (draws * 0.5)
            
            bot1_win_rate = bot1_score / total_games if total_games > 0 else 0
            bot2_win_rate = bot2_score / total_games if total_games > 0 else 0
            
            # Calculate confidence intervals (simplified)
            confidence_interval = self._calculate_confidence_interval(bot1_score, total_games)
            
            # Performance comparison
            performance_diff = bot1_win_rate - bot2_win_rate
            
            results = {
                'total_games': total_games,
                'bot1_wins': bot1_wins,
                'bot2_wins': bot2_wins,
                'draws': draws,
                'bot1_score': bot1_score,
                'bot2_score': bot2_score,
                'bot1_win_rate': bot1_win_rate,
                'bot2_win_rate': bot2_win_rate,
                'performance_difference': performance_diff,
                'confidence_interval': confidence_interval,
                'statistical_significance': abs(performance_diff) > confidence_interval,
                'winner': self._determine_winner(bot1_win_rate, bot2_win_rate, confidence_interval),
                'completed_at': datetime.now().isoformat()
            }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error calculating test results: {e}")
            return {'error': str(e)}
    
    def _calculate_confidence_interval(self, score: float, total_games: int, confidence: float = 0.95) -> float:
        """
        Calculate confidence interval for win rate.
        
        Args:
            score: Total score (wins + 0.5 * draws)
            total_games: Total number of games
            confidence: Confidence level (default 95%)
            
        Returns:
            Confidence interval half-width
        """
        if total_games == 0:
            return 0.0
        
        # Simplified confidence interval calculation
        # In practice, would use proper statistical methods
        win_rate = score / total_games
        variance = win_rate * (1 - win_rate) / total_games
        
        # Approximate 95% confidence interval
        z_score = 1.96  # For 95% confidence
        margin_of_error = z_score * (variance ** 0.5)
        
        return margin_of_error
    
    def _determine_winner(self, bot1_rate: float, bot2_rate: float, confidence_interval: float) -> str:
        """
        Determine the winner based on win rates and statistical significance.
        
        Args:
            bot1_rate: Bot 1 win rate
            bot2_rate: Bot 2 win rate
            confidence_interval: Confidence interval
            
        Returns:
            Winner determination string
        """
        diff = abs(bot1_rate - bot2_rate)
        
        if diff < confidence_interval:
            return "inconclusive"
        elif bot1_rate > bot2_rate:
            return "bot1"
        else:
            return "bot2"
    
    def get_test_suite_status(self, suite_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a test suite.
        
        Args:
            suite_id: Test suite identifier
            
        Returns:
            Test suite status information or None if not found
        """
        if suite_id not in self.active_test_suites:
            return None
        
        test_suite = self.active_test_suites[suite_id]
        
        # Calculate progress
        completed_matches = sum(1 for m in test_suite.matches if m.status in ['completed', 'failed'])
        progress = completed_matches / len(test_suite.matches) if test_suite.matches else 0
        
        return {
            'suite_id': suite_id,
            'status': test_suite.status,
            'progress': progress,
            'completed_matches': completed_matches,
            'total_matches': len(test_suite.matches),
            'bot1_id': test_suite.bot1_id,
            'bot2_id': test_suite.bot2_id,
            'description': test_suite.description,
            'created_at': test_suite.created_at.isoformat(),
            'results_summary': test_suite.results_summary
        }
    
    def list_test_suites(self) -> List[Dict[str, Any]]:
        """
        List all test suites.
        
        Returns:
            List of test suite summaries
        """
        suites = []
        for suite_id, test_suite in self.active_test_suites.items():
            status_info = self.get_test_suite_status(suite_id)
            if status_info:
                suites.append(status_info)
        return suites
    
    def stop_test_suite(self, suite_id: str) -> bool:
        """
        Stop a running test suite.
        
        Args:
            suite_id: Test suite identifier
            
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            if suite_id not in self.active_test_suites:
                self.logger.error(f"Test suite {suite_id} not found")
                return False
            
            test_suite = self.active_test_suites[suite_id]
            
            if test_suite.status != 'running':
                self.logger.warning(f"Test suite {suite_id} is not running")
                return True
            
            test_suite.status = 'paused'
            self.logger.info(f"Stopped test suite: {suite_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping test suite: {e}")
            return False
    
    def _save_test_suite(self, test_suite: ABTestSuite) -> None:
        """
        Save test suite to disk.
        
        Args:
            test_suite: Test suite to save
        """
        try:
            filepath = os.path.join(self.results_dir, f"{test_suite.suite_id}.json")
            
            # Convert to serializable format
            data = asdict(test_suite)
            
            # Convert datetime objects to ISO format
            for key in ['created_at', 'started_at', 'completed_at']:
                if data[key]:
                    data[key] = data[key].isoformat()
            
            # Convert match datetime objects
            for match_data in data['matches']:
                for key in ['started_at', 'completed_at']:
                    if match_data[key]:
                        match_data[key] = match_data[key].isoformat()
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving test suite: {e}")
    
    def _load_existing_test_suites(self) -> None:
        """Load existing test suites from disk."""
        try:
            if not os.path.exists(self.results_dir):
                return
            
            for filename in os.listdir(self.results_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.results_dir, filename)
                    
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                        
                        # Convert datetime strings back to datetime objects
                        for key in ['created_at', 'started_at', 'completed_at']:
                            if data[key]:
                                data[key] = datetime.fromisoformat(data[key])
                        
                        # Convert match datetime objects
                        matches = []
                        for match_data in data['matches']:
                            for key in ['started_at', 'completed_at']:
                                if match_data[key]:
                                    match_data[key] = datetime.fromisoformat(match_data[key])
                            matches.append(TestMatch(**match_data))
                        
                        data['matches'] = matches
                        test_suite = ABTestSuite(**data)
                        
                        self.active_test_suites[test_suite.suite_id] = test_suite
                        self.logger.info(f"Loaded test suite: {test_suite.suite_id}")
                        
                    except Exception as e:
                        self.logger.error(f"Error loading test suite from {filename}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error loading existing test suites: {e}")
    
    def _log_test_results(self, test_suite: ABTestSuite) -> None:
        """
        Log comprehensive test results.
        
        Args:
            test_suite: Completed test suite
        """
        if not test_suite.results_summary:
            return
        
        results = test_suite.results_summary
        
        self.logger.info(f"=== A/B Test Results: {test_suite.suite_id} ===")
        self.logger.info(f"Bot 1 ({test_suite.bot1_id}): {results['bot1_wins']} wins, "
                        f"{results['bot1_score']:.1f} points ({results['bot1_win_rate']:.1%})")
        self.logger.info(f"Bot 2 ({test_suite.bot2_id}): {results['bot2_wins']} wins, "
                        f"{results['bot2_score']:.1f} points ({results['bot2_win_rate']:.1%})")
        self.logger.info(f"Draws: {results['draws']}")
        self.logger.info(f"Performance difference: {results['performance_difference']:.1%}")
        self.logger.info(f"Statistical significance: {results['statistical_significance']}")
        self.logger.info(f"Winner: {results['winner']}")


# Global A/B test manager
_global_ab_manager = None

def get_ab_test_manager() -> ABTestManager:
    """Get the global A/B test manager."""
    global _global_ab_manager
    if _global_ab_manager is None:
        _global_ab_manager = ABTestManager()
    return _global_ab_manager


if __name__ == "__main__":
    # Test the A/B testing system
    from .multi_bot_manager import BotInstanceManager
    
    # Create test bot manager
    bot_manager = BotInstanceManager("test_configs")
    
    # Create test configurations
    config1 = {
        'piece_values': {'pawn': 100, 'knight': 320, 'bishop': 330, 'rook': 500, 'queen': 900, 'king': 0},
        'mobility_weight': 10.0,
        'search_depth': 4
    }
    
    config2 = {
        'piece_values': {'pawn': 110, 'knight': 330, 'bishop': 340, 'rook': 510, 'queen': 910, 'king': 0},
        'mobility_weight': 12.0,
        'search_depth': 4
    }
    
    # Create bot instances
    bot_manager.create_bot_instance("standard-bot", config1, "Standard configuration")
    bot_manager.create_bot_instance("aggressive-bot", config2, "Aggressive configuration")
    
    # Create A/B test manager
    ab_manager = ABTestManager(bot_manager, "test_ab_results")
    
    # Create test suite
    suite_id = ab_manager.create_test_suite(
        bot1_id="standard-bot",
        bot2_id="aggressive-bot",
        num_games=6,
        description="Standard vs Aggressive configuration test"
    )
    
    if suite_id:
        print(f"Created test suite: {suite_id}")
        
        # Get test suite status
        status = ab_manager.get_test_suite_status(suite_id)
        print(f"Test suite status: {status}")
        
        print("A/B testing system test completed successfully!")
    else:
        print("Failed to create test suite")