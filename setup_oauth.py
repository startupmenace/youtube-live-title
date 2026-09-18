"""
YouTube OAuth Setup Script
===========================
Run this ONCE on your local machine to get a refresh token for Wasmer deployment.

STEPS:
  1. pip install google-auth-oauthlib google-api-python-client
  2. Place your client_secret.json next to this script
  3. Run: python setup_oauth.py
  4. A browser window opens — sign in and authorize
  5. Copy the REFRESH_TOKEN printed at the end
  6. Save it — you'll need it for Wasmer environment variables
"""

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CLIENT_SECRET_FILE = "client_secret.json"

def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit("Missing dependency. Run: pip install google-auth-oauthlib")

    import os
    if not os.path.exists(CLIENT_SECRET_FILE):
        sys.exit(
            f"Missing {CLIENT_SECRET_FILE}.\n"
            "Download it from Google Cloud Console:\n"
            "  APIs & Services > Credentials > your OAuth client > Download JSON\n"
            f"Save it as {CLIENT_SECRET_FILE} next to this script."
        )

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)

    print("Opening browser for authorization...")
    print("If the browser doesn't open, copy the URL below and open it manually.\n")

    creds = flow.run_local_server(port=8090, open_browser=True)

    print("\n" + "=" * 60)
    print("SUCCESS! Authorization complete.")
    print("=" * 60)
    print(f"\nYour REFRESH_TOKEN:\n\n{creds.refresh_token}\n")
    print("Save this token — you'll need it for Wasmer environment variables.")
    print("\nYou can also test the token by running:")
    print("  python youtube_live_title_updater.py --video-id YOUR_VIDEO_ID --once")

    # Save token for reference
    token_data = {
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
    }
    with open("refresh_token.json", "w") as f:
        json.dump(token_data, f, indent=2)
    print("\nFull token details saved to refresh_token.json")

if __name__ == "__main__":
    main()
