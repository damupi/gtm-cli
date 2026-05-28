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
        """Convert HTTP errors to typed exceptions.

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
        if status_code == 403:
            raise PermissionDeniedError(operation) from error

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
            response = service.accounts().containers().workspaces().list(parent=parent).execute()
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

    def create_workspace(
        self,
        account_id: str,
        container_id: str,
        name: str,
        description: str | None = None,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Create a new workspace in the given container.

        Args:
            account_id: The account ID
            container_id: The container ID
            name: The workspace name
            description: Optional workspace description
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Created workspace dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}"
        body: dict[str, str] = {"name": name}
        if description:
            body["description"] = description
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .create(parent=parent, body=body)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, "create workspace")
            return {}

    def delete_workspace(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> None:
        """Delete a workspace.

        Returns None — the API returns 204 No Content on success.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID to delete
            profile_name: Profile to use
            service_account_path: Optional service account path
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            service.accounts().containers().workspaces().delete(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"delete workspace {workspace_id}")

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
                service.accounts().containers().workspaces().tags().list(parent=parent).execute()
            )
            return response.get("tag", [])
        except HttpError as e:
            self._handle_error(e, "list tags")
            return []

    def create_tag(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        tag_body: dict[str, Any],
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Create a tag in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            tag_body: Tag definition (name, type, parameter, firingTriggerId, etc.)
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Created tag dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .tags()
                .create(parent=parent, body=tag_body)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, "create tag")
            return {}

    def get_tag(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        tag_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific tag in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            tag_id: The tag ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Tag dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/tags/{tag_id}"
        try:
            return service.accounts().containers().workspaces().tags().get(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"get tag {tag_id}")
            return {}

    def update_tag(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        tag_id: str,
        tag_body: dict[str, Any],
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Update a tag in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            tag_id: The tag ID to update
            tag_body: Full tag body (PUT semantics)
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Updated tag dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/tags/{tag_id}"
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .tags()
                .update(path=path, body=tag_body)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, f"update tag {tag_id}")
            return {}

    def delete_tag(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        tag_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> None:
        """Delete a tag from a workspace."""
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/tags/{tag_id}"
        try:
            service.accounts().containers().workspaces().tags().delete(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"delete tag {tag_id}")

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

    def create_trigger(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        trigger_body: dict[str, Any],
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Create a trigger in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            trigger_body: Trigger definition (name, type, parameter, etc.)
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Created trigger dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .triggers()
                .create(parent=parent, body=trigger_body)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, "create trigger")
            return {}

    def get_trigger(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        trigger_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific trigger in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            trigger_id: The trigger ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Trigger dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/triggers/{trigger_id}"
        try:
            return service.accounts().containers().workspaces().triggers().get(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"get trigger {trigger_id}")
            return {}

    def delete_trigger(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        trigger_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> None:
        """Delete a trigger from a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            trigger_id: The trigger ID to delete
            profile_name: Profile to use
            service_account_path: Optional service account path
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/triggers/{trigger_id}"
        try:
            service.accounts().containers().workspaces().triggers().delete(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"delete trigger {trigger_id}")

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

    def get_variable(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        variable_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific variable in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            variable_id: The variable ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Variable dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/variables/{variable_id}"
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .variables()
                .get(path=path)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, f"get variable {variable_id}")
            return {}

    def create_variable(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        variable_body: dict[str, Any],
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Create a new variable in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            variable_body: Variable body dict
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Created variable dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .variables()
                .create(parent=parent, body=variable_body)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, "create variable")
            return {}

    def update_variable(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        variable_id: str,
        variable_body: dict[str, Any],
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Update a variable in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            variable_id: The variable ID to update
            variable_body: Full variable body (PUT semantics)
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Updated variable dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/variables/{variable_id}"
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .variables()
                .update(path=path, body=variable_body)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, f"update variable {variable_id}")
            return {}

    def delete_variable(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        variable_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> None:
        """Delete a variable from a workspace."""
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/variables/{variable_id}"
        try:
            service.accounts().containers().workspaces().variables().delete(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"delete variable {variable_id}")

    def revert_variable(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        variable_id: str,
        fingerprint: str | None = None,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Revert workspace changes for a variable.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            variable_id: The variable ID to revert
            fingerprint: Optional fingerprint for optimistic concurrency
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Dict with reverted variable under the 'variable' key
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/variables/{variable_id}"
        kwargs: dict[str, Any] = {"path": path}
        if fingerprint:
            kwargs["fingerprint"] = fingerprint
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .variables()
                .revert(**kwargs)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, f"revert variable {variable_id}")
            return {}

    # Folder methods
    def list_folders(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all folders in a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            List of folder dictionaries
        """
        service = self._get_service(profile_name, service_account_path)
        parent = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            response = (
                service.accounts().containers().workspaces().folders().list(parent=parent).execute()
            )
            return response.get("folder", [])
        except HttpError as e:
            self._handle_error(e, "list folders")
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
                service.accounts().containers().version_headers().list(parent=parent).execute()
            )
            return response.get("containerVersionHeader", [])
        except HttpError as e:
            self._handle_error(e, "list versions")
            return []

    def get_version(
        self,
        account_id: str,
        container_id: str,
        version_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific container version with full detail.

        Returns all tags, triggers, variables, and the fingerprint timestamp.

        Args:
            account_id: The account ID
            container_id: The container ID
            version_id: The version ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Full version dictionary
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/versions/{version_id}"
        try:
            return service.accounts().containers().versions().get(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"get version {version_id}")
            return {}

    def create_version(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        name: str | None = None,
        notes: str | None = None,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Create a container version from a workspace.

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            name: Optional version name
            notes: Optional version notes
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Response containing containerVersion and optional compilerError/syncStatus
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        body: dict[str, str] = {}
        if name:
            body["name"] = name
        if notes:
            body["notes"] = notes
        try:
            return (
                service.accounts()
                .containers()
                .workspaces()
                .create_version(path=path, body=body)
                .execute()
            )
        except HttpError as e:
            self._handle_error(e, "create version")
            return {}

    def publish_version(
        self,
        account_id: str,
        container_id: str,
        version_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Publish a container version.

        Args:
            account_id: The account ID
            container_id: The container ID
            version_id: The version ID to publish
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Response containing containerVersion
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/versions/{version_id}"
        try:
            return service.accounts().containers().versions().publish(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"publish version {version_id}")
            return {}

    def get_workspace_status(
        self,
        account_id: str,
        container_id: str,
        workspace_id: str,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> dict[str, Any]:
        """Get the status of a workspace (pending changes).

        Args:
            account_id: The account ID
            container_id: The container ID
            workspace_id: The workspace ID
            profile_name: Profile to use
            service_account_path: Optional service account path

        Returns:
            Workspace status with mergeConflict and workspaceChange lists
        """
        service = self._get_service(profile_name, service_account_path)
        path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
        try:
            return service.accounts().containers().workspaces().getStatus(path=path).execute()
        except HttpError as e:
            self._handle_error(e, f"get workspace status {workspace_id}")
            return {}


# Global client instance
_client: GTMClient | None = None


def get_client() -> GTMClient:
    """Get or create the global GTM client instance."""
    global _client
    if _client is None:
        _client = GTMClient()
    return _client
