"""Main entry point for AIde CLI."""
from __future__ import annotations

import subprocess
import sys

from aide_cli import __version__
from aide_cli.auth import login, logout
from aide_cli.client import ApiClient
from aide_cli.config import Config
from aide_cli.node_bridge import NodeBridge
from aide_cli.repl import Repl


def print_help():
    """Print help message."""
    print(f"""
AIde CLI v{__version__}

Usage:
  aide [options] [command]

Commands:
  login             Authenticate via browser
  logout            Revoke token and clear config

Options:
  --api-url URL     Override API endpoint (default: https://get.toaide.com)
  --aide ID         Start REPL with specific aide
  -h, --help        Show this help
  -v, --version     Show version

Environment:
  AIDE_API_URL      Override API endpoint (same as --api-url)

Examples:
  aide login                                    # Login to production
  aide login --api-url http://localhost:8000    # Login to local dev
  aide logout                                   # Logout current environment
  aide logout --all                             # Logout all environments

REPL Commands:
  /list             Show all aides
  /switch <n>       Switch to aide
  /new              Start new aide
  /page             Open published page
  /info             Show current aide details
  /history [n]      Show message history
  /view             Render current state as text
  /watch [on|off]   Auto-render after each message
  /help             Show REPL help
  /quit             Exit REPL
""")


def check_node():
    """Check if Node.js is available."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version_str = result.stdout.strip().lstrip("v")
        major_version = int(version_str.split(".")[0])

        if major_version < 18:
            print(f"Warning: aide requires Node.js 18+. Current: {result.stdout.strip()}")
            print("Text rendering (/view, /watch) will be disabled.")
            return False

        return True

    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        print("Warning: Node.js not found. Install from https://nodejs.org")
        print("Text rendering (/view, /watch) will be disabled.")
        return False


def init_bridge(config: Config) -> NodeBridge | None:
    """Initialize Node bridge. Returns None if unavailable."""
    # Check Node availability
    if not check_node():
        return None

    # Fetch engine.js
    client = ApiClient(config.api_url, config.token)
    if not client.fetch_engine():
        return None

    # Start bridge
    try:
        bridge = NodeBridge()
        bridge.start()
        return bridge
    except Exception as e:
        print(f"  Warning: Failed to start Node bridge: {e}")
        print("  Text rendering (/view, /watch) will be disabled.")
        return None


def parse_args(args: list[str]) -> dict:
    """
    Parse command line arguments.

    Returns dict with:
        command: str | None (login, logout, None for REPL)
        api_url: str | None
        aide_id: str | None
        logout_all: bool
        show_help: bool
        show_version: bool
    """
    result = {
        "command": None,
        "api_url": None,
        "aide_id": None,
        "logout_all": False,
        "show_help": False,
        "show_version": False,
    }

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "login":
            result["command"] = "login"
        elif arg == "logout":
            result["command"] = "logout"
        elif arg == "--api-url":
            if i + 1 < len(args):
                result["api_url"] = args[i + 1]
                i += 1
            else:
                print("Error: --api-url requires a URL")
                sys.exit(1)
        elif arg == "--aide":
            if i + 1 < len(args):
                result["aide_id"] = args[i + 1]
                i += 1
            else:
                print("Error: --aide requires an ID")
                sys.exit(1)
        elif arg == "--all":
            result["logout_all"] = True
        elif arg in ("--help", "-h"):
            result["show_help"] = True
        elif arg in ("--version", "-v"):
            result["show_version"] = True
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}")
            print("Run 'aide --help' for usage.")
            sys.exit(1)
        else:
            # Unknown positional argument
            print(f"Unknown command: {arg}")
            print("Run 'aide --help' for usage.")
            sys.exit(1)

        i += 1

    return result


def main():
    """Main entry point."""
    args = parse_args(sys.argv[1:])

    # Handle help and version first
    if args["show_help"]:
        print_help()
        return

    if args["show_version"]:
        print(f"aide-cli {__version__}")
        return

    # Create config with optional api_url override
    config = Config(api_url_override=args["api_url"])

    # Handle commands
    if args["command"] == "login":
        success = login(config)
        sys.exit(0 if success else 1)

    elif args["command"] == "logout":
        success = logout(config, logout_all=args["logout_all"])
        sys.exit(0 if success else 1)

    else:
        # No command - start REPL
        if not config.is_authenticated:
            print(f"Not authenticated to {config.api_url}")
            print("Run 'aide login' first.")
            sys.exit(1)

        # Initialize Node bridge for text rendering
        bridge = init_bridge(config)

        repl = Repl(config, aide_id=args["aide_id"], bridge=bridge)
        try:
            repl.start()
        finally:
            if bridge:
                bridge.stop()


if __name__ == "__main__":
    main()
