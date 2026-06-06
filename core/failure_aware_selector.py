"""Failure-aware mutation selector that learns from past failures."""

import os
import json
import logging
import numpy as np
from collections import deque
from typing import List, Dict, Optional, Tuple, Any

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class FeatureVectorExtractor:
    """Computes feature vectors from mutation context."""

    def __init__(self):
        self._feature_dim = 3

    def extract(self, context: Dict[str, Any]) -> Tuple[float, float, float]:
        """Extract feature vector from mutation context.
        
        Args:
            context: Dictionary containing mutation context with keys:
                - 'code': The source code string
                - 'imports': List of import statements
                - 'files': List of file paths involved
        
        Returns:
            Tuple of (complexity, import_count, file_count)
        """
        code = context.get('code', '')
        imports = context.get('imports', [])
        files = context.get('files', [])

        # Compute complexity as lines of code
        if isinstance(code, str):
            complexity = float(len(code.splitlines()))
        else:
            complexity = 0.0

        # Count imports
        if isinstance(imports, list):
            import_count = float(len(imports))
        else:
            import_count = 0.0

        # Count files
        if isinstance(files, list):
            file_count = float(len(files))
        else:
            file_count = 0.0

        return (complexity, import_count, file_count)

    def get_feature_dim(self) -> int:
        """Return the dimension of the feature vector."""
        return self._feature_dim


