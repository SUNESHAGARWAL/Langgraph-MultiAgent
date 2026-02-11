"""
Model Versioning and A/B Testing Framework

This module provides:
1. Model version management
2. Feature flags for gradual rollout
3. A/B testing experiment tracking
4. Version-specific agent strategies
5. Traffic splitting and routing

Usage:
    from src.versioning import VersionManager, FeatureFlags

    # Initialize
    version_manager = VersionManager()
    feature_flags = FeatureFlags()

    # Get agent version for user
    version = version_manager.get_version_for_user(user_id)

    # Check feature flag
    if feature_flags.is_enabled("use_grader", user_id):
        # Use grader validation
        ...
"""

import os
import hashlib
import json
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StrategyVersion(Enum):
    """Available agent strategy versions"""
    V3_0_0 = "3.0.0"  # Current: Supervisor + Grader + Parallel + Cache
    V3_1_0 = "3.1.0"  # Experimental: Enhanced supervisor with better prompts
    V3_2_0 = "3.2.0"  # Experimental: Different grading criteria
    V3_3_0 = "3.3.0"  # Experimental: No grader (faster but lower quality)


class RolloutStrategy(Enum):
    """Traffic rollout strategies"""
    PERCENTAGE = "percentage"  # X% of users
    USER_LIST = "user_list"    # Specific user IDs
    CANARY = "canary"          # Gradual increase (10% → 25% → 50% → 100%)
    ALL = "all"                # Everyone


