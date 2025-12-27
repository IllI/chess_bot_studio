"""
Configuration module for chess engine tuning parameters.
"""

import json
import os
import logging
from typing import Dict, Any, Optional, Tuple
from copy import deepcopy
from datetime import datetime

# Default configuration values
DEFAULT_CONFIG = {
    'piece_values': {
        'pawn': 100,
        'knight': 320,
        'bishop': 330,
        'rook': 500,
        'queen': 900,
        'king': 0
    },
    'mobility_weight': 10.0,
    'pawn_structure_bonus': {
        'passed_pawn': 50,
        'doubled_pawn': -20,
        'isolated_pawn': -15,
        'backward_pawn': -10,
        'connected_pawns': 5,
    },
    'king_safety_penalty': {
        'open_file_near_king': -30,
        'weak_pawn_shield': -20,
        'king_in_center': -40,
        'enemy_pieces_near_king': -15,
    },
    'search_depth': 4
}

# Configuration bounds for parameter validation
PARAMETER_BOUNDS = {
    'piece_values': {
        'pawn': (50, 200),
        'knight': (200, 500),
        'bishop': (200, 500),
        'rook': (300, 800),
        'queen': (600, 1200),
        'king': (0, 0)
    },
    'mobility_weight': (0.0, 50.0),
    'pawn_structure_bonus': {
        'passed_pawn': (0, 100),
        'doubled_pawn': (-50, 0),
        'isolated_pawn': (-50, 0),
        'backward_pawn': (-50, 0),
        'connected_pawns': (0, 20)
    },
    'king_safety_penalty': {
        'open_file_near_king': (-100, 0),
        'weak_pawn_shield': (-100, 0),
        'king_in_center': (-100, 0),
        'enemy_pieces_near_king': (-50, 0)
    },
    'search_depth': (1, 8)
}


