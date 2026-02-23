"""Main entry point for AIde CLI."""
import sys

from aide_cli import __version__
from aide_cli.auth import login, logout
from aide_cli.config import Config
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
  /help                    - Show REPL help
  /quit                    - Exit REPL
""")


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

        repl = Repl(config)
        repl.start()
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

        aide_id = args[1]
        repl = Repl(config, aide_id=aide_id)
        repl.start()
        return

    else:
        print(f"Unknown command: {cmd}")
        print("Run 'aide --help' for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