@dataclass
class VersionConfig:
    """Configuration for a model version"""
    version: str
    name: str
    description: str
    rollout_percentage: float = 0.0  # 0.0 to 1.0
    enabled: bool = True
    features: Dict[str, bool] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class ExperimentConfig:
    """A/B test experiment configuration"""
    experiment_id: str
    name: str
    description: str
    control_version: str  # Baseline version (e.g., "3.0.0")
    treatment_versions: List[str]  # Test versions (e.g., ["3.1.0", "3.2.0"])
    traffic_split: Dict[str, float]  # {"3.0.0": 0.5, "3.1.0": 0.25, "3.2.0": 0.25}
    start_date: str
    end_date: Optional[str] = None
    active: bool = True
    success_metrics: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class VersionManager:
    """
    Manages model versions and A/B testing experiments.

    Supports:
    - Version registration
    - Traffic splitting
    - A/B experiment tracking
    - User assignment (deterministic based on user_id hash)
    """

    def __init__(self, config_path: str = "./config/versions.json"):
        """
        Initialize version manager.

        Args:
            config_path: Path to version config file
        """
        self.config_path = config_path
        self.versions: Dict[str, VersionConfig] = {}
        self.experiments: Dict[str, ExperimentConfig] = {}
        self._load_config()

    def _load_config(self):
        """Load version configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)

                # Load versions
                for v_data in data.get("versions", []):
                    version_config = VersionConfig(**v_data)
                    self.versions[version_config.version] = version_config

                # Load experiments
                for e_data in data.get("experiments", []):
                    experiment = ExperimentConfig(**e_data)
                    self.experiments[experiment.experiment_id] = experiment

                logger.info(f"Loaded {len(self.versions)} versions and {len(self.experiments)} experiments")

            except Exception as e:
                logger.error(f"Failed to load version config: {e}")
                self._initialize_default_config()
        else:
            logger.info("No version config found, initializing defaults")
            self._initialize_default_config()

    def _initialize_default_config(self):
        """Initialize default version configuration"""
        # Register v3.0.0 as production (100%)
        self.register_version(
            version="3.0.0",
            name="Production Stable",
            description="Supervisor + Grader + Parallel + Semantic Cache",
            rollout_percentage=1.0,
            features={
                "use_grader": True,
                "parallel_execution": True,
                "semantic_cache": True,
                "result_validation": True,
            }
        )

        # Register v3.1.0 as experimental (0%)
        self.register_version(
            version="3.1.0",
            name="Enhanced Supervisor",
            description="Better supervisor prompts and routing logic",
            rollout_percentage=0.0,
            enabled=False,
            features={
                "use_grader": True,
                "parallel_execution": True,
                "semantic_cache": True,
                "result_validation": True,
                "enhanced_prompts": True,
            }
        )

        # Register v3.2.0 as experimental (0%)
        self.register_version(
            version="3.2.0",
            name="Strict Grading",
            description="Stricter grading criteria for higher quality",
            rollout_percentage=0.0,
            enabled=False,
            features={
                "use_grader": True,
                "parallel_execution": True,
                "semantic_cache": True,
                "result_validation": True,
                "strict_grading": True,
            }
        )

        self._save_config()

    def _save_config(self):
        """Save version configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            data = {
                "versions": [v.to_dict() for v in self.versions.values()],
                "experiments": [e.to_dict() for e in self.experiments.values()],
            }

            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved version config to {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to save version config: {e}")

    def register_version(
        self,
        version: str,
        name: str,
        description: str,
        rollout_percentage: float = 0.0,
        enabled: bool = True,
        features: Optional[Dict[str, bool]] = None
    ):
        """
        Register a new model version.

        Args:
            version: Version string (e.g., "3.1.0")
            name: Human-readable name
            description: Description of changes
            rollout_percentage: Initial rollout (0.0 to 1.0)
            enabled: Whether version is enabled
            features: Feature flags for this version
        """
        version_config = VersionConfig(
            version=version,
            name=name,
            description=description,
            rollout_percentage=rollout_percentage,
            enabled=enabled,
            features=features or {},
        )

        self.versions[version] = version_config
        self._save_config()

        logger.info(f"Registered version {version} ({name}) with {rollout_percentage*100}% rollout")

    def get_version_for_user(
        self,
        user_id: str,
        experiment_id: Optional[str] = None
    ) -> str:
        """
        Get model version for a user (deterministic based on user_id).

        Args:
            user_id: User identifier
            experiment_id: Optional experiment ID to participate in

        Returns:
            Version string (e.g., "3.0.0")
        """
        # If experiment specified, use experiment traffic split
        if experiment_id and experiment_id in self.experiments:
            experiment = self.experiments[experiment_id]

            if experiment.active:
                return self._assign_version_by_traffic_split(
                    user_id,
                    experiment.traffic_split
                )

        # Otherwise, use version rollout percentages
        return self._assign_version_by_rollout(user_id)

    def _assign_version_by_rollout(self, user_id: str) -> str:
        """Assign version based on rollout percentages"""
        # Get hash of user_id (0-100)
        user_hash = self._get_user_hash(user_id)

        # Sort versions by rollout percentage (descending)
        enabled_versions = [
            (v.version, v.rollout_percentage)
            for v in self.versions.values()
            if v.enabled and v.rollout_percentage > 0
        ]

        # Default to highest rollout version
        if not enabled_versions:
            return "3.0.0"  # Fallback

        enabled_versions.sort(key=lambda x: x[1], reverse=True)

        # Assign based on cumulative percentage
        cumulative = 0
        for version, percentage in enabled_versions:
            cumulative += percentage * 100

            if user_hash < cumulative:
                return version

        # Fallback to first enabled version
        return enabled_versions[0][0]

    def _assign_version_by_traffic_split(
        self,
        user_id: str,
        traffic_split: Dict[str, float]
    ) -> str:
        """Assign version based on experiment traffic split"""
        user_hash = self._get_user_hash(user_id)

        cumulative = 0
        for version, percentage in traffic_split.items():
            cumulative += percentage * 100

            if user_hash < cumulative:
                return version

        # Fallback to first version
        return list(traffic_split.keys())[0]

    def _get_user_hash(self, user_id: str) -> int:
        """Get deterministic hash (0-100) for user_id"""
        hash_obj = hashlib.md5(user_id.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        return hash_int % 100

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        description: str,
        control_version: str,
        treatment_versions: List[str],
        traffic_split: Optional[Dict[str, float]] = None
    ) -> ExperimentConfig:
        """
        Create a new A/B test experiment.

        Args:
            experiment_id: Unique experiment ID
            name: Experiment name
            description: Experiment description
            control_version: Baseline version
            treatment_versions: Test versions
            traffic_split: Manual traffic split (or auto-calculate)

        Returns:
            ExperimentConfig

        Example:
            manager.create_experiment(
                experiment_id="grading_test_001",
                name="Grading Strategy Test",
                description="Compare standard vs strict grading",
                control_version="3.0.0",
                treatment_versions=["3.2.0"],
                traffic_split={"3.0.0": 0.7, "3.2.0": 0.3}
            )
        """
        # Auto-calculate traffic split if not provided
        if traffic_split is None:
            all_versions = [control_version] + treatment_versions
            equal_split = 1.0 / len(all_versions)
            traffic_split = {v: equal_split for v in all_versions}

        experiment = ExperimentConfig(
            experiment_id=experiment_id,
            name=name,
            description=description,
            control_version=control_version,
            treatment_versions=treatment_versions,
            traffic_split=traffic_split,
            start_date=datetime.utcnow().isoformat(),
            success_metrics=[
                "avg_latency",
                "success_rate",
                "validation_pass_rate",
                "user_satisfaction",
            ]
        )

        self.experiments[experiment_id] = experiment
        self._save_config()

        logger.info(f"Created experiment {experiment_id}: {name}")
        return experiment

    def update_rollout(self, version: str, new_percentage: float):
        """
        Update rollout percentage for a version (canary deployment).

        Args:
            version: Version to update
            new_percentage: New rollout percentage (0.0 to 1.0)

        Example:
            # Gradual rollout
            manager.update_rollout("3.1.0", 0.10)  # 10%
            # ... monitor metrics ...
            manager.update_rollout("3.1.0", 0.25)  # 25%
            # ... monitor metrics ...
            manager.update_rollout("3.1.0", 0.50)  # 50%
            # ... monitor metrics ...
            manager.update_rollout("3.1.0", 1.00)  # 100%
        """
        if version in self.versions:
            old_percentage = self.versions[version].rollout_percentage
            self.versions[version].rollout_percentage = new_percentage
            self._save_config()

            logger.info(f"Updated rollout for {version}: {old_percentage*100}% → {new_percentage*100}%")
        else:
            logger.warning(f"Version {version} not found")

    def get_version_config(self, version: str) -> Optional[VersionConfig]:
        """Get configuration for a specific version"""
        return self.versions.get(version)

    def list_versions(self) -> List[VersionConfig]:
        """List all registered versions"""
        return list(self.versions.values())

    def list_experiments(self) -> List[ExperimentConfig]:
        """List all experiments"""
        return list(self.experiments.values())


class FeatureFlags:
    """
    Feature flag management for gradual feature rollout.

    Supports:
    - Per-feature rollout percentages
    - User-specific overrides
    - Environment-based flags
    """

    def __init__(self, config_path: str = "./config/feature_flags.json"):
        """
        Initialize feature flags.

        Args:
            config_path: Path to feature flags config
        """
        self.config_path = config_path
        self.flags: Dict[str, Dict[str, Any]] = {}
        self._load_config()

    def _load_config(self):
        """Load feature flags from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.flags = json.load(f)

                logger.info(f"Loaded {len(self.flags)} feature flags")

            except Exception as e:
                logger.error(f"Failed to load feature flags: {e}")
                self._initialize_default_flags()
        else:
            self._initialize_default_flags()

    def _initialize_default_flags(self):
        """Initialize default feature flags"""
        self.flags = {
            "use_grader": {
                "enabled": True,
                "rollout_percentage": 1.0,
                "description": "Enable result grader validation"
            },
            "parallel_execution": {
                "enabled": True,
                "rollout_percentage": 1.0,
                "description": "Enable parallel agent execution"
            },
            "semantic_cache": {
                "enabled": True,
                "rollout_percentage": 1.0,
                "description": "Enable semantic caching for Genie"
            },
            "enhanced_prompts": {
                "enabled": False,
                "rollout_percentage": 0.0,
                "description": "Use enhanced supervisor prompts"
            },
            "strict_grading": {
                "enabled": False,
                "rollout_percentage": 0.0,
                "description": "Use strict grading criteria"
            },
            "fast_mode": {
                "enabled": False,
                "rollout_percentage": 0.0,
                "description": "Skip grader for faster responses (lower quality)"
            },
        }

        self._save_config()

    def _save_config(self):
        """Save feature flags to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, 'w') as f:
                json.dump(self.flags, f, indent=2)

            logger.info(f"Saved feature flags to {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to save feature flags: {e}")

    def is_enabled(self, flag_name: str, user_id: Optional[str] = None) -> bool:
        """
        Check if feature flag is enabled for user.

        Args:
            flag_name: Name of feature flag
            user_id: Optional user ID for % rollout

        Returns:
            True if enabled, False otherwise

        Example:
            if feature_flags.is_enabled("use_grader", user_id):
                # Use grader validation
                result = grader_node(state)
            else:
                # Skip grader
                result = supervisor_node(state)
        """
        if flag_name not in self.flags:
            logger.warning(f"Unknown feature flag: {flag_name}")
            return False

        flag_config = self.flags[flag_name]

        # Check if globally disabled
        if not flag_config.get("enabled", False):
            return False

        # Check rollout percentage
        rollout = flag_config.get("rollout_percentage", 0.0)

        if rollout >= 1.0:
            return True  # 100% rollout

        if user_id:
            # Deterministic assignment based on user_id hash
            user_hash = self._get_user_hash(user_id)
            return user_hash < (rollout * 100)

        # If no user_id, check global enable
        return rollout > 0.0

    def _get_user_hash(self, user_id: str) -> int:
        """Get deterministic hash (0-100) for user_id"""
        hash_obj = hashlib.md5(user_id.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        return hash_int % 100

    def set_flag(self, flag_name: str, enabled: bool, rollout_percentage: float = 1.0):
        """
        Set feature flag state.

        Args:
            flag_name: Name of flag
            enabled: Whether enabled globally
            rollout_percentage: Rollout percentage (0.0 to 1.0)

        Example:
            # Enable for 10% of users
            feature_flags.set_flag("enhanced_prompts", True, 0.10)
        """
        if flag_name not in self.flags:
            self.flags[flag_name] = {"description": ""}

        self.flags[flag_name]["enabled"] = enabled
        self.flags[flag_name]["rollout_percentage"] = rollout_percentage

        self._save_config()

        logger.info(f"Set flag {flag_name}: enabled={enabled}, rollout={rollout_percentage*100}%")

    def get_all_flags(self) -> Dict[str, Dict[str, Any]]:
        """Get all feature flags"""
        return self.flags


# Singleton instances
_version_manager = None
_feature_flags = None


def get_version_manager() -> VersionManager:
    """Get singleton VersionManager instance"""
    global _version_manager

    if _version_manager is None:
        _version_manager = VersionManager()

    return _version_manager


def get_feature_flags() -> FeatureFlags:
    """Get singleton FeatureFlags instance"""
    global _feature_flags

    if _feature_flags is None:
        _feature_flags = FeatureFlags()

    return _feature_flags
