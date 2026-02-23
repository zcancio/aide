"""Main entry point for AIde CLI."""
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
  aide login               - Authenticate with device flow
  aide logout              - Logout and clear credentials
  aide [--aide <id>]       - Start REPL (optionally with specific aide)
  aide --help              - Show this help
  aide --version           - Show version

REPL Commands:
  /list                    - Show all aides
  /switch <n>              - Switch to aide
  /new                     - Start new aide
  /page                    - Open published page
  /info                    - Show current aide details
  /history [n]             - Show message history
  /view                    - Render current state as text
  /watch [on|off]          - Auto-render after each message
  /help                    - Show REPL help
  /quit                    - Exit REPL
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


def main():
    """Main entry point."""
    config = Config()

    # Parse args
    args = sys.argv[1:]

    if not args:
        # No args - start REPL
        if not config.is_authenticated:
            print("Not authenticated. Run 'aide login' first.")
            sys.exit(1)

        # Initialize Node bridge for text rendering
        bridge = init_bridge(config)

        repl = Repl(config, bridge=bridge)
        try:
            repl.start()
        finally:
            if bridge:
                bridge.stop()
        return

    cmd = args[0]

    if cmd == "login":
        success = login(config)
        sys.exit(0 if success else 1)

    elif cmd == "logout":
        success = logout(config)
        sys.exit(0 if success else 1)

    elif cmd == "--help" or cmd == "-h":
        print_help()
        return

    elif cmd == "--version" or cmd == "-v":
        print(f"aide-cli {__version__}")
        return

    elif cmd == "--aide":
        if len(args) < 2:
            print("Error: --aide requires an aide ID")
            sys.exit(1)

        if not config.is_authenticated:
            print("Not authenticated. Run 'aide login' first.")
            sys.exit(1)

        # Initialize Node bridge for text rendering
        bridge = init_bridge(config)

        aide_id = args[1]
        repl = Repl(config, aide_id=aide_id, bridge=bridge)
        try:
            repl.start()
        finally:
            if bridge:
                bridge.stop()
        return

    else:
        print(f"Unknown command: {cmd}")
        print("Run 'aide --help' for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
