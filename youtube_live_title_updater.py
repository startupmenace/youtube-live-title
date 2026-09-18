"""
YouTube Live Title Updater — Wasmer Edge Edition
==================================================
Updates a YouTube video's title to show a live metric (view count).
Designed for headless deployment on Wasmer Edge with cron jobs.

SETUP (Wasmer Deployment)
  1. Create Google Cloud project + enable YouTube Data API v3
  2. Create OAuth 2.0 credentials (Desktop app type)
  3. Run setup_oauth.py locally to get your refresh token
  4. Deploy to Wasmer with environment variables:
     - VIDEO_ID: Your YouTube video ID
     - REFRESH_TOKEN: From setup_oauth.py output
     - CLIENT_SECRET_JSON: Contents of client_secret.json (as JSON string)
  5. Wasmer cron runs this every 10 minutes automatically

LOCAL TESTING
  python youtube_live_title_updater.py --video-id dQw4w9WgXcQ --once

QUOTA NOTE
  Each title edit costs 50 quota units; reading stats costs ~1 unit.
  At 10-minute intervals: ~7,344 units/day (within 10,000 default quota).
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("title-updater")


def get_credentials():
    """Get credentials from environment variables (Wasmer) or local files."""
    refresh_token = os.environ.get("REFRESH_TOKEN")
    client_secret_json = os.environ.get("CLIENT_SECRET_JSON")

    if refresh_token and client_secret_json:
        # Headless mode (Wasmer deployment)
        client_secrets = json.loads(client_secret_json)
        # Extract client_id and client_secret from the OAuth client config
        client_id = client_secrets.get("installed", {}).get("client_id") or \
                    client_secrets.get("web", {}).get("client_id")
        client_secret = client_secrets.get("installed", {}).get("client_secret") or \
                       client_secrets.get("web", {}).get("client_secret")

        if not client_id or not client_secret:
            sys.exit("CLIENT_SECRET_JSON missing client_id or client_secret")

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return creds
    else:
        # Local mode — use token.json / client_secret.json
        token_file = "token.json"
        client_secret_file = "client_secret.json"

        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(client_secret_file):
                    sys.exit(
                        f"Missing {client_secret_file}. Either:\n"
                        "  1. Run setup_oauth.py to get a refresh token, then set env vars, or\n"
                        "  2. Download client_secret.json from Google Cloud Console"
                    )
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        return creds


def get_view_count(youtube, video_id):
    """Read the view count for a video."""
    resp = youtube.videos().list(part="statistics", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(f"Video not found — check VIDEO_ID ({video_id}).")
    return int(items[0]["statistics"]["viewCount"])


def update_title(youtube, video_id, new_title):
    """Update a video's title. Returns True if changed."""
    resp = youtube.videos().list(part="snippet", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(f"Video not found — check VIDEO_ID ({video_id}).")
    snippet = items[0]["snippet"]
    if snippet.get("title") == new_title:
        return False
    snippet["title"] = new_title
    youtube.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}).execute()
    return True


def main():
    # Configuration from environment variables (Wasmer) or defaults
    video_id = os.environ.get("VIDEO_ID", "")
    template = os.environ.get("TITLE_TEMPLATE", "This YouTube video has exactly {count} views")

    if not video_id:
        # Check CLI args as fallback
        import argparse
        parser = argparse.ArgumentParser(description="Update YouTube video title with live view count.")
        parser.add_argument("--video-id", help="YouTube video ID")
        parser.add_argument("--template", default=template, help="Title template with {count} placeholder")
        parser.add_argument("--interval", type=int, default=600, help="Seconds between updates (default 600 = 10 min)")
        parser.add_argument("--once", action="store_true", help="Update once and exit")
        args = parser.parse_args()

        if args.video_id:
            video_id = args.video_id
        else:
            sys.exit("Set VIDEO_ID environment variable or use --video-id")

        template = args.template
        run_once = args.once
        interval = args.interval
    else:
        # Wasmer mode — run continuously (cron handles scheduling)
        run_once = True  # Cron triggers once per execution
        interval = 600

    log.info(f"Video ID: {video_id}")
    log.info(f"Template: {template}")

    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    while True:
        try:
            view_count = get_view_count(youtube, video_id)
            title = template.format(count=f"{view_count:,}")
            changed = update_title(youtube, video_id, title)
            timestamp = datetime.now(timezone.utc).isoformat()

            if changed:
                log.info(f"[{timestamp}] Updated title -> \"{title}\"")
            else:
                log.info(f"[{timestamp}] No change ({view_count} views); title already current.")
        except HttpError as e:
            log.error(f"YouTube API error: {e}")
            if e.resp.status == 403:
                log.error("Quota exceeded or API not enabled. Check Google Cloud Console.")
        except Exception as e:
            log.error(f"Error: {e}")

        if run_once:
            break

        time.sleep(interval)


if __name__ == "__main__":
    main()
