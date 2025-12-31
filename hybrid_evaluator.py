"""
Hybrid Evaluator for Chess Bot Studio.

Combines traditional heuristic evaluation with neural network evaluation.
Allows smooth transition from hand-crafted to learned evaluation.
"""

import chess
from typing import Dict, Any, Optional
from pathlib import Path

from evaluation import evaluate_board
from config import ChessConfig, DEFAULT_CONFIG


class HybridEvaluator:
    """
    Combines heuristic and neural network evaluation.
    
    The blend ratio determines how much weight to give each:
    - blend=0.0: Pure heuristic evaluation
    - blend=0.5: 50/50 mix
    - blend=1.0: Pure neural network evaluation
    """
    
    def __init__(self, config: Optional[ChessConfig] = None, neural_blend: float = 0.0):
        """
        Initialize the hybrid evaluator.
        
        Args:
            config: Chess configuration for heuristic evaluation
            neural_blend: How much to weight neural network (0.0 to 1.0)
        """
        self.config = config
        self.neural_blend = max(0.0, min(1.0, neural_blend))
        self.neural_network = None
        self._load_neural_network()
        
        # Track which evaluation method is being used
        self.last_eval_method = 'heuristic'
    
    def _load_neural_network(self) -> bool:
        """Load the neural network if available."""
        try:
            from neural_network import ChessNeuralNetwork, NN_WEIGHTS_PATH
            
            if NN_WEIGHTS_PATH.exists():
                self.neural_network = ChessNeuralNetwork()
                print(f"[HybridEval] Neural network loaded (v{self.neural_network.version})")
                return True
            else:
                print("[HybridEval] No neural network weights found, using heuristic only")
                return False
        except ImportError:
            print("[HybridEval] Neural network module not available")
            return False
        except Exception as e:
            print(f"[HybridEval] Error loading neural network: {e}")
            return False
    
    def reload_neural_network(self) -> bool:
        """Reload the neural network (for hot-reload after training)."""
        return self._load_neural_network()
    
    def evaluate(self, board: chess.Board) -> float:
        """
        Evaluate a chess position using hybrid approach.
        
        Args:
            board: Chess position to evaluate
            
        Returns:
            Evaluation score (positive = white advantage)
        """
        # Get heuristic evaluation
        heuristic_eval = evaluate_board(board, self.config)
        
        # If no neural network or blend is 0, return pure heuristic
        if self.neural_network is None or self.neural_blend == 0.0:
            self.last_eval_method = 'heuristic'
            return heuristic_eval
        
        # Get neural network evaluation
        try:
            # Neural network returns -1 to 1, scale to centipawn range
            neural_eval = self.neural_network.evaluate(board) * 1000  # Scale to ~centipawns
            
            # Blend the evaluations
            blended_eval = (1 - self.neural_blend) * heuristic_eval + self.neural_blend * neural_eval
            
            self.last_eval_method = f'hybrid({self.neural_blend:.0%})'
            return blended_eval
            
        except Exception as e:
            # Fall back to heuristic on error
            self.last_eval_method = 'heuristic (fallback)'
            return heuristic_eval
    
    def set_neural_blend(self, blend: float) -> None:
        """Update the neural network blend ratio."""
        self.neural_blend = max(0.0, min(1.0, blend))
        print(f"[HybridEval] Neural blend set to {self.neural_blend:.0%}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get evaluator status."""
        return {
            'neural_available': self.neural_network is not None,
            'neural_blend': self.neural_blend,
            'neural_version': self.neural_network.version if self.neural_network else None,
            'last_eval_method': self.last_eval_method
        }


# Global hybrid evaluator instance
_hybrid_evaluator: Optional[HybridEvaluator] = None


def get_hybrid_evaluator(config: Optional[ChessConfig] = None) -> HybridEvaluator:
    """Get or create the global hybrid evaluator."""
    global _hybrid_evaluator
    if _hybrid_evaluator is None:
        _hybrid_evaluator = HybridEvaluator(config)
    return _hybrid_evaluator


def hybrid_evaluate(board: chess.Board, config: Optional[ChessConfig] = None) -> float:
    """Convenience function for hybrid evaluation."""
    evaluator = get_hybrid_evaluator(config)
    return evaluator.evaluate(board)
