"""Node bridge for running engine.js from Python CLI."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class NodeBridge:
    """Manages long-lived Node child process for engine operations."""

    def __init__(self):
        self.process = None
        self._id = 0

    def start(self):
        """Spawn Node process. Called once on CLI startup."""
        bridge_path = Path(__file__).parent / "bridge.js"
        engine_path = Path.home() / ".aide" / "engine.js"

        if not engine_path.exists():
            raise RuntimeError(
                "Engine not found. Run `aide login` or check network. "
                f"Expected at: {engine_path}"
            )

        # Check if Node is available
        try:
            subprocess.run(
                ["node", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            raise RuntimeError(
                "Node.js not found. Please install Node.js 18+ from https://nodejs.org"
            ) from e

        try:
            self.process = subprocess.Popen(
                ["node", str(bridge_path), str(engine_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Wait for ready signal
            line = self.process.stdout.readline()
            if not line:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                raise RuntimeError(f"Node bridge failed to start. stderr: {stderr}")

            msg = json.loads(line)
            if not msg.get("ready"):
                raise RuntimeError("Node bridge failed to send ready signal")

        except Exception as e:
            if self.process:
                self.process.kill()
                self.process = None
            raise RuntimeError(f"Failed to start Node bridge: {e}") from e

    def call(self, method: str, params: dict) -> Any:
        """Send JSON-RPC call, return result."""
        if not self.process:
            raise RuntimeError("Node bridge not started")

        self._id += 1
        request = json.dumps({"id": self._id, "method": method, "params": params})

        try:
            self.process.stdin.write(request + "\n")
            self.process.stdin.flush()

            line = self.process.stdout.readline()
            if not line:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                raise RuntimeError(f"Node bridge died. stderr: {stderr}")

            response = json.loads(line)

            if "error" in response:
                raise RuntimeError(f"Node bridge error: {response['error']}")

            return response["result"]

        except (BrokenPipeError, OSError) as e:
            # Bridge crashed, try to restart
            self.stop()
            raise RuntimeError(f"Node bridge communication failed: {e}") from e

    def render_text(self, snapshot: dict) -> str:
        """Render snapshot as unicode text."""
        return self.call("renderText", {"snapshot": snapshot})

    def reduce(self, snapshot: dict, event: dict) -> dict:
        """Apply an event to a snapshot."""
        return self.call("reduce", {"snapshot": snapshot, "event": event})

    def ping(self) -> str:
        """Ping the bridge to check if it's alive."""
        return self.call("ping", {})

    def stop(self):
        """Kill Node process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            finally:
                self.process = None

    def __del__(self):
        """Cleanup on destruction."""
        self.stop()
