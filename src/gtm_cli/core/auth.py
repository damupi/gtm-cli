"""Authentication handling for GTM Orchestrator."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuth2Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from gtm_cli.core.config import ConfigManager, Profile, get_config_manager
from gtm_cli.utils.errors import (
    AuthenticationError,
    ConfigurationError,
    NotLoggedInError,
    TokenExpiredError,
)

# OAuth2 scopes for GTM API
SCOPES = {
    "readonly": "https://www.googleapis.com/auth/tagmanager.readonly",
    "edit_containers": "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "delete_containers": "https://www.googleapis.com/auth/tagmanager.delete.containers",
    "edit_versions": "https://www.googleapis.com/auth/tagmanager.edit.containerversions",
    "publish": "https://www.googleapis.com/auth/tagmanager.publish",
    "manage_users": "https://www.googleapis.com/auth/tagmanager.manage.users",
    "manage_accounts": "https://www.googleapis.com/auth/tagmanager.manage.accounts",
}

# Predefined scope sets
SCOPE_SETS: dict[str, list[str]] = {
    "readonly": [SCOPES["readonly"]],
    "edit": [
        SCOPES["readonly"],
        SCOPES["edit_containers"],
        SCOPES["edit_versions"],
    ],
    "full": list(SCOPES.values()),
}

# Default OAuth2 client configuration for installed applications
DEFAULT_CLIENT_CONFIG = {
    "installed": {
        "client_id": "",  # User must provide their own
        "client_secret": "",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


def get_scopes(scope_name: str = "full") -> list[str]:
    """Get the OAuth2 scopes for a given scope set name.

    Args:
        scope_name: Name of the scope set (readonly, edit, full)

    Returns:
        List of OAuth2 scope URLs
    """
    return SCOPE_SETS.get(scope_name, SCOPE_SETS["full"])


def is_gcloud_installed() -> bool:
    """Check if gcloud CLI is installed and available."""
    return shutil.which("gcloud") is not None


class AuthManager:
    """Manages authentication for GTM Orchestrator."""

    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        """Initialize the auth manager.

        Args:
            config_manager: ConfigManager instance (uses global if None)
        """
        self.config_manager = config_manager or get_config_manager()

    def get_client_secrets_path(self) -> Path:
        """Get the path to the client secrets file."""
        return self.config_manager.config_dir / "client_secrets.json"

    def _load_client_config(self) -> dict[str, Any]:
        """Load OAuth2 client configuration.

        Returns:
            Client configuration dict

        Raises:
            ConfigurationError: If client secrets file not found
        """
        secrets_path = self.get_client_secrets_path()

        if not secrets_path.exists():
            raise ConfigurationError(
                f"OAuth2 client secrets not found at {secrets_path}. "
                "Please download from Google Cloud Console and save there."
            )

        with open(secrets_path) as f:
            return json.load(f)

    def _get_service_account_credentials(
        self, credentials_path: str, scopes: list[str]
    ) -> Credentials:
        """Load service account credentials.

        Args:
            credentials_path: Path to service account JSON file
            scopes: OAuth2 scopes to request

        Returns:
            Service account credentials

        Raises:
            ConfigurationError: If credentials file not found
        """
        path = Path(credentials_path)
        if not path.exists():
            raise ConfigurationError(f"Service account credentials not found at {path}")

        return service_account.Credentials.from_service_account_file(str(path), scopes=scopes)

    def _get_oauth2_credentials(self, profile: Profile, scopes: list[str]) -> OAuth2Credentials:
        """Load OAuth2 credentials for a profile.

        OAuth tokens are shared across all profiles since they represent the same
        Google account. If no token exists for this profile, we try the default
        token (from any profile), since all OAuth profiles share the same identity.

        Args:
            profile: The profile to load credentials for
            scopes: OAuth2 scopes

        Returns:
            OAuth2 credentials

        Raises:
            NotLoggedInError: If no token exists for any profile
            TokenExpiredError: If token is expired and cannot be refreshed
        """
        token_path = self.config_manager.get_token_path(profile.name)

        # If no token for this profile, try to use any existing OAuth token
        if not token_path.exists():
            # Look for any existing token file
            tokens_dir = self.config_manager.config_dir / "tokens"
            if tokens_dir.exists():
                for token_file in tokens_dir.glob("*.json"):
                    token_path = token_file
                    break

        if not token_path.exists():
            raise NotLoggedInError(profile.name)

        with open(token_path) as f:
            token_data = json.load(f)

        creds = OAuth2Credentials.from_authorized_user_info(token_data, scopes)

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(profile.name, creds)
            except Exception as e:
                raise TokenExpiredError() from e

        if not creds.valid:
            raise TokenExpiredError()

        return creds

    def _save_credentials(self, profile_name: str, credentials: OAuth2Credentials) -> None:
        """Save OAuth2 credentials to token file.

        Args:
            profile_name: Profile name
            credentials: Credentials to save
        """
        token_path = self.config_manager.get_token_path(profile_name)
        self.config_manager.ensure_directories()

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }

        with open(token_path, "w") as f:
            json.dump(token_data, f, indent=2)

    def get_credentials(
        self,
        profile_name: str | None = None,
        service_account_path: str | None = None,
    ) -> Credentials:
        """Get credentials for API access.

        Priority:
        1. Service account path (explicit override)
        2. GOOGLE_APPLICATION_CREDENTIALS env var
        3. Application Default Credentials (gcloud)
        4. Profile-specific OAuth2 credentials

        Args:
            profile_name: Profile to use (uses default if None)
            service_account_path: Optional path to service account JSON

        Returns:
            Valid credentials for API access

        Raises:
            AuthenticationError: If credentials cannot be obtained
        """
        scopes = get_scopes("full")

        # Check for service account override
        if service_account_path:
            return self._get_service_account_credentials(service_account_path, scopes)

        # Check environment variable
        env_sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if env_sa_path:
            return self._get_service_account_credentials(env_sa_path, scopes)

        # Load from profile
        profile = self.config_manager.get_profile(profile_name)
        scopes = get_scopes(profile.auth.scopes)

        if profile.auth.method == "service_account":
            if not profile.auth.credentials_path:
                raise ConfigurationError(
                    f"Profile '{profile.name}' uses service account auth "
                    "but no credentials_path is configured."
                )
            return self._get_service_account_credentials(profile.auth.credentials_path, scopes)

        # Use OAuth2 from profile (has correct GTM scopes)
        return self._get_oauth2_credentials(profile, scopes)

    def login_with_gcloud(self, scopes: list[str]) -> str:
        """Perform login using gcloud CLI.

        Args:
            scopes: OAuth2 scopes to request

        Returns:
            Email address of logged-in user

        Raises:
            AuthenticationError: If login fails
        """
        if not is_gcloud_installed():
            raise AuthenticationError("gcloud CLI is not installed")

        # Build the gcloud command
        scopes_str = ",".join(scopes)
        cmd = [
            "gcloud",
            "auth",
            "application-default",
            "login",
            f"--scopes={scopes_str}",
        ]

        try:
            # Run gcloud login - this opens browser automatically
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise AuthenticationError(f"gcloud login failed: {e}") from e
        except FileNotFoundError as e:
            raise AuthenticationError("gcloud CLI not found") from e

        # Get the email from gcloud
        try:
            email_result = subprocess.run(
                ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                capture_output=True,
                text=True,
                check=True,
            )
            email = (
                email_result.stdout.strip().split("\n")[0]
                if email_result.stdout.strip()
                else "unknown"
            )
            return email
        except Exception:
            return "unknown"

    def login(
        self,
        profile_name: str | None = None,
        no_browser: bool = False,
        port: int = 8080,
        use_gcloud: bool | None = None,
    ) -> str:
        """Perform login flow.

        Args:
            profile_name: Profile to login to (uses default if None)
            no_browser: If True, use copy/paste flow instead of browser
            port: Port for local callback server
            use_gcloud: If True, use gcloud CLI. If None, auto-detect.

        Returns:
            Email address of logged-in user

        Raises:
            ConfigurationError: If client secrets not found (and no gcloud)
            AuthenticationError: If login fails
        """
        if profile_name is None:
            profile_name = self.config_manager.get_global_config().default_profile

        # Ensure profile exists (create default if needed)
        if not self.config_manager.profile_exists(profile_name):
            if profile_name == "default":
                profile = Profile(name="default")
                self.config_manager.save_profile(profile)
            else:
                from gtm_cli.utils.errors import ProfileNotFoundError

                raise ProfileNotFoundError(profile_name)

        profile = self.config_manager.get_profile(profile_name)
        scopes = get_scopes(profile.auth.scopes)

        # Auto-detect: use gcloud if available, otherwise fall back to OAuth2
        if use_gcloud is None:
            use_gcloud = is_gcloud_installed()

        if use_gcloud:
            return self.login_with_gcloud(scopes)

        # Fall back to manual OAuth2 flow (requires client_secrets.json)
        client_config = self._load_client_config()

        flow = InstalledAppFlow.from_client_config(client_config, scopes)

        try:
            if no_browser:
                # Console-based flow
                creds = flow.run_console()
            else:
                # Browser-based flow with local server
                creds = flow.run_local_server(
                    port=port,
                    prompt="consent",
                    success_message="Authentication successful! You can close this window.",
                )
        except Exception as e:
            raise AuthenticationError(f"Login failed: {e}") from e

        # Save credentials
        self._save_credentials(profile_name, creds)

        # Get user info
        email = self._get_user_email(creds)
        return email

    def _get_user_email(self, credentials: OAuth2Credentials) -> str:
        """Get the email address from credentials.

        Args:
            credentials: OAuth2 credentials

        Returns:
            User email address or 'unknown'
        """
        try:
            from googleapiclient.discovery import build

            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info.get("email", "unknown")
        except Exception:
            return "unknown"

    def logout(self, profile_name: str | None = None) -> None:
        """Remove stored credentials for a profile.

        Args:
            profile_name: Profile to logout from (uses default if None)
        """
        if profile_name is None:
            profile_name = self.config_manager.get_global_config().default_profile

        token_path = self.config_manager.get_token_path(profile_name)
        if token_path.exists():
            token_path.unlink()

    def get_login_status(self, profile_name: str | None = None) -> dict[str, Any]:
        """Get login status for a profile.

        Args:
            profile_name: Profile to check (uses default if None)

        Returns:
            Dict with 'logged_in', 'profile', and optionally 'email' keys
        """
        if profile_name is None:
            profile_name = self.config_manager.get_global_config().default_profile

        token_path = self.config_manager.get_token_path(profile_name)

        if not token_path.exists():
            return {"logged_in": False, "profile": profile_name}

        try:
            profile = self.config_manager.get_profile(profile_name)
            scopes = get_scopes(profile.auth.scopes)
            creds = self._get_oauth2_credentials(profile, scopes)
            email = self._get_user_email(creds)
            return {"logged_in": True, "profile": profile_name, "email": email}
        except Exception:
            return {"logged_in": False, "profile": profile_name}


# Global auth manager instance
_auth_manager: AuthManager | None = None


def get_auth_manager() -> AuthManager:
    """Get or create the global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
