from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

class FailureAnalyzer:
    """
    Analyzes failure reports from the mutation engine and generates
    recommended alternative strategies when the engine is paused.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the analyzer with optional configuration.
        
        Args:
            config: Dictionary containing configuration parameters
                    (e.g., template library, parameter ranges, etc.)
        """
        self.config = config or {}
        self.failure_history = []

    def analyze_failure(self, failure_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a failure report and generate a recommended strategy.
        
        Args:
            failure_report: Dictionary containing failure details
                Expected keys:
                - 'error_type': str (e.g., 'template_error', 'parameter_out_of_bounds')
                - 'template_used': str
                - 'parameters': dict
                - 'mutation_type': str
                - 'context': dict (optional)
        
        Returns:
            Dictionary with recommended strategy
        """
        self.failure_history.append(failure_report)
        
        error_type = failure_report.get('error_type', 'unknown')
        template_used = failure_report.get('template_used', '')
        parameters = failure_report.get('parameters', {})
        mutation_type = failure_report.get('mutation_type', '')
        
        # Generate recommendation based on error type
        if error_type == 'template_error':
            recommendation = self._handle_template_error(template_used, parameters)
        elif error_type == 'parameter_out_of_bounds':
            recommendation = self._handle_parameter_error(parameters, mutation_type)
        elif error_type == 'mutation_failure':
            recommendation = self._handle_mutation_failure(mutation_type, parameters)
        else:
            recommendation = self._handle_unknown_error(failure_report)
        
        # Add metadata to recommendation
        recommendation['analysis_id'] = len(self.failure_history)
        recommendation['original_error'] = error_type
        recommendation['confidence'] = self._calculate_confidence(recommendation)
        
        logger.info(f"Generated recommendation for failure #{len(self.failure_history)}: {recommendation['strategy']}")
        return recommendation

    def _handle_template_error(self, template: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest alternative templates when the current one fails.
        """
        # Suggest different template families
        alternative_templates = self._get_alternative_templates(template)
        
        return {
            'strategy': 'switch_template',
            'recommended_action': 'Try a different template family',
            'alternative_templates': alternative_templates,
            'parameter_tuning': {
                'adjust': ['complexity', 'structure'],
                'suggestion': 'Reduce template complexity or use a simpler structure'
            },
            'details': f"Template '{template}' failed. Consider using one of: {alternative_templates}"
        }

    def _handle_parameter_error(self, parameters: Dict[str, Any], mutation_type: str) -> Dict[str, Any]:
        """
        Suggest parameter tuning when parameters are out of bounds.
        """
        # Analyze which parameters caused the issue
        problematic_params = self._identify_problematic_parameters(parameters)
        
        return {
            'strategy': 'tune_parameters',
            'recommended_action': 'Adjust parameter ranges and values',
            'parameter_adjustments': {
                param: {
                    'current_value': parameters.get(param),
                    'suggested_range': self._get_suggested_range(param, mutation_type),
                    'adjustment_type': 'shrink' if self._is_out_of_bounds(param, parameters.get(param)) else 'shift'
                }
                for param in problematic_params
            },
            'details': f"Parameters {problematic_params} caused bounds error. Suggested ranges provided."
        }

    def _handle_mutation_failure(self, mutation_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest a new mutation paradigm when the current one fails.
        """
        alternative_paradigms = self._get_alternative_paradigms(mutation_type)
        
        return {
            'strategy': 'change_paradigm',
            'recommended_action': 'Switch to a different mutation paradigm',
            'alternative_paradigms': alternative_paradigms,
            'paradigm_details': {
                paradigm: self._get_paradigm_description(paradigm)
                for paradigm in alternative_paradigms[:3]  # Top 3 suggestions
            },
            'details': f"Mutation type '{mutation_type}' failed. Consider: {alternative_paradigms}"
        }

    def _handle_unknown_error(self, failure_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a conservative recommendation for unknown errors.
        """
        return {
            'strategy': 'conservative_reset',
            'recommended_action': 'Reset to default configuration and retry',
            'suggestions': [
                'Use default templates',
                'Reduce mutation rate',
                'Simplify parameter space',
                'Enable verbose logging for debugging'
            ],
            'details': 'Unknown error occurred. Recommended to start with conservative settings.'
        }

    def _get_alternative_templates(self, current_template: str) -> list:
        """Get alternative templates based on the current one."""
        template_library = self.config.get('template_library', {
            'structural': ['template_a', 'template_b', 'template_c'],
            'functional': ['template_d', 'template_e'],
            'hybrid': ['template_f']
        })
        
        # Find the category of the current template
        for category, templates in template_library.items():
            if current_template in templates:
                # Return templates from other categories
                alternatives = []
                for cat, temps in template_library.items():
                    if cat != category:
                        alternatives.extend(temps)
                return alternatives[:3]  # Return top 3 alternatives
        
        # If template not found, return all templates
        all_templates = [t for temps in template_library.values() for t in temps]
        return all_templates[:3]

    def _identify_problematic_parameters(self, parameters: Dict[str, Any]) -> list:
        """Identify parameters that are likely causing issues."""
        problematic = []
        param_ranges = self.config.get('parameter_ranges', {})
        
        for param, value in parameters.items():
            if param in param_ranges:
                min_val, max_val = param_ranges[param]
                if not (min_val <= value <= max_val):
                    problematic.append(param)
            else:
                # Unknown parameter - flag it
                problematic.append(param)
        
        return problematic if problematic else list(parameters.keys())[:2]

    def _get_suggested_range(self, param: str, mutation_type: str) -> tuple:
        """Get suggested parameter range based on mutation type."""
        default_ranges = self.config.get('parameter_ranges', {})
        mutation_specific = self.config.get('mutation_specific_ranges', {}).get(mutation_type, {})
        
        # Prefer mutation-specific ranges, fall back to defaults
        if param in mutation_specific:
            return mutation_specific[param]
        elif param in default_ranges:
            return default_ranges[param]
        else:
            return (0.0, 1.0)  # Default safe range

    def _is_out_of_bounds(self, param: str, value: Any) -> bool:
        """Check if a parameter value is out of bounds."""
        param_ranges = self.config.get('parameter_ranges', {})
        if param in param_ranges:
            min_val, max_val = param_ranges[param]
            return not (min_val <= value <= max_val)
        return False

    def _get_alternative_paradigms(self, current_paradigm: str) -> list:
        """Get alternative mutation paradigms."""
        paradigms = self.config.get('mutation_paradigms', [
            'point_mutation',
            'crossover',
            'inversion',
            'translocation',
            'duplication',
            'deletion'
        ])
        
        # Return paradigms different from the current one
        alternatives = [p for p in paradigms if p != current_paradigm]
        return alternatives[:3]  # Return top 3 alternatives

    def _get_paradigm_description(self, paradigm: str) -> str:
        """Get a description of a mutation paradigm."""
        descriptions = {
            'point_mutation': 'Change single elements in the sequence',
            'crossover': 'Combine elements from two parent sequences',
            'inversion': 'Reverse a subsequence',
            'translocation': 'Move a subsequence to a different position',
            'duplication': 'Duplicate a subsequence',
            'deletion': 'Remove a subsequence'
        }
        return descriptions.get(paradigm, 'Unknown paradigm')

    def _calculate_confidence(self, recommendation: Dict[str, Any]) -> float:
        """Calculate confidence score for the recommendation."""
        # Simple heuristic based on strategy type
        confidence_map = {
            'switch_template': 0.7,
            'tune_parameters': 0.8,
            'change_paradigm': 0.6,
            'conservative_reset': 0.9
        }
        return confidence_map.get(recommendation.get('strategy', 'conservative_reset'), 0.5)

    def get_failure_summary(self) -> Dict[str, Any]:
        """Get a summary of all failures analyzed."""
        if not self.failure_history:
            return {'total_failures': 0, 'message': 'No failures recorded'}
        
        error_types = {}
        for report in self.failure_history:
            error_type = report.get('error_type', 'unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            'total_failures': len(self.failure_history),
            'error_type_distribution': error_types,
            'most_common_error': max(error_types, key=error_types.get) if error_types else None
        }


# Convenience function for quick analysis
def generate_recommended_strategy(failure_report: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generate a recommended strategy when the mutation engine is paused.
    
    Args:
        failure_report: Dictionary containing failure details
        config: Optional configuration dictionary
    
    Returns:
        Dictionary with recommended strategy
    """
    analyzer = FailureAnalyzer(config)
    return analyzer.analyze_failure(failure_report)