class ChessConfig:
    """Configuration management system for chess engine parameters."""
    
    def __init__(self, config_id: Optional[str] = None):
        """Initialize configuration with optional identifier."""
        self.config_id = config_id or "default"
        self.config = deepcopy(DEFAULT_CONFIG)
        self.change_history = []
        self.logger = logging.getLogger(f"ChessConfig.{self.config_id}")        

    def validate_parameter(self, param_name: str, param_value: Any) -> Tuple[bool, str]:
        """Validate a parameter value against defined bounds."""
        if param_name not in PARAMETER_BOUNDS:
            return False, f"Unknown parameter: {param_name}"
            
        if param_name == 'piece_values':
            if not isinstance(param_value, dict):
                return False, "piece_values must be a dictionary"
            for piece, value in param_value.items():
                if piece not in PARAMETER_BOUNDS['piece_values']:
                    return False, f"Unknown piece type: {piece}"
                if not isinstance(value, (int, float)):
                    return False, f"Piece value for {piece} must be numeric"
                min_val, max_val = PARAMETER_BOUNDS['piece_values'][piece]
                if not (min_val <= value <= max_val):
                    return False, f"Piece value for {piece} must be between {min_val} and {max_val}"
            return True, ""
        
        elif param_name == 'mobility_weight':
            if not isinstance(param_value, (int, float)):
                return False, "mobility_weight must be numeric"
            min_val, max_val = PARAMETER_BOUNDS['mobility_weight']
            if not (min_val <= param_value <= max_val):
                return False, f"mobility_weight must be between {min_val} and {max_val}"
            return True, ""
        
        elif param_name in ['pawn_structure_bonus', 'king_safety_penalty']:
            if not isinstance(param_value, dict):
                return False, f"{param_name} must be a dictionary"
            bounds_dict = PARAMETER_BOUNDS[param_name]
            for key, value in param_value.items():
                if key not in bounds_dict:
                    return False, f"Unknown {param_name} key: {key}"
                if not isinstance(value, (int, float)):
                    return False, f"Value for {key} must be numeric"
                min_val, max_val = bounds_dict[key]
                if not (min_val <= value <= max_val):
                    return False, f"Value for {key} must be between {min_val} and {max_val}"
            return True, ""
        
        elif param_name == 'search_depth':
            if not isinstance(param_value, int):
                return False, "search_depth must be an integer"
            min_val, max_val = PARAMETER_BOUNDS['search_depth']
            if not (min_val <= param_value <= max_val):
                return False, f"search_depth must be between {min_val} and {max_val}"
            return True, ""
        
        return False, f"Validation not implemented for parameter: {param_name}"   
 
    def update_parameter(self, param_name: str, new_value: Any) -> bool:
        """Update a configuration parameter with validation and logging."""
        is_valid, error_msg = self.validate_parameter(param_name, new_value)
        if not is_valid:
            self.logger.error(f"Parameter update failed: {error_msg}")
            return False
        
        old_value = self.config.get(param_name)
        self.config[param_name] = deepcopy(new_value)
        
        # Log the change
        change_record = {
            'timestamp': datetime.now().isoformat(),
            'parameter': param_name,
            'old_value': old_value,
            'new_value': new_value,
            'config_id': self.config_id
        }
        self.change_history.append(change_record)
        self.logger.info(f"Parameter updated: {param_name} = {new_value}")
        
        return True
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get the current configuration as a dictionary."""
        return deepcopy(self.config)
    
    def get_parameter(self, param_name: str) -> Any:
        """Get a specific parameter value."""
        return deepcopy(self.config.get(param_name))
    
    def export_config(self, filepath: str, include_metadata: bool = True) -> bool:
        """Export current configuration to a JSON file with optional metadata."""
        try:
            export_data = {
                'config': self.config,
                'config_id': self.config_id,
                'exported_at': datetime.now().isoformat()
            }
            
            if include_metadata:
                export_data['change_history'] = self.change_history
                export_data['parameter_bounds'] = PARAMETER_BOUNDS
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info(f"Configuration exported to {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Error exporting configuration: {e}")
            return False 
   
    def import_config(self, filepath: str) -> bool:
        """Import configuration from a JSON file with validation."""
        try:
            if not os.path.exists(filepath):
                self.logger.error(f"Configuration file not found: {filepath}")
                return False
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Handle both old format (direct config) and new format (with metadata)
            if 'config' in data:
                config_to_import = data['config']
                if 'change_history' in data:
                    self.change_history.extend(data['change_history'])
            else:
                config_to_import = data
            
            # Validate all parameters before importing
            for param_name, param_value in config_to_import.items():
                is_valid, error_msg = self.validate_parameter(param_name, param_value)
                if not is_valid:
                    self.logger.error(f"Import validation failed for {param_name}: {error_msg}")
                    return False
            
            # If all parameters are valid, update the configuration
            self.config = deepcopy(config_to_import)
            
            # Log the import
            change_record = {
                'timestamp': datetime.now().isoformat(),
                'action': 'config_import',
                'source_file': filepath,
                'config_id': self.config_id
            }
            self.change_history.append(change_record)
            self.logger.info(f"Configuration imported from {filepath}")
            
            return True
        except Exception as e:
            self.logger.error(f"Error importing configuration: {e}")
            return False
    
    def reset_to_defaults(self) -> None:
        """Reset all parameters to their default values."""
        old_config = deepcopy(self.config)
        self.config = deepcopy(DEFAULT_CONFIG)
        
        # Log the reset
        change_record = {
            'timestamp': datetime.now().isoformat(),
            'action': 'reset_to_defaults',
            'old_config': old_config,
            'config_id': self.config_id
        }
        self.change_history.append(change_record)
        self.logger.info("Configuration reset to defaults")
    
    def get_parameter_bounds(self, param_name: str) -> Optional[Dict[str, Any]]:
        """Get the bounds for a specific parameter."""
        return PARAMETER_BOUNDS.get(param_name)
    
    def get_change_history(self) -> list:
        """Get the history of parameter changes."""
        return deepcopy(self.change_history)
    
    def clear_change_history(self) -> None:
        """Clear the parameter change history."""
        self.change_history.clear()
        self.logger.info("Change history cleared")

# Global configuration instance for backward compatibility
_global_config = ChessConfig()

# Backward compatibility functions
def validate_parameter(param_name: str, param_value: Any) -> bool:
    """Validate a parameter value against defined bounds."""
    is_valid, _ = _global_config.validate_parameter(param_name, param_value)
    return is_valid

def update_parameter(param_name: str, new_value: Any) -> bool:
    """Update a configuration parameter with validation."""
    return _global_config.update_parameter(param_name, new_value)

def get_current_config() -> Dict[str, Any]:
    """Get the current configuration as a dictionary."""
    return _global_config.get_current_config()

def export_config(filepath: str) -> bool:
    """Export current configuration to a JSON file."""
    return _global_config.export_config(filepath)

def import_config(filepath: str) -> bool:
    """Import configuration from a JSON file with validation."""
    return _global_config.import_config(filepath)

def reset_to_defaults() -> None:
    """Reset all parameters to their default values."""
    _global_config.reset_to_defaults()

# Expose current configuration values for direct access
PIECE_VALUES = _global_config.get_parameter('piece_values')
MOBILITY_WEIGHT = _global_config.get_parameter('mobility_weight')
PAWN_STRUCTURE_BONUS = _global_config.get_parameter('pawn_structure_bonus')
KING_SAFETY_PENALTY = _global_config.get_parameter('king_safety_penalty')
SEARCH_DEPTH = _global_config.get_parameter('search_depth')


if __name__ == "__main__":
    print("Testing ChessConfig...")
    config = ChessConfig("test")
    print(f"Config ID: {config.config_id}")
    print(f"Piece values: {config.get_parameter('piece_values')}")
    print("Test completed successfully!")