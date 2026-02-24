"""One-time Gmail OAuth setup — run this to generate token.json.

Usage:
    uv run python gmail_oauth_setup.py

This will:
1. Read your credentials.json from Secrets/
2. Open a browser for Google login and consent
3. Save the refresh token to Secrets/token.json
4. Verify the token works by fetching your Gmail profile
"""

import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail scopes:
#   gmail.readonly  — watching inbox for new emails
#   gmail.send      — sending emails
#   gmail.compose   — creating drafts
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]

SECRETS_DIR = Path(__file__).parent / "Secrets"
CREDENTIALS_FILE = SECRETS_DIR / "gmail_credentials.json"
TOKEN_FILE = SECRETS_DIR / "token.json"


def main():
    if not CREDENTIALS_FILE.exists():
        print(f"ERROR: credentials file not found at {CREDENTIALS_FILE}")
        print("Download it from Google Cloud Console > APIs & Services > Credentials")
        sys.exit(1)

    creds = None

    # Check for existing token
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds and creds.valid:
            print(f"token.json already exists and is valid: {TOKEN_FILE}")
            _verify(creds)
            return
        if creds and creds.expired and creds.refresh_token:
            print("Token expired, refreshing...")
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            print(f"Token refreshed and saved to {TOKEN_FILE}")
            _verify(creds)
            return

    # Run the OAuth consent flow
    print("Starting OAuth consent flow...")
    print("A browser window will open — log in with the Google account you want to monitor.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    # Save the token
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"\ntoken.json saved to {TOKEN_FILE}")

    _verify(creds)


def _verify(creds: Credentials):
    """Verify the token works by fetching Gmail profile."""
    print("\nVerifying token...")
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    print(f"  Email: {profile['emailAddress']}")
    print(f"  Total messages: {profile['messagesTotal']}")
    print(f"  Threads: {profile['threadsTotal']}")
    print("\nGmail OAuth setup complete! The Gmail watcher and Email MCP server are ready.")


if __name__ == "__main__":
    main()
