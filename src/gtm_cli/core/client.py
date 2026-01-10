"""GTM API client wrapper."""

import contextlib
from typing import Any

from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gtm_cli.core.auth import AuthManager, get_auth_manager
from gtm_cli.core.config import ConfigManager, get_config_manager
from gtm_cli.utils.errors import (
    APIError,
    PermissionDeniedError,
    ResourceNotFoundError,
)

# GTM API version
API_SERVICE_NAME = "tagmanager"
API_VERSION = "v2"


class GTMClient:
    """Wrapper for the Google Tag Manager API."""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        auth_manager: AuthManager | None = None,
    ) -> None:
        """Initialize the GTM client.

        Args:
            config_manager: ConfigManager instance (uses global if None)
            auth_manager: AuthManager instance (uses global if None)
        """
        self.config_manager = config_manager or get_config_manager()
        self.auth_manager = auth_manager or get_auth_manager()
        self._service: Any = None
        self._credentials: Credentials | None = None

    def _get_service(
        self,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> Any:
        """Get or create the GTM API service.

        Args:
            profile_name: Profile to use
            service_account_path: Optional service account path override

        Returns:
            GTM API service object
        """
        credentials = self.auth_manager.get_credentials(
            profile_name=profile_name,
            service_account_path=service_account_path,
        )

        # Rebuild service if credentials changed
        if self._credentials is not credentials:
            self._service = build(
                API_SERVICE_NAME,
                API_VERSION,
                credentials=credentials,
                cache_discovery=False,
            )
            self._credentials = credentials

        return self._service

    def _handle_error(self, error: HttpError, operation: str) -> None:
        """Convert HTTP errors to GTM Orchestrator exceptions.

        Args:
            error: The HTTP error
            operation: Description of the operation that failed

        Raises:
            ResourceNotFoundError: For 404 errors
            PermissionDeniedError: For 403 errors
            APIError: For other errors
        """
        status_code = error.resp.status

        if status_code == 404:
            raise ResourceNotFoundError("Resource", operation) from error
        elif status_code == 403:
            raise PermissionDeniedError(operation) from error
        else:
            error_details: dict[str, Any] = {}
            with contextlib.suppress(AttributeError):
                error_details = error.error_details or {}

            raise APIError(
                f"API error during {operation}: {error}",
                status_code=status_code,
                error_details=error_details,
            ) from error

    # Account methods
    def list_accounts(
        self,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all GTM accounts accessible to the user.

        Args:
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            List of account dictionaries
        """
        service = self._get_service(profile_name, service_account_path)
        try:
            response = service.accounts().list().execute()
            return response.get("account", [])
        except HttpError as e:
            self._handle_error(e, "list accounts")
            return []  # Never reached, but satisfies type checker

    def get_account(
        self,
        account_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific GTM account.

        Args:
            account_id: The account ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Account dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}"
        try:
            return service.accounts().get(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"get account {account_id}")
            return {}

    # Container methods
    def list_containers(
        self,
        account_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all containers in an account.

        Args:
            account_id: The account ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            List of container dictionaries
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}"
        try:
            response = service.accounts().containers().list(parent=parent).execute()
            return response.get("container", [])
        except HttpError as e:
            self._handle_error(e, f"list containers for account {account_id}")
            return []

    def get_container(
        self,
        account_id: str,
        container_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific container.

        Args:
            account_id: The account ID
            container_id: The container ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Container dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}"
        try:
            return service.accounts().containers().get(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"get container {container_id}")
            return {}

    # Workspace methods
    def list_workspaces(
        self,
        account_id: str,
        container_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all workspaces in a container.

        Args:
            account_id: The account ID
            container_id: The container ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            List of workspace dictionaries
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}"
        try:
            response = (
                service.accounts().containers().workspaces().list(parent=parent).execute()
            )
            return response.get("workspace", [])
        except HttpError as e:
            self._handle_error(e, "list workspaces")
            return []

    def get_workspace(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Workspace dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            return service.accounts().containers().workspaces().get(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"get workspace {workspace_id}")
            return {}

    # Tag methods
    def list_tags(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all tags in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            List of tag dictionaries
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            response = (
                service.accounts()
                .containers()
                .workspaces()
                .tags()
                .list(parent=parent)
                .execute()
            )
            return response.get("tag", [])
        except HttpError as e:
            self._handle_error(e, "list tags")
            return []

    # Trigger methods
    def list_triggers(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all triggers in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            List of trigger dictionaries
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            response = (
                service.accounts()
                .containers()
                .workspaces()
                .triggers()
                .list(parent=parent)
                .execute()
            )
            return response.get("trigger", [])
        except HttpError as e:
            self._handle_error(e, "list triggers")
            return []

    # Variable methods
    def list_variables(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all variables in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            List of variable dictionaries
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            response = (
                service.accounts()
                .containers()
                .workspaces()
                .variables()
                .list(parent=parent)
                .execute()
            )
            return response.get("variable", [])
        except HttpError as e:
            self._handle_error(e, "list variables")
            return []

    # Version methods
    def list_versions(
        self,
        account_id: str,
        container_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all versions in a container.

        Args:
            account_id: The account ID
            container_id: The container ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            List of version header dictionaries
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}"
        try:
            response = (
                service.accounts()
                .containers()
                .version_headers()
                .list(parent=parent)
                .execute()
            )
            return response.get("containerVersionHeader", [])
        except HttpError as e:
            self._handle_error(e, "list versions")
            return []


# Global client instance
_client: GTMClient | None = None


def get_client() -> GTMClient:
    """Get or create the global GTM client instance."""
    global _client
    if _client is None:
        _client = GTMClient()
    return _client
