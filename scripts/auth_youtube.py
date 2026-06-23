"""One-time YouTube OAuth2 setup. Run this once in the Replit shell."""

import os
import pickle
from pathlib import Path


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds_dir = Path(__file__).parent.parent / "credentials"
    token_path = creds_dir / "token.pickle"
    secrets_file = creds_dir / "client_secrets.json"

    if not secrets_file.exists():
        print(f"ERROR: {secrets_file} not found.")
        print("Upload your client_secrets.json to the credentials/ folder first.")
        return

    creds = None
    if token_path.exists():
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.valid:
        print("Already authenticated! Token is valid.")
        return

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        print("Token refreshed successfully.")
    else:
        print("\n=== YouTube Authorization ===")
        print("A URL will appear below. Open it in your browser, log in with")
        print("your YouTube Google account, then paste the code back here.\n")
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), SCOPES)
        creds = flow.run_console()

    creds_dir.mkdir(parents=True, exist_ok=True)
    with open(token_path, "wb") as f:
        pickle.dump(creds, f)
    print(f"\nSuccess! Token saved to {token_path}")
    print("Your YouTube channel is now connected. Videos will upload automatically.")


if __name__ == "__main__":
    main()
