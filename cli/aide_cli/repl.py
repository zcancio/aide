"""REPL for AIde CLI."""
import webbrowser

from aide_cli.client import ApiClient
from aide_cli.config import Config


class Repl:
    """Interactive REPL for AIde."""

    def __init__(self, config: Config, aide_id: str | None = None):
        self.config = config
        self.client = ApiClient(config.api_url, config.token)
        self.current_aide_id = aide_id or config.default_aide_id
        self.current_aide = None
        self.running = True

    def start(self):
        """Start the REPL."""
        # Load current aide if ID is set
        if self.current_aide_id:
            try:
                self.current_aide = self.client.get(f"/api/aides/{self.current_aide_id}")
                print(f"aide > {self.current_aide['name']}")
            except Exception as e:
                print(f"Failed to load aide: {e}")
                self.current_aide_id = None
                self.current_aide = None

        # If no aide, prompt to create one
        if not self.current_aide:
            print("aide > New aide. Say what you're running.")

        # REPL loop
        while self.running:
            try:
                line = input("aide > ").strip()

                if not line:
                    continue

                # Handle commands
                if line.startswith("/"):
                    self._handle_command(line)
                else:
                    # Send message
                    self._send_message(line)

            except (EOFError, KeyboardInterrupt):
                print()
                break
            except Exception as e:
                print(f"Error: {e}")

        self.client.close()

    def _handle_command(self, line: str):
        """Handle REPL commands."""
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None

        if cmd == "/quit":
            self.running = False
            print("Goodbye.")
        elif cmd == "/list":
            self._list_aides()
        elif cmd == "/switch":
            if arg:
                self._switch_aide(arg)
            else:
                print("Usage: /switch <number>")
        elif cmd == "/new":
            self._new_aide()
        elif cmd == "/page":
            self._open_page()
        elif cmd == "/info":
            self._show_info()
        elif cmd == "/history":
            n = int(arg) if arg else 10
            self._show_history(n)
        elif cmd == "/help":
            self._show_help()
        else:
            print(f"Unknown command: {cmd}")
            print("Type /help for available commands.")

    def _send_message(self, text: str):
        """Send a message to current aide."""
        if not self.current_aide:
            # Create new aide with first message
            try:
                data = {"title": text[:50]}
                aide = self.client.post("/api/aides", data)
                self.current_aide_id = aide["id"]
                self.current_aide = aide
                self.config.default_aide_id = aide["id"]
            except Exception as e:
                print(f"Failed to create aide: {e}")
                return

        # Send message
        try:
            # Note: This is a simplified version. The real implementation would
            # need to handle WebSocket streaming or polling for responses.
            # For now, we just send the message and show a placeholder response.
            data = {"aide_id": self.current_aide_id, "message": text}
            self.client.post("/api/message", data)
            print("  Message sent. (Note: streaming not yet implemented in CLI)")
        except Exception as e:
            print(f"Failed to send message: {e}")

    def _list_aides(self):
        """List all aides."""
        try:
            aides = self.client.get("/api/aides")
            if not aides:
                print("  No aides yet. Start chatting to create one.")
                return

            print("  Aides:")
            for i, aide in enumerate(aides[:10], 1):
                title = aide.get("title", "Untitled")
                # TODO: Add last activity timestamp when available
                print(f"  {i}. {title}")

        except Exception as e:
            print(f"Failed to list aides: {e}")

    def _switch_aide(self, index: str):
        """Switch to a different aide."""
        try:
            idx = int(index) - 1
            aides = self.client.get("/api/aides")

            if 0 <= idx < len(aides):
                aide = aides[idx]
                self.current_aide_id = aide["id"]
                self.current_aide = aide
                self.config.default_aide_id = aide["id"]
                print(f"  Switched to: {aide.get('title', 'Untitled')}")
            else:
                print("  Invalid index. Use /list to see aides.")

        except ValueError:
            print("  Invalid number.")
        except Exception as e:
            print(f"Failed to switch aide: {e}")

    def _new_aide(self):
        """Start a new aide."""
        self.current_aide_id = None
        self.current_aide = None
        self.config.default_aide_id = None
        print("  New aide started. Say what you're running.")

    def _open_page(self):
        """Open published page in browser."""
        if not self.current_aide:
            print("  No current aide.")
            return

        # Get published slug
        try:
            aide = self.client.get(f"/api/aides/{self.current_aide_id}")
            slug = aide.get("published_slug")

            if not slug:
                print("  This aide is not published yet.")
                return

            url = f"{self.config.api_url}/s/{slug}"
            print(f"  Opening {url}")
            webbrowser.open(url)

        except Exception as e:
            print(f"Failed to open page: {e}")

    def _show_info(self):
        """Show current aide details."""
        if not self.current_aide:
            print("  No current aide.")
            return

        try:
            aide = self.client.get(f"/api/aides/{self.current_aide_id}")
            name = aide.get("title", "Untitled")
            created = aide.get("created_at", "Unknown")
            slug = aide.get("published_slug")

            print(f"  Name: {name}")
            print(f"  Created: {created}")
            if slug:
                print(f"  Published: {self.config.api_url}/s/{slug}")

        except Exception as e:
            print(f"Failed to get aide info: {e}")

    def _show_history(self, n: int):
        """Show message history."""
        if not self.current_aide:
            print("  No current aide.")
            return

        # TODO: Implement when message history endpoint is available
        print("  (Message history not yet implemented)")

    def _show_help(self):
        """Show help message."""
        print("""
  REPL Commands:
    /list          - Show all aides
    /switch <n>    - Switch to aide number <n>
    /new           - Start a new aide
    /page          - Open published page in browser
    /info          - Show current aide details
    /history [n]   - Show last n messages (default 10)
    /help          - Show this help
    /quit          - Exit REPL
""")
