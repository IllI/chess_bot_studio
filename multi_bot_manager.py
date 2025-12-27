"""
Multi-bot configuration management for A/B testing.
Handles isolated configuration spaces for concurrent bot instances.
"""

import os
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from copy import deepcopy
from .config import ChessConfig, DEFAULT_CONFIG
from .custom_lichess_bot import LichessBotClient


class BotInstanceManager:
    """Manages multiple bot instances with isolated configurations."""
    
    def __init__(self, base_config_dir: str = "configs/bots"):
        """
        Initialize the multi-bot manager.
        
        Args:
            base_config_dir: Base directory for bot configurations
        """
        self.base_config_dir = base_config_dir
        self.bot_instances = {}  # bot_id -> BotInstance
        self.active_bots = {}   # bot_id -> LichessBotClient
        self.config_lock = threading.Lock()
        self.logger = logging.getLogger("BotInstanceManager")
        
        # Ensure config directory exists
        os.makedirs(base_config_dir, exist_ok=True)
        
        # Load existing bot configurations
        self._load_existing_configurations()
    
    def create_bot_instance(self, 
                          bot_id: str, 
                          config: Optional[Dict[str, Any]] = None,
                          description: str = "") -> bool:
        """
        Create a new bot instance with isolated configuration.
        
        Args:
            bot_id: Unique identifier for the bot instance
            config: Initial configuration (uses default if None)
            description: Human-readable description of the bot
            
        Returns:
            True if bot instance created successfully, False otherwise
        """
        try:
            with self.config_lock:
                if bot_id in self.bot_instances:
                    self.logger.error(f"Bot instance {bot_id} already exists")
                    return False
                
                # Validate bot_id format
                if not self._validate_bot_id(bot_id):
                    self.logger.error(f"Invalid bot_id format: {bot_id}")
                    return False
                
                # Create bot configuration
                bot_config = ChessConfig(config_id=bot_id)
                if config:
                    # Validate and apply custom configuration
                    for param_name, param_value in config.items():
                        if not bot_config.update_parameter(param_name, param_value):
                            self.logger.error(f"Failed to set parameter {param_name} for bot {bot_id}")
                            return False
                
                # Create bot instance record
                bot_instance = BotInstance(
                    bot_id=bot_id,
                    config=bot_config,
                    description=description,
                    created_at=datetime.now()
                )
                
                # Save configuration to file
                config_file = self._get_config_file_path(bot_id)
                if not bot_instance.save_to_file(config_file):
                    self.logger.error(f"Failed to save configuration for bot {bot_id}")
                    return False
                
                self.bot_instances[bot_id] = bot_instance
                self.logger.info(f"Created bot instance: {bot_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error creating bot instance {bot_id}: {e}")
            return False
    
    def get_bot_instance(self, bot_id: str) -> Optional['BotInstance']:
        """
        Get a bot instance by ID.
        
        Args:
            bot_id: Bot instance identifier
            
        Returns:
            BotInstance object or None if not found
        """
        return self.bot_instances.get(bot_id)
    
    def list_bot_instances(self) -> List[Dict[str, Any]]:
        """
        List all bot instances with their basic information.
        
        Returns:
            List of bot instance summaries
        """
        instances = []
        for bot_id, instance in self.bot_instances.items():
            instances.append({
                'bot_id': bot_id,
                'description': instance.description,
                'created_at': instance.created_at.isoformat(),
                'is_active': bot_id in self.active_bots,
                'config_summary': instance.get_config_summary()
            })
        return instances
    
    def update_bot_configuration(self, 
                               bot_id: str, 
                               parameter_updates: Dict[str, Any]) -> bool:
        """
        Update configuration parameters for a specific bot instance.
        
        Args:
            bot_id: Bot instance identifier
            parameter_updates: Dictionary of parameter updates
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            with self.config_lock:
                if bot_id not in self.bot_instances:
                    self.logger.error(f"Bot instance {bot_id} not found")
                    return False
                
                bot_instance = self.bot_instances[bot_id]
                
                # Apply parameter updates
                for param_name, param_value in parameter_updates.items():
                    if not bot_instance.config.update_parameter(param_name, param_value):
                        self.logger.error(f"Failed to update parameter {param_name} for bot {bot_id}")
                        return False
                
                # Save updated configuration
                config_file = self._get_config_file_path(bot_id)
                if not bot_instance.save_to_file(config_file):
                    self.logger.error(f"Failed to save updated configuration for bot {bot_id}")
                    return False
                
                self.logger.info(f"Updated configuration for bot {bot_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating bot configuration {bot_id}: {e}")
            return False
    
    def delete_bot_instance(self, bot_id: str) -> bool:
        """
        Delete a bot instance and its configuration.
        
        Args:
            bot_id: Bot instance identifier
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            with self.config_lock:
                if bot_id not in self.bot_instances:
                    self.logger.error(f"Bot instance {bot_id} not found")
                    return False
                
                # Stop bot if it's active
                if bot_id in self.active_bots:
                    self.stop_bot(bot_id)
                
                # Remove configuration file
                config_file = self._get_config_file_path(bot_id)
                if os.path.exists(config_file):
                    os.remove(config_file)
                
                # Remove from memory
                del self.bot_instances[bot_id]
                
                self.logger.info(f"Deleted bot instance: {bot_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error deleting bot instance {bot_id}: {e}")
            return False
    
    def start_bot(self, bot_id: str, lichess_token: str) -> bool:
        """
        Start a bot instance with Lichess connection.
        
        Args:
            bot_id: Bot instance identifier
            lichess_token: Lichess API token for this bot
            
        Returns:
            True if bot started successfully, False otherwise
        """
        try:
            if bot_id not in self.bot_instances:
                self.logger.error(f"Bot instance {bot_id} not found")
                return False
            
            if bot_id in self.active_bots:
                self.logger.warning(f"Bot {bot_id} is already active")
                return True
            
            bot_instance = self.bot_instances[bot_id]
            
            # Create Lichess bot client with isolated configuration
            lichess_bot = LichessBotClient(
                token=lichess_token,
                enable_logging=True
            )
            
            # Set bot-specific configuration
            lichess_bot.bot_id = bot_id
            lichess_bot.config = bot_instance.config
            
            # Connect to Lichess
            if not lichess_bot.connect():
                self.logger.error(f"Failed to connect bot {bot_id} to Lichess")
                return False
            
            # Store active bot
            self.active_bots[bot_id] = lichess_bot
            
            # Start bot in separate thread
            bot_thread = threading.Thread(
                target=self._run_bot_main_loop,
                args=(bot_id, lichess_bot),
                daemon=False
            )
            bot_thread.start()
            
            self.logger.info(f"Started bot instance: {bot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting bot {bot_id}: {e}")
            return False
    
    def stop_bot(self, bot_id: str) -> bool:
        """
        Stop an active bot instance.
        
        Args:
            bot_id: Bot instance identifier
            
        Returns:
            True if bot stopped successfully, False otherwise
        """
        try:
            if bot_id not in self.active_bots:
                self.logger.warning(f"Bot {bot_id} is not active")
                return True
            
            lichess_bot = self.active_bots[bot_id]
            lichess_bot.disconnect()
            
            del self.active_bots[bot_id]
            
            self.logger.info(f"Stopped bot instance: {bot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping bot {bot_id}: {e}")
            return False
    
    def get_active_bots(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently active bots.
        
        Returns:
            Dictionary of active bot information
        """
        active_info = {}
        for bot_id, lichess_bot in self.active_bots.items():
            bot_instance = self.bot_instances.get(bot_id)
            active_info[bot_id] = {
                'bot_id': bot_id,
                'description': bot_instance.description if bot_instance else "",
                'connected': lichess_bot.is_connected(),
                'active_games': len(lichess_bot.get_active_games()),
                'connection_status': lichess_bot.get_connection_status()
            }
        return active_info
    
    def prevent_configuration_conflicts(self) -> List[str]:
        """
        Check for and report potential configuration conflicts between bot instances.
        
        Returns:
            List of conflict warnings
        """
        conflicts = []
        
        try:
            bot_configs = {}
            for bot_id, instance in self.bot_instances.items():
                config_hash = self._get_config_hash(instance.config.get_current_config())
                if config_hash in bot_configs:
                    conflicts.append(
                        f"Identical configurations detected: {bot_id} and {bot_configs[config_hash]}"
                    )
                else:
                    bot_configs[config_hash] = bot_id
            
            # Check for similar configurations (within threshold)
            similar_configs = self._find_similar_configurations()
            for similarity_info in similar_configs:
                conflicts.append(
                    f"Similar configurations detected: {similarity_info['bot1']} and "
                    f"{similarity_info['bot2']} (similarity: {similarity_info['similarity']:.2f})"
                )
            
        except Exception as e:
            self.logger.error(f"Error checking configuration conflicts: {e}")
            conflicts.append(f"Error checking conflicts: {e}")
        
        return conflicts
    
    def _validate_bot_id(self, bot_id: str) -> bool:
        """
        Validate bot ID format.
        
        Args:
            bot_id: Bot identifier to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Bot ID should be alphanumeric with hyphens/underscores, 3-50 characters
        import re
        pattern = r'^[a-zA-Z0-9_-]{3,50}$'
        return bool(re.match(pattern, bot_id))
    
    def _get_config_file_path(self, bot_id: str) -> str:
        """Get the configuration file path for a bot instance."""
        return os.path.join(self.base_config_dir, f"{bot_id}.json")
    
    def _load_existing_configurations(self) -> None:
        """Load existing bot configurations from disk."""
        try:
            if not os.path.exists(self.base_config_dir):
                return
            
            for filename in os.listdir(self.base_config_dir):
                if filename.endswith('.json'):
                    bot_id = filename[:-5]  # Remove .json extension
                    config_file = os.path.join(self.base_config_dir, filename)
                    
                    try:
                        bot_instance = BotInstance.load_from_file(config_file)
                        if bot_instance:
                            self.bot_instances[bot_id] = bot_instance
                            self.logger.info(f"Loaded bot instance: {bot_id}")
                    except Exception as e:
                        self.logger.error(f"Error loading bot instance {bot_id}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error loading existing configurations: {e}")
    
    def _run_bot_main_loop(self, bot_id: str, lichess_bot: LichessBotClient) -> None:
        """
        Run the main loop for a bot instance.
        
        Args:
            bot_id: Bot instance identifier
            lichess_bot: Lichess bot client
        """
        try:
            self.logger.info(f"Starting main loop for bot {bot_id}")
            lichess_bot.main_loop()
        except Exception as e:
            self.logger.error(f"Error in main loop for bot {bot_id}: {e}")
        finally:
            # Clean up on exit
            if bot_id in self.active_bots:
                del self.active_bots[bot_id]
            self.logger.info(f"Main loop ended for bot {bot_id}")
    
    def _get_config_hash(self, config: Dict[str, Any]) -> str:
        """
        Generate a hash for a configuration to detect duplicates.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configuration hash string
        """
        import hashlib
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def _find_similar_configurations(self, similarity_threshold: float = 0.9) -> List[Dict[str, Any]]:
        """
        Find configurations that are very similar (potential duplicates).
        
        Args:
            similarity_threshold: Threshold for considering configurations similar
            
        Returns:
            List of similar configuration pairs
        """
        similar_pairs = []
        
        try:
            bot_ids = list(self.bot_instances.keys())
            
            for i in range(len(bot_ids)):
                for j in range(i + 1, len(bot_ids)):
                    bot1_id = bot_ids[i]
                    bot2_id = bot_ids[j]
                    
                    config1 = self.bot_instances[bot1_id].config.get_current_config()
                    config2 = self.bot_instances[bot2_id].config.get_current_config()
                    
                    similarity = self._calculate_config_similarity(config1, config2)
                    
                    if similarity >= similarity_threshold:
                        similar_pairs.append({
                            'bot1': bot1_id,
                            'bot2': bot2_id,
                            'similarity': similarity
                        })
        
        except Exception as e:
            self.logger.error(f"Error finding similar configurations: {e}")
        
        return similar_pairs
    
    def _calculate_config_similarity(self, config1: Dict[str, Any], config2: Dict[str, Any]) -> float:
        """
        Calculate similarity between two configurations.
        
        Args:
            config1: First configuration
            config2: Second configuration
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # Simple similarity calculation based on parameter differences
            total_params = 0
            matching_params = 0
            
            # Compare piece values
            if 'piece_values' in config1 and 'piece_values' in config2:
                for piece in config1['piece_values']:
                    total_params += 1
                    if config1['piece_values'][piece] == config2['piece_values'][piece]:
                        matching_params += 1
            
            # Compare other parameters
            for param in ['mobility_weight', 'search_depth']:
                if param in config1 and param in config2:
                    total_params += 1
                    if config1[param] == config2[param]:
                        matching_params += 1
            
            # Compare nested parameters
            for nested_param in ['pawn_structure_bonus', 'king_safety_penalty']:
                if nested_param in config1 and nested_param in config2:
                    for key in config1[nested_param]:
                        total_params += 1
                        if config1[nested_param][key] == config2[nested_param][key]:
                            matching_params += 1
            
            return matching_params / total_params if total_params > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating config similarity: {e}")
            return 0.0


class BotInstance:
    """Represents a single bot instance with its configuration and metadata."""
    
    def __init__(self, 
                 bot_id: str, 
                 config: ChessConfig, 
                 description: str = "",
                 created_at: Optional[datetime] = None):
        """
        Initialize a bot instance.
        
        Args:
            bot_id: Unique identifier for the bot
            config: Chess configuration for this bot
            description: Human-readable description
            created_at: Creation timestamp
        """
        self.bot_id = bot_id
        self.config = config
        self.description = description
        self.created_at = created_at or datetime.now()
        self.last_modified = datetime.now()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the bot's configuration.
        
        Returns:
            Configuration summary dictionary
        """
        config = self.config.get_current_config()
        return {
            'piece_values_sum': sum(config['piece_values'].values()),
            'mobility_weight': config['mobility_weight'],
            'search_depth': config['search_depth'],
            'pawn_bonus_sum': sum(config['pawn_structure_bonus'].values()),
            'king_penalty_sum': sum(config['king_safety_penalty'].values())
        }
    
    def save_to_file(self, filepath: str) -> bool:
        """
        Save bot instance to a JSON file.
        
        Args:
            filepath: Path to save the configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = {
                'bot_id': self.bot_id,
                'description': self.description,
                'created_at': self.created_at.isoformat(),
                'last_modified': self.last_modified.isoformat(),
                'config': self.config.get_current_config(),
                'change_history': self.config.get_change_history()
            }
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            logging.getLogger("BotInstance").error(f"Error saving bot instance: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, filepath: str) -> Optional['BotInstance']:
        """
        Load bot instance from a JSON file.
        
        Args:
            filepath: Path to load the configuration from
            
        Returns:
            BotInstance object or None if loading failed
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Create configuration
            config = ChessConfig(config_id=data['bot_id'])
            
            # Load configuration parameters
            for param_name, param_value in data['config'].items():
                config.update_parameter(param_name, param_value)
            
            # Restore change history if available
            if 'change_history' in data:
                config.change_history = data['change_history']
            
            # Create bot instance
            instance = cls(
                bot_id=data['bot_id'],
                config=config,
                description=data.get('description', ''),
                created_at=datetime.fromisoformat(data['created_at'])
            )
            
            if 'last_modified' in data:
                instance.last_modified = datetime.fromisoformat(data['last_modified'])
            
            return instance
            
        except Exception as e:
            logging.getLogger("BotInstance").error(f"Error loading bot instance: {e}")
            return None


# Global instance manager
_global_manager = None

def get_bot_manager() -> BotInstanceManager:
    """Get the global bot instance manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = BotInstanceManager()
    return _global_manager


if __name__ == "__main__":
    # Test the multi-bot manager
    manager = BotInstanceManager("test_configs")
    
    # Create test bot instances
    test_config1 = {
        'piece_values': {'pawn': 110, 'knight': 330, 'bishop': 340, 'rook': 510, 'queen': 910, 'king': 0},
        'mobility_weight': 12.0,
        'search_depth': 5
    }
    
    test_config2 = {
        'piece_values': {'pawn': 90, 'knight': 310, 'bishop': 320, 'rook': 490, 'queen': 890, 'king': 0},
        'mobility_weight': 8.0,
        'search_depth': 3
    }
    
    # Create bot instances
    manager.create_bot_instance("aggressive-bot", test_config1, "Aggressive playing style")
    manager.create_bot_instance("defensive-bot", test_config2, "Defensive playing style")
    
    # List instances
    instances = manager.list_bot_instances()
    print("Bot instances:")
    for instance in instances:
        print(f"  {instance['bot_id']}: {instance['description']}")
    
    # Check for conflicts
    conflicts = manager.prevent_configuration_conflicts()
    if conflicts:
        print("Configuration conflicts:")
        for conflict in conflicts:
            print(f"  {conflict}")
    else:
        print("No configuration conflicts detected")
    
    print("Multi-bot manager test completed successfully!")