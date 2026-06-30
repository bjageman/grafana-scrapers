#!/usr/bin/env python3
"""
Standalone Fitbit token refresher.
Scheduled to run every 6 hours. Proactively refreshes the access token
when it is within 2 hours of expiry, so the main fitbit.py scraper
never encounters an expired token.
"""
import os
import sys
import json
import time
import requests

TOKEN_FILE = "/app/fitbit.json"
CLIENT_ID = os.getenv("FITBIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET")

# Refresh when fewer than this many seconds remain
REFRESH_THRESHOLD = 2 * 3600  # 2 hours


def read_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Could not read token file: {e}", file=sys.stderr)
        sys.exit(1)


def save_token(token_data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)


def refresh_token(refresh_tok):
    r = requests.post(
        "https://api.fitbit.com/oauth2/token",
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "refresh_token", "refresh_token": refresh_tok},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Fitbit token refresh failed: {r.status_code} {r.text}")
    j = r.json()
    return {
        "access_token": j["access_token"],
        "refresh_token": j["refresh_token"],
        "expires_at": int(time.time()) + j.get("expires_in", 28800),
    }


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: FITBIT_CLIENT_ID and FITBIT_CLIENT_SECRET must be set.", file=sys.stderr)
        sys.exit(1)

    token = read_token()
    now = int(time.time())
    expires_at = token.get("expires_at", 0)
    time_remaining = expires_at - now

    print(f"Token expires in {time_remaining // 3600}h {(time_remaining % 3600) // 60}m.")

    if time_remaining <= REFRESH_THRESHOLD:
        print("Within 2-hour refresh window — refreshing token...")
        try:
            new_token = refresh_token(token["refresh_token"])
            save_token(new_token)
            new_remaining = new_token["expires_at"] - int(time.time())
            print(f"Token refreshed successfully. New expiry in {new_remaining // 3600}h {(new_remaining % 3600) // 60}m.")
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Token is still fresh — no refresh needed.")


if __name__ == "__main__":
    main()
