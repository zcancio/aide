"""
Configuration management for AIde CLI.

Multi-environment support:
  The CLI stores separate credentials per API URL. You can be logged into
  production, staging, and local dev simultaneously.

  Config structure:
  {
    "environments": {
      "https://get.toaide.com": {
        "token": "aide_...",
        "email": "user@example.com",
        "default_aide_id": "..."
      },
      "http://localhost:8000": {
        "token": "aide_...",
        "email": "dev@example.com",
        "default_aide_id": "..."
      }
    },
    "default_url": "https://get.toaide.com"
  }

Environment resolution order:
  1. AIDE_API_URL environment variable
  2. --api-url command line flag (passed via resolve_api_url)
  3. default_url from config file
  4. Fallback: https://get.toaide.com

Usage:
  # Terminal 1 — production
  export AIDE_API_URL=https://get.toaide.com
  aide

  # Terminal 2 — local dev
  export AIDE_API_URL=http://localhost:8000
  aide

  # Or use --api-url flag
  aide login --api-url http://localhost:8000
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_API_URL = "https://get.toaide.com"


class Config:
    """Config manager for AIde CLI with multi-environment support."""

    def __init__(self, api_url_override: str | None = None):
        """
        Initialize config.

        Args:
            api_url_override: Optional --api-url flag value
        """
        self.config_dir = Path.home() / ".aide"
        self.config_file = self.config_dir / "config.json"
        self._data = {}
        self._api_url_override = api_url_override
        self._load()

    def _load(self):
        """Load config from disk."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    self._data = json.load(f)

                # Migrate old flat config to new format
                if "token" in self._data and "environments" not in self._data:
                    self._migrate_flat_config()

            except Exception:
                self._data = {}

        # Ensure environments dict exists
        if "environments" not in self._data:
            self._data["environments"] = {}

    def _migrate_flat_config(self):
        """Migrate old flat config to multi-environment format."""
        old_token = self._data.get("token")
        old_email = self._data.get("email")
        old_aide_id = self._data.get("default_aide_id")
        old_api_url = self._data.get("api_url", DEFAULT_API_URL)

        # Create new structure
        self._data = {
            "environments": {
                old_api_url: {
                    "token": old_token,
                    "email": old_email,
                    "default_aide_id": old_aide_id,
                }
            },
            "default_url": old_api_url,
        }

        self._save()

    def _save(self):
        """Save config to disk with secure permissions."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Write with restricted permissions (owner-only read/write)
        with open(self.config_file, "w") as f:
            json.dump(self._data, f, indent=2)

        # Set file permissions to 0600
        self.config_file.chmod(0o600)

    @property
    def api_url(self) -> str:
        """
        Get current API URL.

        Resolution order:
        1. AIDE_API_URL environment variable
        2. --api-url flag (passed to constructor)
        3. default_url from config
        4. Fallback: https://get.toaide.com
        """
        # 1. Environment variable takes precedence
        env_url = os.environ.get("AIDE_API_URL")
        if env_url:
            return env_url.rstrip("/")

        # 2. Command line flag
        if self._api_url_override:
            return self._api_url_override.rstrip("/")

        # 3. Config default
        default = self._data.get("default_url", DEFAULT_API_URL)
        return default.rstrip("/")

    @property
    def default_url(self) -> str:
        """Get default URL from config."""
        return self._data.get("default_url", DEFAULT_API_URL)

    @default_url.setter
    def default_url(self, value: str):
        """Set default URL."""
        self._data["default_url"] = value.rstrip("/")
        self._save()

    def _get_env(self) -> dict:
        """Get current environment config dict."""
        return self._data["environments"].get(self.api_url, {})

    def _set_env(self, key: str, value):
        """Set a value in current environment config."""
        if self.api_url not in self._data["environments"]:
            self._data["environments"][self.api_url] = {}
        self._data["environments"][self.api_url][key] = value
        self._save()

    @property
    def token(self) -> str | None:
        """Get API token for current environment."""
        return self._get_env().get("token")

    @token.setter
    def token(self, value: str):
        """Set API token for current environment."""
        self._set_env("token", value)

    @property
    def email(self) -> str | None:
        """Get user email for current environment."""
        return self._get_env().get("email")

    @email.setter
    def email(self, value: str):
        """Set user email for current environment."""
        self._set_env("email", value)

    @property
    def default_aide_id(self) -> str | None:
        """Get default aide ID for current environment."""
        return self._get_env().get("default_aide_id")

    @default_aide_id.setter
    def default_aide_id(self, value: str | None):
        """Set default aide ID for current environment."""
        self._set_env("default_aide_id", value)

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated for current environment."""
        return bool(self.token)

    def clear_environment(self, url: str | None = None):
        """
        Clear credentials for a specific environment.

        Args:
            url: Environment URL to clear. If None, clears current environment.
        """
        target_url = (url or self.api_url).rstrip("/")
        if target_url in self._data["environments"]:
            del self._data["environments"][target_url]
            self._save()

    def clear_all(self):
        """Clear all credentials and delete config file."""
        self._data = {"environments": {}}
        if self.config_file.exists():
            self.config_file.unlink()

    def list_environments(self) -> list[dict]:
        """
        List all authenticated environments.

        Returns:
            List of dicts with url, email, is_current keys.
        """
        current = self.api_url
        result = []
        for url, env in self._data.get("environments", {}).items():
            if env.get("token"):
                result.append({
                    "url": url,
                    "email": env.get("email"),
                    "is_current": url == current,
                })
        return result

    # Backwards compatibility - clear() still works
    def clear(self):
        """Clear current environment credentials (backwards compat)."""
        self.clear_environment()
