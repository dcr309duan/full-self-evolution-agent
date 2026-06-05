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
        self.failure_pattern_counts = {}

    def get_failure_pattern_key(self, failure_context: Dict[str, Any]) -> str:
        """
        Return a normalized string key for deduplication and retry counting.
        
        Args:
            failure_context: Dictionary containing failure context information
                Expected keys:
                - 'error_type': str
                - 'template_used': str (optional)
                - 'mutation_type': str (optional)
                - 'parameter_pattern': str (optional) - normalized parameter pattern
        
        Returns:
            A normalized string key representing the failure pattern
        """
        error_type = failure_context.get('error_type', 'unknown')
        template_used = failure_context.get('template_used', '')
        mutation_type = failure_context.get('mutation_type', '')
        parameter_pattern = failure_context.get('parameter_pattern', '')
        
        # Normalize the key components
        normalized_template = template_used.strip().lower() if template_used else 'no_template'
        normalized_mutation = mutation_type.strip().lower() if mutation_type else 'no_mutation'
        normalized_parameter = parameter_pattern.strip().lower() if parameter_pattern else 'no_parameters'
        
        # Create a structured key
        key_parts = [
            f"error:{error_type}",
            f"template:{normalized_template}",
            f"mutation:{normalized_mutation}",
            f"params:{normalized_parameter}"
        ]
        
        return "|".join(key_parts)

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
        
        # Generate failure pattern key for deduplication
        failure_context = {
            'error_type': error_type,
            'template_used': template_used,
            'mutation_type': mutation_type,
            'parameter_pattern': self._normalize_parameter_pattern(parameters)
        }
        pattern_key = self.get_failure_pattern_key(failure_context)
        
        # Update failure pattern counts
        self.failure_pattern_counts[pattern_key] = self.failure_pattern_counts.get(pattern_key, 0) + 1
        retry_count = self.failure_pattern_counts[pattern_key]
        
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
        recommendation['failure_pattern_key'] = pattern_key
        recommendation['retry_count'] = retry_count
        
        # Add actionable recommendations for design limitations
        if self._is_design_limitation(error_type, recommendation):
            recommendation['design_limitation_recommendations'] = self._get_design_limitation_recommendations(error_type, template_used, mutation_type)
        
        logger.info(f"Generated recommendation for failure #{len(self.failure_history)}: {recommendation['strategy']}")
        return recommendation

    def analyze_subsystem_failure(self, subsystem_name: str, failure_report: dict) -> str:
        """
        Analyze a failure report for a specific subsystem and return a recommended
        new strategy for evolving that subsystem.
        
        Args:
            subsystem_name: Name of the subsystem that failed
            failure_report: Dictionary containing failure details for the subsystem
        
        Returns:
            A string describing the recommended new strategy for the subsystem
        """
        self.failure_history.append(failure_report)
        
        error_type = failure_report.get('error_type', 'unknown')
        template_used = failure_report.get('template_used', '')
        parameters = failure_report.get('parameters', {})
        mutation_type = failure_report.get('mutation_type', '')
        
        # Generate failure pattern key for subsystem
        failure_context = {
            'error_type': error_type,
            'template_used': template_used,
            'mutation_type': mutation_type,
            'parameter_pattern': self._normalize_parameter_pattern(parameters)
        }
        pattern_key = self.get_failure_pattern_key(failure_context)
        
        # Update failure pattern counts
        self.failure_pattern_counts[pattern_key] = self.failure_pattern_counts.get(pattern_key, 0) + 1
        
        # Generate subsystem-specific recommendation
        if error_type == 'template_error':
            recommendation = self._handle_subsystem_template_error(subsystem_name, template_used, parameters)
        elif error_type == 'parameter_out_of_bounds':
            recommendation = self._handle_subsystem_parameter_error(subsystem_name, parameters, mutation_type)
        elif error_type == 'mutation_failure':
            recommendation = self._handle_subsystem_mutation_failure(subsystem_name, mutation_type, parameters)
        else:
            recommendation = self._handle_subsystem_unknown_error(subsystem_name, failure_report)
        
        # Add design limitation recommendations if applicable
        if self._is_design_limitation(error_type, {}):
            recommendation += " " + self._get_design_limitation_recommendations(error_type, template_used, mutation_type)
        
        logger.info(f"Generated subsystem recommendation for '{subsystem_name}' failure #{len(self.failure_history)}: {recommendation}")
        return recommendation

    def _normalize_parameter_pattern(self, parameters: Dict[str, Any]) -> str:
        """
        Normalize parameter dictionary into a pattern string for deduplication.
        
        Args:
            parameters: Dictionary of parameter names and values
        
        Returns:
            Normalized parameter pattern string
        """
        if not parameters:
            return "empty"
        
        # Sort parameters by name for consistency
        sorted_params = sorted(parameters.items())
        
        # Create a pattern based on parameter names and value types
        pattern_parts = []
        for param_name, param_value in sorted_params:
            if isinstance(param_value, (int, float)):
                # For numeric values, categorize by range
                if param_value < 0:
                    value_type = "negative"
                elif param_value == 0:
                    value_type = "zero"
                elif param_value < 1:
                    value_type = "small_positive"
                else:
                    value_type = "large_positive"
                pattern_parts.append(f"{param_name}:{value_type}")
            elif isinstance(param_value, str):
                pattern_parts.append(f"{param_name}:string")
            elif isinstance(param_value, bool):
                pattern_parts.append(f"{param_name}:bool")
            elif isinstance(param_value, list):
                pattern_parts.append(f"{param_name}:list:{len(param_value)}")
            elif isinstance(param_value, dict):
                pattern_parts.append(f"{param_name}:dict:{len(param_value)}")
            else:
                pattern_parts.append(f"{param_name}:other")
        
        return ",".join(pattern_parts)

    def _is_design_limitation(self, error_type: str, recommendation: Dict[str, Any]) -> bool:
        """
        Determine if the error indicates a design limitation.
        
        Args:
            error_type: Type of error encountered
            recommendation: Generated recommendation dictionary
        
        Returns:
            True if the error suggests a design limitation
        """
        # Design limitations are typically indicated by repeated failures
        # or specific error types that suggest fundamental issues
        design_limitation_indicators = [
            'template_error',
            'mutation_failure',
            'parameter_out_of_bounds'
        ]
        
        # Check if error type suggests design limitation
        if error_type in design_limitation_indicators:
            # Check if this pattern has occurred multiple times
            pattern_key = recommendation.get('failure_pattern_key', '')
            if pattern_key and self.failure_pattern_counts.get(pattern_key, 0) >= 2:
                return True
        
        return False

    def _get_design_limitation_recommendations(self, error_type: str, template: str, mutation_type: str) -> str:
        """
        Generate actionable recommendations for alternative approaches when a design limitation is detected.
        
        Args:
            error_type: Type of error encountered
            template: Template that was being used
            mutation_type: Mutation type that was being applied
        
        Returns:
            String with actionable recommendations
        """
        recommendations = []
        
        if error_type == 'template_error':
            recommendations.append(
                f"Design limitation detected with template '{template}'. "
                f"Consider redesigning the template structure to be more flexible. "
                f"Alternative approaches: (1) Use a more generic template that supports multiple patterns, "
                f"(2) Implement template composition to combine simpler templates, "
                f"(3) Add template validation before execution to catch issues early."
            )
        elif error_type == 'parameter_out_of_bounds':
            recommendations.append(
                f"Design limitation detected with parameter ranges. "
                f"Consider implementing adaptive parameter bounds that adjust based on context. "
                f"Alternative approaches: (1) Use dynamic range calculation based on historical data, "
                f"(2) Implement parameter normalization to keep values within valid ranges, "
                f"(3) Add parameter constraints that are context-aware."
            )
        elif error_type == 'mutation_failure':
            recommendations.append(
                f"Design limitation detected with mutation type '{mutation_type}'. "
                f"Consider implementing a fallback mutation strategy when the primary one fails. "
                f"Alternative approaches: (1) Use a hybrid mutation approach that combines multiple types, "
                f"(2) Implement mutation validation before application, "
                f"(3) Add mutation rate adaptation based on failure history."
            )
        else:
            recommendations.append(
                f"Design limitation detected. Consider reviewing the overall system architecture. "
                f"Alternative approaches: (1) Implement graceful degradation, "
                f"(2) Add comprehensive error handling with fallback mechanisms, "
                f"(3) Consider using a different algorithmic approach."
            )
        
        return " ".join(recommendations)

    def _handle_subsystem_template_error(self, subsystem_name: str, template: str, parameters: Dict[str, Any]) -> str:
        """
        Suggest alternative templates for a specific subsystem when the current one fails.
        """
        alternative_templates = self._get_alternative_templates(template)
        return (f"Subsystem '{subsystem_name}' template error: Switch to a different template family. "
                f"Recommended templates: {alternative_templates}. "
                f"Consider reducing template complexity or using a simpler structure for this subsystem.")

    def _handle_subsystem_parameter_error(self, subsystem_name: str, parameters: Dict[str, Any], mutation_type: str) -> str:
        """
        Suggest parameter tuning for a specific subsystem when parameters are out of bounds.
        """
        problematic_params = self._identify_problematic_parameters(parameters)
        adjustments = []
        for param in problematic_params:
            suggested_range = self._get_suggested_range(param, mutation_type)
            adjustments.append(f"{param}: adjust to range {suggested_range}")
        return (f"Subsystem '{subsystem_name}' parameter error: Tune parameters. "
                f"Problematic parameters: {problematic_params}. "
                f"Suggested adjustments: {'; '.join(adjustments)}. "
                f"Consider subsystem-specific parameter ranges for better evolution.")

    def _handle_subsystem_mutation_failure(self, subsystem_name: str, mutation_type: str, parameters: Dict[str, Any]) -> str:
        """
        Suggest a new mutation paradigm for a specific subsystem when the current one fails.
        """
        alternative_paradigms = self._get_alternative_paradigms(mutation_type)
        return (f"Subsystem '{subsystem_name}' mutation failure: Switch to a different mutation paradigm. "
                f"Recommended paradigms: {alternative_paradigms}. "
                f"Consider subsystem-specific optimizations like adjusting mutation rate or using "
                f"specialized mutation templates for '{subsystem_name}'.")

    def _handle_subsystem_unknown_error(self, subsystem_name: str, failure_report: Dict[str, Any]) -> str:
        """
        Generate a conservative recommendation for unknown errors in a specific subsystem.
        """
        return (f"Subsystem '{subsystem_name}' unknown error: Reset to default configuration and retry. "
                f"Suggestions: Use default templates, reduce mutation rate, simplify parameter space, "
                f"enable verbose logging for debugging. Consider subsystem-specific optimizations "
                f"once the error is identified.")

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
            'most_common_error': max(error_types, key=error_types.get) if error_types else None,
            'failure_pattern_counts': dict(self.failure_pattern_counts)
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