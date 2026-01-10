"""Configuration and profile management for GTM Orchestrator."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from gtm_cli.utils.errors import (
    ConfigurationError,
    ProfileExistsError,
    ProfileNotFoundError,
)

# Default config directory
DEFAULT_CONFIG_DIR = Path.home() / ".gtm-orchestrator"


class AuthConfig(BaseModel):
    """Authentication configuration for a profile."""

    method: str = Field(default="oauth", pattern="^(oauth|service_account)$")
    credentials_path: str | None = None
    scopes: str = "full"


class DefaultsConfig(BaseModel):
    """Default values for GTM resources."""

    account_id: str | None = None
    container_id: str | None = None
    workspace_id: str | None = None


class OutputConfig(BaseModel):
    """Output configuration."""

    format: str = Field(default="table", pattern="^(json|yaml|table)$")
    color: bool = True


class Profile(BaseModel):
    """A GTM Orchestrator profile configuration."""

    name: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for YAML serialization."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Create a Profile from a dictionary."""
        return cls.model_validate(data)


class GlobalConfig(BaseModel):
    """Global configuration settings."""

    default_profile: str = "default"
    output: OutputConfig = Field(default_factory=OutputConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for YAML serialization."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GlobalConfig":
        """Create GlobalConfig from a dictionary."""
        return cls.model_validate(data)


class ConfigManager:
    """Manages GTM Orchestrator configuration and profiles."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the config manager.

        Args:
            config_dir: Path to config directory (defaults to ~/.gtm-orchestrator)
        """
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.profiles_dir = self.config_dir / "profiles"
        self.tokens_dir = self.config_dir / "tokens"
        self.config_file = self.config_dir / "config.yaml"
        self._global_config: GlobalConfig | None = None

    def ensure_directories(self) -> None:
        """Create config directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(exist_ok=True)
        self.tokens_dir.mkdir(exist_ok=True)

    def get_global_config(self) -> GlobalConfig:
        """Load and return the global configuration."""
        if self._global_config is not None:
            return self._global_config

        if self.config_file.exists():
            with open(self.config_file) as f:
                data = yaml.safe_load(f) or {}
            self._global_config = GlobalConfig.from_dict(data)
        else:
            self._global_config = GlobalConfig()

        return self._global_config

    def save_global_config(self, config: GlobalConfig) -> None:
        """Save the global configuration."""
        self.ensure_directories()
        with open(self.config_file, "w") as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False)
        self._global_config = config

    def get_profile_path(self, name: str) -> Path:
        """Get the path to a profile's config file."""
        return self.profiles_dir / f"{name}.yaml"

    def get_token_path(self, name: str) -> Path:
        """Get the path to a profile's OAuth token file."""
        return self.tokens_dir / f"{name}.json"

    def profile_exists(self, name: str) -> bool:
        """Check if a profile exists."""
        return self.get_profile_path(name).exists()

    def list_profiles(self) -> list[str]:
        """List all profile names."""
        if not self.profiles_dir.exists():
            return []
        return [p.stem for p in self.profiles_dir.glob("*.yaml")]

    def get_profile(self, name: str | None = None) -> Profile:
        """Load a profile by name.

        Args:
            name: Profile name (uses default if None)

        Returns:
            The loaded Profile

        Raises:
            ProfileNotFoundError: If profile doesn't exist
        """
        if name is None:
            name = self.get_global_config().default_profile

        profile_path = self.get_profile_path(name)

        if not profile_path.exists():
            # Return a default profile with just the name if it doesn't exist
            if name == "default":
                return Profile(name="default")
            raise ProfileNotFoundError(name)

        with open(profile_path) as f:
            data = yaml.safe_load(f) or {}

        # Ensure name is set
        data["name"] = name
        return Profile.from_dict(data)

    def save_profile(self, profile: Profile, overwrite: bool = False) -> None:
        """Save a profile.

        Args:
            profile: The profile to save
            overwrite: If True, overwrite existing profile

        Raises:
            ProfileExistsError: If profile exists and overwrite is False
        """
        if not overwrite and self.profile_exists(profile.name):
            raise ProfileExistsError(profile.name)

        self.ensure_directories()
        profile_path = self.get_profile_path(profile.name)

        with open(profile_path, "w") as f:
            yaml.dump(profile.to_dict(), f, default_flow_style=False)

    def delete_profile(self, name: str) -> None:
        """Delete a profile and its token.

        Args:
            name: Profile name to delete

        Raises:
            ProfileNotFoundError: If profile doesn't exist
            ConfigurationError: If trying to delete the last profile
        """
        if not self.profile_exists(name):
            raise ProfileNotFoundError(name)

        profiles = self.list_profiles()
        if len(profiles) == 1 and name in profiles:
            raise ConfigurationError("Cannot delete the last profile.")

        # Delete profile file
        self.get_profile_path(name).unlink()

        # Delete token file if it exists
        token_path = self.get_token_path(name)
        if token_path.exists():
            token_path.unlink()

        # If this was the default profile, update default
        config = self.get_global_config()
        if config.default_profile == name:
            remaining = [p for p in profiles if p != name]
            if remaining:
                config.default_profile = remaining[0]
                self.save_global_config(config)

    def set_default_profile(self, name: str) -> None:
        """Set the default profile.

        Args:
            name: Profile name to set as default

        Raises:
            ProfileNotFoundError: If profile doesn't exist
        """
        if not self.profile_exists(name):
            raise ProfileNotFoundError(name)

        config = self.get_global_config()
        config.default_profile = name
        self.save_global_config(config)

    def is_logged_in(self, profile_name: str | None = None) -> bool:
        """Check if a profile has a valid token.

        Args:
            profile_name: Profile to check (uses default if None)

        Returns:
            True if token exists
        """
        if profile_name is None:
            profile_name = self.get_global_config().default_profile

        return self.get_token_path(profile_name).exists()


# Global config manager instance
_config_manager: ConfigManager | None = None


def get_config_manager(config_dir: Path | None = None) -> ConfigManager:
    """Get or create the global config manager instance."""
    global _config_manager
    if _config_manager is None or config_dir is not None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager
