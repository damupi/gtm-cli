"""Custom exceptions for GTM Orchestrator."""

from typing import Any


class GTMOrchestratorError(Exception):
    """Base exception for GTM Orchestrator."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(GTMOrchestratorError):
    """Raised when there's a configuration issue."""


class ProfileNotFoundError(ConfigurationError):
    """Raised when a profile doesn't exist."""

    def __init__(self, profile_name: str) -> None:
        super().__init__(
            f"Profile '{profile_name}' not found. "
            f"Use 'gtm profile create {profile_name}' to create it."
        )
        self.profile_name = profile_name


class ProfileExistsError(ConfigurationError):
    """Raised when trying to create a profile that already exists."""

    def __init__(self, profile_name: str) -> None:
        super().__init__(f"Profile '{profile_name}' already exists.")
        self.profile_name = profile_name


class AuthenticationError(GTMOrchestratorError):
    """Raised when authentication fails."""


class NotLoggedInError(AuthenticationError):
    """Raised when user is not logged in."""

    def __init__(self, profile_name: str = "default") -> None:
        super().__init__(
            f"Not logged in to profile '{profile_name}'. Use 'gtm login' to authenticate."
        )
        self.profile_name = profile_name


class TokenExpiredError(AuthenticationError):
    """Raised when the OAuth token has expired and cannot be refreshed."""

    def __init__(self) -> None:
        super().__init__("Authentication token expired. Please run 'gtm login' again.")


class APIError(GTMOrchestratorError):
    """Raised when the GTM API returns an error."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_details)
        self.status_code = status_code


class ResourceNotFoundError(APIError):
    """Raised when a requested resource doesn't exist."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(
            f"{resource_type} '{resource_id}' not found.",
            status_code=404,
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class PermissionDeniedError(APIError):
    """Raised when the user doesn't have permission for an operation."""

    def __init__(self, operation: str) -> None:
        super().__init__(
            f"Permission denied for operation: {operation}. Check your GTM account permissions.",
            status_code=403,
        )
        self.operation = operation


class ValidationError(GTMOrchestratorError):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"Validation error for '{field}': {message}")
        self.field = field
