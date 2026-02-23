"""Configuration management for AIde CLI."""
import json
from pathlib import Path


class Config:
    """Config manager for AIde CLI."""

    def __init__(self):
        self.config_dir = Path.home() / ".aide"
        self.config_file = self.config_dir / "config.json"
        self._data = {}
        self._load()

    def _load(self):
        """Load config from disk."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        """Save config to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def token(self) -> str | None:
        """Get API token."""
        return self._data.get("token")

    @token.setter
    def token(self, value: str):
        """Set API token."""
        self._data["token"] = value
        self._save()

    @property
    def email(self) -> str | None:
        """Get user email."""
        return self._data.get("email")

    @email.setter
    def email(self, value: str):
        """Set user email."""
        self._data["email"] = value
        self._save()

    @property
    def default_aide_id(self) -> str | None:
        """Get default aide ID."""
        return self._data.get("default_aide_id")

    @default_aide_id.setter
    def default_aide_id(self, value: str):
        """Set default aide ID."""
        self._data["default_aide_id"] = value
        self._save()

    @property
    def api_url(self) -> str:
        """Get API URL."""
        return self._data.get("api_url", "https://get.toaide.com")

    @api_url.setter
    def api_url(self, value: str):
        """Set API URL."""
        self._data["api_url"] = value
        self._save()

    def clear(self):
        """Clear all config."""
        self._data = {}
        if self.config_file.exists():
            self.config_file.unlink()

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return bool(self.token)
