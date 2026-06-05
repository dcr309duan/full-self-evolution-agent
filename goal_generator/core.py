from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from schema.validator import validate_cycle_report, ValidationError
from schema.models import CycleReport, GoalSpec, ReportVersion


class MigrationError(Exception):
    """Raised when migration of a CycleReport fails."""
    pass


class GoalGenerationError(Exception):
    """Raised when goal generation fails."""
    pass


class GoalType(Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    STRETCH = "stretch"
    MILESTONE = "milestone"


@dataclass
class GoalGeneratorConfig:
    """Configuration for the goal generator."""
    target_version: str = "2.0"
    auto_migrate: bool = True
    strict_validation: bool = True
    max_goals_per_report: int = 10
    default_goal_type: GoalType = GoalType.SHORT_TERM


class GoalGenerator:
    """
    Core goal generator that processes CycleReport objects and produces GoalSpec objects.
    Handles validation, migration, and goal generation logic.
    """

    def __init__(self, config: Optional[GoalGeneratorConfig] = None):
        self.config = config or GoalGeneratorConfig()
        self._migration_history: List[dict] = []

    def process_report(self, report: CycleReport) -> GoalSpec:
        """
        Process a single CycleReport and generate a GoalSpec.
        
        Args:
            report: The CycleReport to process
            
        Returns:
            GoalSpec: The generated goal specification
            
        Raises:
            ValidationError: If the report fails validation
            MigrationError: If migration fails
            GoalGenerationError: If goal generation fails
        """
        # Validate the report
        self._validate_report(report)
        
        # Check for version mismatch and migrate if needed
        if self._version_mismatch(report):
            report = self._migrate_report(report)
        
        # Generate goals from the validated/migrated report
        return self._generate_goals(report)

    def process_reports(self, reports: List[CycleReport]) -> List[GoalSpec]:
        """
        Process multiple CycleReport objects and generate GoalSpec objects.
        
        Args:
            reports: List of CycleReport objects to process
            
        Returns:
            List[GoalSpec]: List of generated goal specifications
        """
        return [self.process_report(report) for report in reports]

    def _validate_report(self, report: CycleReport) -> None:
        """
        Validate a CycleReport using the schema validator.
        
        Args:
            report: The CycleReport to validate
            
        Raises:
            ValidationError: If validation fails and strict mode is enabled
        """
        try:
            validate_cycle_report(report)
        except ValidationError as e:
            if self.config.strict_validation:
                raise
            # In non-strict mode, log warning but continue
            import warnings
            warnings.warn(f"Validation warning for report {report.id}: {e}")

    def _version_mismatch(self, report: CycleReport) -> bool:
        """
        Check if the report version matches the target version.
        
        Args:
            report: The CycleReport to check
            
        Returns:
            bool: True if version mismatch detected
        """
        current_version = getattr(report, 'version', None)
        if current_version is None:
            return True
        
        # Handle both string and ReportVersion enum
        if isinstance(current_version, ReportVersion):
            return current_version.value != self.config.target_version
        return str(current_version) != self.config.target_version

    def _migrate_report(self, report: CycleReport) -> CycleReport:
        """
        Migrate a CycleReport to the target version.
        
        Args:
            report: The CycleReport to migrate
            
        Returns:
            CycleReport: The migrated report
            
        Raises:
            MigrationError: If migration fails or auto_migrate is disabled
        """
        if not self.config.auto_migrate:
            raise MigrationError(
                f"Version mismatch detected for report {report.id}. "
                f"Auto-migration is disabled."
            )
        
        try:
            migrated_report = self._perform_migration(report)
            self._record_migration(report, migrated_report)
            return migrated_report
        except Exception as e:
            raise MigrationError(f"Migration failed for report {report.id}: {e}")

    def _perform_migration(self, report: CycleReport) -> CycleReport:
        """
        Perform the actual migration logic.
        
        Args:
            report: The CycleReport to migrate
            
        Returns:
            CycleReport: The migrated report
        """
        # Create a new report with updated version
        migrated_data = {
            'id': report.id,
            'version': self.config.target_version,
            'timestamp': datetime.utcnow(),
            'cycle_data': self._migrate_cycle_data(report),
            'metadata': self._migrate_metadata(report),
        }
        
        # Create new CycleReport instance (assuming it accepts dict or kwargs)
        return CycleReport(**migrated_data)

    def _migrate_cycle_data(self, report: CycleReport) -> dict:
        """
        Migrate cycle-specific data.
        
        Args:
            report: The original CycleReport
            
        Returns:
            dict: Migrated cycle data
        """
        # Placeholder for actual migration logic
        # This should be expanded based on specific version differences
        cycle_data = getattr(report, 'cycle_data', {})
        
        # Example migration: ensure required fields exist
        if 'metrics' not in cycle_data:
            cycle_data['metrics'] = {}
        if 'objectives' not in cycle_data:
            cycle_data['objectives'] = []
            
        return cycle_data

    def _migrate_metadata(self, report: CycleReport) -> dict:
        """
        Migrate metadata fields.
        
        Args:
            report: The original CycleReport
            
        Returns:
            dict: Migrated metadata
        """
        metadata = getattr(report, 'metadata', {})
        
        # Add migration metadata
        metadata['migrated_at'] = datetime.utcnow().isoformat()
        metadata['original_version'] = str(getattr(report, 'version', 'unknown'))
        
        return metadata

    def _record_migration(self, original: CycleReport, migrated: CycleReport) -> None:
        """
        Record a migration event in the history.
        
        Args:
            original: The original report before migration
            migrated: The migrated report
        """
        self._migration_history.append({
            'report_id': original.id,
            'original_version': str(getattr(original, 'version', 'unknown')),
            'target_version': self.config.target_version,
            'migrated_at': datetime.utcnow().isoformat(),
            'original_report': original,
            'migrated_report': migrated,
        })

    def _generate_goals(self, report: CycleReport) -> GoalSpec:
        """
        Generate GoalSpec from a validated and migrated CycleReport.
        
        Args:
            report: The processed CycleReport
            
        Returns:
            GoalSpec: The generated goal specification
            
        Raises:
            GoalGenerationError: If goal generation fails
        """
        try:
            goals = self._extract_goals(report)
            return GoalSpec(
                report_id=report.id,
                generated_at=datetime.utcnow(),
                goals=goals[:self.config.max_goals_per_report],
                metadata=self._build_goal_metadata(report)
            )
        except Exception as e:
            raise GoalGenerationError(f"Failed to generate goals for report {report.id}: {e}")

    def _extract_goals(self, report: CycleReport) -> List[dict]:
        """
        Extract and structure goals from the report data.
        
        Args:
            report: The CycleReport to extract goals from
            
        Returns:
            List[dict]: List of structured goal dictionaries
        """
        goals = []
        cycle_data = getattr(report, 'cycle_data', {})
        
        # Extract objectives as primary goals
        objectives = cycle_data.get('objectives', [])
        for obj in objectives:
            goal = {
                'type': self.config.default_goal_type.value,
                'description': obj.get('description', ''),
                'target_date': obj.get('target_date'),
                'metrics': obj.get('metrics', {}),
                'priority': obj.get('priority', 'medium'),
                'status': 'active'
            }
            goals.append(goal)
        
        # Extract key results as sub-goals or milestones
        key_results = cycle_data.get('key_results', [])
        for kr in key_results:
            goal = {
                'type': GoalType.MILESTONE.value,
                'description': kr.get('description', ''),
                'target_date': kr.get('target_date'),
                'metrics': {'current': kr.get('current', 0), 'target': kr.get('target', 100)},
                'priority': 'high',
                'status': 'in_progress'
            }
            goals.append(goal)
        
        return goals

    def _build_goal_metadata(self, report: CycleReport) -> dict:
        """
        Build metadata for the GoalSpec.
        
        Args:
            report: The source CycleReport
            
        Returns:
            dict: Metadata dictionary
        """
        return {
            'source_version': str(getattr(report, 'version', 'unknown')),
            'generator_version': self.config.target_version,
            'generation_timestamp': datetime.utcnow().isoformat(),
            'migration_applied': bool(self._migration_history),
            'total_migrations': len(self._migration_history),
        }

    def get_migration_history(self) -> List[dict]:
        """
        Get the history of migrations performed.
        
        Returns:
            List[dict]: List of migration records
        """
        return self._migration_history.copy()

    def clear_migration_history(self) -> None:
        """Clear the migration history."""
        self._migration_history.clear()


# Convenience function for simple use cases
def generate_goals(report: CycleReport, config: Optional[GoalGeneratorConfig] = None) -> GoalSpec:
    """
    Convenience function to generate goals from a single CycleReport.
    
    Args:
        report: The CycleReport to process
        config: Optional configuration for the generator
        
    Returns:
        GoalSpec: The generated goal specification
    """
    generator = GoalGenerator(config)
    return generator.process_report(report)


def generate_goals_batch(reports: List[CycleReport], config: Optional[GoalGeneratorConfig] = None) -> List[GoalSpec]:
    """
    Convenience function to generate goals from multiple CycleReports.
    
    Args:
        reports: List of CycleReport objects to process
        config: Optional configuration for the generator
        
    Returns:
        List[GoalSpec]: List of generated goal specifications
    """
    generator = GoalGenerator(config)
    return generator.process_reports(reports)