class FailureLogger:
    """Records mutation attempts with error type, feature vector, and outcome."""

    ERROR_TYPES = ("import", "syntax", "integration")

    def __init__(self, max_records: int = 200):
        self.max_records = max_records
        self.records: List[Dict[str, Any]] = []
        self._feature_dim = 3  # complexity, import_count, file_count

    def log_attempt(
        self,
        error_type: str,
        feature_vector: Tuple[float, float, float],
        success: bool,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record a mutation attempt."""
        if error_type not in self.ERROR_TYPES:
            raise ValueError(f"Invalid error_type: {error_type}. Must be one of {self.ERROR_TYPES}")

        if len(feature_vector) != self._feature_dim:
            raise ValueError(f"Feature vector must have {self._feature_dim} elements")

        record = {
            "error_type": error_type,
            "feature_vector": list(feature_vector),
            "success": success,
            "metadata": metadata or {}
        }
        self.records.append(record)

        # Trim to max_records
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]

    def get_recent_failures(self, n: int = 50) -> List[Dict]:
        """Get the most recent n failure records."""
        failures = [r for r in self.records if not r["success"]]
        return failures[-n:] if len(failures) > n else failures

    def get_training_data(self, n: int = 50) -> Tuple[np.ndarray, np.ndarray]:
        """Get feature matrix and labels for the last n records."""
        recent = self.records[-n:] if len(self.records) > n else self.records
        if len(recent) < 2:
            return np.empty((0, self._feature_dim)), np.empty(0)

        X = np.array([r["feature_vector"] for r in recent])
        y = np.array([1 if r["success"] else 0 for r in recent])
        return X, y

    def clear(self) -> None:
        """Clear all records."""
        self.records.clear()

    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "max_records": self.max_records,
            "records": self.records
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "FailureLogger":
        """Deserialize from dictionary."""
        logger_instance = cls(max_records=data.get("max_records", 200))
        logger_instance.records = data.get("records", [])
        return logger_instance


class LightweightClassifier:
    """Classifier trained on recent failures to predict success probability."""

    def __init__(self, model_type: str = "logistic", max_samples: int = 50):
        if model_type not in ("logistic", "decision_tree"):
            raise ValueError(f"Unsupported model_type: {model_type}")

        self.model_type = model_type
        self.max_samples = max_samples
        self._model = None
        self._feature_dim = 3
        self._is_trained = False

        if SKLEARN_AVAILABLE:
            if model_type == "logistic":
                self._model = LogisticRegression(
                    max_iter=1000,
                    random_state=42,
                    class_weight="balanced"
                )
            else:
                self._model = DecisionTreeClassifier(
                    max_depth=3,
                    random_state=42,
                    class_weight="balanced"
                )
        else:
            logger.warning("scikit-learn not available; classifier will use fallback heuristic")

    def train(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train the classifier on given data."""
        if len(X) < 2:
            logger.warning("Insufficient training data (need at least 2 samples)")
            self._is_trained = False
            return

        if X.shape[1] != self._feature_dim:
            raise ValueError(f"Expected {self._feature_dim} features, got {X.shape[1]}")

        # Limit samples
        if len(X) > self.max_samples:
            X = X[-self.max_samples:]
            y = y[-self.max_samples:]

        if SKLEARN_AVAILABLE and self._model is not None:
            try:
                self._model.fit(X, y)
                self._is_trained = True
                logger.debug(f"Classifier trained on {len(X)} samples")
            except Exception as e:
                logger.warning(f"Classifier training failed: {e}")
                self._is_trained = False
        else:
            # Fallback: simple heuristic based on success rate
            self._is_trained = True
            self._fallback_success_rate = float(np.mean(y))
            self._fallback_feature_weights = np.array([0.3, 0.3, 0.4])  # complexity, imports, files

    def predict_proba(self, feature_vector: Tuple[float, float, float]) -> float:
        """Predict probability of success for a given feature vector."""
        if len(feature_vector) != self._feature_dim:
            raise ValueError(f"Feature vector must have {self._feature_dim} elements")

        if not self._is_trained:
            return 0.5  # Default probability when untrained

        X = np.array([feature_vector])

        if SKLEARN_AVAILABLE and self._model is not None:
            try:
                proba = self._model.predict_proba(X)
                # Return probability of class 1 (success)
                if proba.shape[1] > 1:
                    return float(proba[0][1])
                else:
                    return float(proba[0][0])
            except Exception as e:
                logger.warning(f"Prediction failed: {e}")
                return 0.5
        else:
            # Fallback heuristic
            complexity, import_count, file_count = feature_vector
            # Normalize features (rough estimates)
            norm_complexity = min(complexity / 10.0, 1.0)
            norm_imports = min(import_count / 20.0, 1.0)
            norm_files = min(file_count / 10.0, 1.0)

            # Weighted combination
            risk_score = (
                self._fallback_feature_weights[0] * norm_complexity +
                self._fallback_feature_weights[1] * norm_imports +
                self._fallback_feature_weights[2] * norm_files
            )

            # Adjust base success rate by risk
            adjusted_rate = self._fallback_success_rate * (1.0 - risk_score * 0.5)
            return max(0.0, min(1.0, adjusted_rate))

    def is_trained(self) -> bool:
        """Check if classifier has been trained."""
        return self._is_trained

    def reset(self) -> None:
        """Reset the classifier."""
        self._model = None
        self._is_trained = False
        if SKLEARN_AVAILABLE:
            if self.model_type == "logistic":
                self._model = LogisticRegression(
                    max_iter=1000,
                    random_state=42,
                    class_weight="balanced"
                )
            else:
                self._model = DecisionTreeClassifier(
                    max_depth=3,
                    random_state=42,
                    class_weight="balanced"
                )


class FailureAwareSelector:
    """Selects mutations based on predicted success probability using failure history."""

    def __init__(
        self,
        threshold: Optional[float] = None,
        classifier: Optional[LightweightClassifier] = None,
        logger_instance: Optional[FailureLogger] = None,
        config_path: Optional[str] = None
    ):
        # Load threshold from env, config, or default
        if threshold is not None:
            self.threshold = threshold
        else:
            env_threshold = os.environ.get("MUTATION_SELECTION_THRESHOLD")
            if env_threshold is not None:
                self.threshold = float(env_threshold)
            else:
                self.threshold = 0.3  # Default

        self.classifier = classifier or LightweightClassifier()
        self.logger = logger_instance or FailureLogger()
        self.config_path = config_path
        self.feature_extractor = FeatureVectorExtractor()

        # Load config if path provided
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

    def _load_config(self, path: str) -> None:
        """Load configuration from JSON file."""
        try:
            with open(path, 'r') as f:
                config = json.load(f)
            if "threshold" in config:
                self.threshold = float(config["threshold"])
            logger.info(f"Loaded config from {path}, threshold={self.threshold}")
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")

    def save_config(self, path: Optional[str] = None) -> None:
        """Save current configuration to JSON file."""
        save_path = path or self.config_path
        if not save_path:
            logger.warning("No config path specified, cannot save")
            return

        config = {"threshold": self.threshold}
        try:
            with open(save_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved config to {save_path}")
        except Exception as e:
            logger.warning(f"Failed to save config to {save_path}: {e}")

    def predict_success(
        self,
        context: Dict[str, Any],
        error_type: str = "integration"
    ) -> float:
        """Predict probability of success for a mutation given its context.
        
        Args:
            context: Dictionary containing mutation context with keys:
                - 'code': The source code string
                - 'imports': List of import statements
                - 'files': List of file paths involved
            error_type: Type of error to check for
        
        Returns:
            Probability of success (0.0 to 1.0)
        """
        # Extract features from context
        feature_vector = self.feature_extractor.extract(context)

        # Train classifier on recent failures if not trained
        if not self.classifier.is_trained():
            X, y = self.logger.get_training_data(n=50)
            if len(X) >= 2:
                self.classifier.train(X, y)

        # Get success probability
        prob = self.classifier.predict_proba(feature_vector)

        logger.debug(
            f"Success prediction: prob={prob:.3f}, threshold={self.threshold}, "
            f"features={feature_vector}, error_type={error_type}"
        )

        return prob

    def evaluate_mutation(
        self,
        context: Dict[str, Any],
        error_type: str = "integration"
    ) -> Tuple[bool, float]:
        """
        Evaluate whether a mutation should be applied.
        Returns (accepted, probability).
        """
        prob = self.predict_success(context, error_type)

        # Decision based on threshold
        accepted = prob >= self.threshold

        logger.debug(
            f"Mutation evaluation: prob={prob:.3f}, threshold={self.threshold}, "
            f"accepted={accepted}"
        )

        return accepted, prob

    def select_mutation(
        self,
        mutations: List[Tuple[str, Dict[str, Any]]],
        error_type: str = "integration"
    ) -> Optional[Tuple[str, float]]:
        """
        Select the best mutation from a list of (description, context) pairs.
        Returns (description, probability) of the best accepted mutation, or None.
        """
        if not mutations:
            return None

        best_mutation = None
        best_prob = -1.0

        for description, context in mutations:
            accepted, prob = self.evaluate_mutation(context, error_type)
            if accepted and prob > best_prob:
                best_prob = prob
                best_mutation = (description, prob)

        # If no mutation accepted, fall back to simplest (lowest complexity)
        if best_mutation is None:
            logger.info("No mutation accepted, falling back to simplest alternative")
            # Find mutation with lowest complexity
            simplest = min(
                mutations,
                key=lambda m: self.feature_extractor.extract(m[1])[0]
            )
            best_mutation = (simplest[0], 0.0)

        return best_mutation

    def get_simpler_alternative(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a simpler alternative context by reducing complexity.
        Returns modified context with reduced features.
        """
        feature_vector = self.feature_extractor.extract(context)
        complexity, import_count, file_count = feature_vector

        # Reduce complexity by 50%, reduce imports by 30%, keep file count same
        reduced_complexity = max(complexity * 0.5, 1.0)
        reduced_imports = max(int(import_count * 0.7), 1)
        reduced_files = max(file_count, 1)

        # Create a modified context with reduced features
        modified_context = dict(context)
        if 'code' in modified_context and isinstance(modified_context['code'], str):
            # Reduce code to approximately reduced_complexity lines
            lines = modified_context['code'].splitlines()
            target_lines = max(int(reduced_complexity), 1)
            if len(lines) > target_lines:
                modified_context['code'] = '\n'.join(lines[:target_lines])
        
        if 'imports' in modified_context and isinstance(modified_context['imports'], list):
            modified_context['imports'] = modified_context['imports'][:int(reduced_imports)]
        
        if 'files' in modified_context and isinstance(modified_context['files'], list):
            modified_context['files'] = modified_context['files'][:int(reduced_files)]

        return modified_context

    def set_threshold(self, threshold: float) -> None:
        """Update the selection threshold."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")
        self.threshold = threshold
        logger.info(f"Threshold updated to {threshold}")

    def get_threshold(self) -> float:
        """Get current threshold."""
        return self.threshold

    def record_outcome(
        self,
        error_type: str,
        context: Dict[str, Any],
        success: bool,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record the outcome of a mutation attempt."""
        feature_vector = self.feature_extractor.extract(context)
        self.logger.log_attempt(error_type, feature_vector, success, metadata)

        # Retrain classifier if we have new data
        X, y = self.logger.get_training_data(n=50)
        if len(X) >= 2:
            self.classifier.train(X, y)

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about selection performance."""
        total = len(self.logger.records)
        successes = sum(1 for r in self.logger.records if r["success"])
        failures = total - successes

        return {
            "total_attempts": total,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / total if total > 0 else 0.0,
            "threshold": self.threshold,
            "classifier_trained": self.classifier.is_trained(),
            "classifier_type": self.classifier.model_type if hasattr(self.classifier, 'model_type') else "unknown"
        }


# Convenience function to create a default selector
def create_default_selector(
    threshold: Optional[float] = None,
    config_path: Optional[str] = None
) -> FailureAwareSelector:
    """Create a FailureAwareSelector with default components."""
    logger_instance = FailureLogger()
    classifier = LightweightClassifier()
    return FailureAwareSelector(
        threshold=threshold,
        classifier=classifier,
        logger_instance=logger_instance,
        config_path=config_path
    )