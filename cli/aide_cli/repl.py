"""REPL for AIde CLI."""

import webbrowser

from aide_cli.client import ApiClient
from aide_cli.config import Config
from aide_cli.node_bridge import NodeBridge


class Repl:
    """Interactive REPL for AIde."""

    def __init__(self, config: Config, aide_id: str | None = None, bridge: NodeBridge | None = None):
        self.config = config
        self.client = ApiClient(config.api_url, config.token)
        self.current_aide_id = aide_id or config.default_aide_id
        self.current_aide = None
        self.running = True
        self.watch_mode = False
        self.bridge = bridge

    def start(self):
        """Start the REPL."""
        # Load current aide if ID is set
        if self.current_aide_id:
            try:
                self.current_aide = self.client.get(f"/api/aides/{self.current_aide_id}")
                print(f"aide > {self.current_aide['title']}")
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
                    # Send message with streaming
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
            n = int(arg) if arg else 20
            self._show_history(n)
        elif cmd == "/view":
            self._view_state()
        elif cmd == "/watch":
            if arg and arg.lower() in ["on", "off"]:
                self._toggle_watch(arg.lower() == "on")
            else:
                self._toggle_watch(not self.watch_mode)
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
            result = self.client.send_message(self.current_aide_id, text)
            response_text = result.get("response_text", "")
            print(f"  \033[32maide:\033[0m {response_text}")

            # If watch mode is on, render the state
            if self.watch_mode and self.bridge:
                self._render_state_after_message()

        except KeyboardInterrupt:
            print()  # Clean newline on interrupt
            print("  (Interrupted)")
        except Exception as e:
            print(f"  Error: {e}")

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
            slug = aide.get("slug")

            if not slug or aide.get("status") != "published":
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
            title = aide.get("title", "Untitled")
            created = aide.get("created_at", "Unknown")
            slug = aide.get("slug")
            status = aide.get("status", "draft")

            print(f"  Title: {title}")
            print(f"  Status: {status}")
            print(f"  Created: {created}")
            if slug and status == "published":
                print(f"  Published: {self.config.api_url}/s/{slug}")

        except Exception as e:
            print(f"Failed to get aide info: {e}")

    def _show_history(self, n: int):
        """Show message history."""
        if not self.current_aide:
            print("  No current aide.")
            return

        try:
            response = self.client.get(f"/api/aides/{self.current_aide_id}/history")
            messages = response.get("messages", [])

            if not messages:
                print("  No conversation history.")
                return

            # Show last n messages
            recent = messages[-n:]

            for i, msg in enumerate(recent):
                role = msg.get("role")
                content = msg.get("content", "")

                if role == "user":
                    prefix = "\033[90myou:\033[0m"  # Dim
                elif role == "assistant":
                    prefix = "\033[32maide:\033[0m"  # Green
                else:
                    continue  # Skip system messages

                print(f"  {prefix} {content}")

                # Blank line after assistant messages (end of exchange)
                if role == "assistant" and i < len(recent) - 1:
                    print()

        except Exception as e:
            print(f"Failed to get history: {e}")

    def _view_state(self):
        """Render current aide state as text."""
        if not self.current_aide:
            print("  No current aide.")
            return

        if not self.bridge:
            print("  Text rendering unavailable. Engine not loaded.")
            return

        try:
            # Fetch aide with snapshot
            aide = self.client.get(f"/api/aides/{self.current_aide_id}", params={"include_snapshot": "true"})
            snapshot = aide.get("snapshot")

            if not snapshot:
                print("  No state yet.")
                return

            # Render via Node bridge
            text = self.bridge.render_text(snapshot)
            print()
            print(text)
            print()

        except Exception as e:
            print(f"Failed to render state: {e}")

    def _toggle_watch(self, enable: bool):
        """Toggle watch mode."""
        self.watch_mode = enable

        if enable:
            print("  Watch mode: showing state after each message.")
        else:
            print("  Watch mode: off.")

    def _render_state_after_message(self):
        """Render state after a message (used in watch mode)."""
        if not self.bridge or not self.current_aide_id:
            return

        try:
            # Add separator
            print()
            print("  " + "┄" * 50)
            print()

            # Fetch and render
            aide = self.client.get(f"/api/aides/{self.current_aide_id}", params={"include_snapshot": "true"})
            snapshot = aide.get("snapshot")

            if snapshot:
                text = self.bridge.render_text(snapshot)
                # Indent the rendered text
                for line in text.split("\n"):
                    print(f"  {line}")
            print()

        except Exception as e:
            print(f"  (Failed to render state: {e})")

    def _show_help(self):
        """Show help message."""
        print("""
  REPL Commands:
    /list          - Show all aides
    /switch <n>    - Switch to aide number <n>
    /new           - Start a new aide
    /page          - Open published page in browser
    /info          - Show current aide details
    /history [n]   - Show last n messages (default 20)
    /view          - Render current state in terminal
    /watch [on|off]- Auto-render state after each message
    /help          - Show this help
    /quit          - Exit REPL
""")
