"""Authentication flow for AIde CLI."""
import secrets
import string
import time
import webbrowser

from aide_cli.client import ApiClient
from aide_cli.config import Config


def generate_device_code(length: int = 6) -> str:
    """Generate a random device code."""
    chars = string.ascii_uppercase + string.digits
    # Exclude ambiguous characters
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(chars) for _ in range(length))


def login(config: Config) -> bool:
    """
    Perform device authorization flow.

    Returns True if successful, False otherwise.
    """
    device_code = generate_device_code()
    client = ApiClient(config.api_url)

    try:
        # Start auth flow
        print("Starting device authorization...")
        start_res = client.post(
            "/api/cli/auth/start", {"device_code": device_code}
        )

        auth_url = start_res["auth_url"]
        print(f"\nOpening browser: {auth_url}")
        print(f"Device code: {device_code}")

        # Open browser
        webbrowser.open(auth_url)

        # Poll for approval
        print("Waiting for authorization...", end="", flush=True)
        max_polls = 150  # 5 minutes at 2s intervals
        poll_count = 0

        while poll_count < max_polls:
            time.sleep(2)
            poll_count += 1

            try:
                poll_res = client.post(
                    "/api/cli/auth/poll", {"device_code": device_code}
                )

                status = poll_res["status"]

                if status == "approved":
                    token = poll_res["token"]
                    config.token = token

                    # Get user info
                    client.token = token
                    user = client.get("/auth/me")
                    config.email = user["email"]

                    print(" done")
                    print(f"Authenticated as {user['email']}")
                    print(f"Token saved to {config.config_file}")
                    return True

                elif status == "expired":
                    print(" expired")
                    print("Device code expired. Please try again.")
                    return False

                # Still pending, keep polling
                print(".", end="", flush=True)

            except Exception as e:
                print(f"\nPoll error: {e}")
                continue

        print(" timeout")
        print("Authorization timed out. Please try again.")
        return False

    except Exception as e:
        print(f"\nLogin failed: {e}")
        return False
    finally:
        client.close()


def logout(config: Config) -> bool:
    """
    Logout and revoke token.

    Returns True if successful, False otherwise.
    """
    if not config.is_authenticated:
        print("Not logged in.")
        return False

    try:
        # Note: We don't have a way to revoke the token from the CLI
        # without knowing the token_id. For now, just clear local config.
        # The token will expire after 90 days.
        config.clear()
        print("Logged out successfully.")
        return True

    except Exception as e:
        print(f"Logout failed: {e}")
        return False
