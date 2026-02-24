"""One-time LinkedIn OAuth setup — run this to generate an access token.

Usage:
    uv run python linkedin_oauth_setup.py

This will:
1. Open a browser for LinkedIn login and consent
2. Exchange the auth code for an access token
3. Fetch your Person URN
4. Update the .env file with the real token and URN
"""

import http.server
import os
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:9876/callback"
SCOPES = "openid profile email w_member_social"

ENV_FILE = Path(__file__).parent / ".env"

auth_code = None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler to capture the OAuth callback."""

    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>LinkedIn OAuth complete!</h2>"
                b"<p>You can close this tab and return to the terminal.</p></body></html>"
            )
        elif "error" in params:
            error = params.get("error", ["unknown"])[0]
            desc = params.get("error_description", [""])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>Error: {error}</h2><p>{desc}</p></body></html>".encode())
            print(f"\nERROR from LinkedIn: {error} — {desc}")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logs


def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for access token."""
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"Token exchange failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    return resp.json()


def get_user_info(access_token: str) -> dict:
    """Fetch LinkedIn user info."""
    resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"Failed to fetch user info: {resp.status_code} {resp.text}")
        return {}
    return resp.json()


def update_env(access_token: str, person_urn: str):
    """Update .env file with the new token and URN."""
    if not ENV_FILE.exists():
        print(f".env not found at {ENV_FILE}")
        return

    content = ENV_FILE.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines = []
    found_token = False
    found_urn = False

    for line in lines:
        if line.startswith("LINKEDIN_ACCESS_TOKEN="):
            new_lines.append(f"LINKEDIN_ACCESS_TOKEN={access_token}")
            found_token = True
        elif line.startswith("LINKEDIN_PERSON_URN="):
            new_lines.append(f"LINKEDIN_PERSON_URN={person_urn}")
            found_urn = True
        elif line.startswith("LINKEDIN_CLIENT_ID=") or line.startswith("LINKEDIN_CLIENT_SECRET="):
            new_lines.append(line)
        else:
            new_lines.append(line)

    if not found_token:
        new_lines.append(f"LINKEDIN_ACCESS_TOKEN={access_token}")
    if not found_urn:
        new_lines.append(f"LINKEDIN_PERSON_URN={person_urn}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f".env updated at {ENV_FILE}")


def main():
    # Step 1: Build authorization URL
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        })
    )

    # Step 2: Start local callback server
    server = http.server.HTTPServer(("localhost", 9876), CallbackHandler)

    print("Opening browser for LinkedIn login...")
    print(f"If the browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Step 3: Wait for callback
    print("Waiting for LinkedIn callback...")
    while auth_code is None:
        server.handle_request()

    server.server_close()
    print(f"Authorization code received.")

    # Step 4: Exchange code for token
    print("\nExchanging code for access token...")
    token_data = exchange_code_for_token(auth_code)

    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", "unknown")
    print(f"  Access token: {access_token[:20]}...")
    print(f"  Expires in: {expires_in} seconds ({int(expires_in) // 86400} days)" if isinstance(expires_in, int) else f"  Expires in: {expires_in}")

    # Step 5: Get user info and person URN
    print("\nFetching user profile...")
    user_info = get_user_info(access_token)
    name = user_info.get("name", "Unknown")
    email = user_info.get("email", "Unknown")
    sub = user_info.get("sub", "")
    person_urn = f"urn:li:person:{sub}" if sub else ""

    print(f"  Name: {name}")
    print(f"  Email: {email}")
    print(f"  Person URN: {person_urn}")

    # Step 6: Update .env
    if access_token and person_urn:
        print("\nUpdating .env...")
        update_env(access_token, person_urn)
        print("\nLinkedIn OAuth setup complete!")
        print(f"Token expires in ~{int(expires_in) // 86400} days — you'll need to re-run this script before then.")
    else:
        print("\nWARNING: Could not get person URN. Saving token only.")
        if access_token:
            update_env(access_token, person_urn or "UNKNOWN")


if __name__ == "__main__":
    main()
