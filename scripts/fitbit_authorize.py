#!/usr/bin/env python3
"""
Re-authorize Fitbit OAuth token.
Run inside the scrapers-runner container:
  docker exec -it scrapers-runner python3 /app/scripts/fitbit_authorize.py
"""
import os
import sys
import json
import time
import base64
import urllib.parse
import http.server
import requests

CLIENT_ID = os.getenv("FITBIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET")
TOKEN_FILE = os.getenv("TOKEN_FILE", "/app/fitbit.json")
REDIRECT_URI = "http://localhost:8080"
SCOPES = "heartrate activity cardio_fitness settings profile"

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: FITBIT_CLIENT_ID and FITBIT_CLIENT_SECRET must be set.", file=sys.stderr)
    sys.exit(1)

auth_code = None

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Authorized! You can close this tab.</h1>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Error: no code received</h1>")

    def log_message(self, format, *args):
        pass

auth_url = (
    "https://www.fitbit.com/oauth2/authorize"
    f"?response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPES)}"
    f"&expires_in=604800"
)

print("\n==========================================================")
print("Open this URL in your browser to authorize Fitbit access:")
print("==========================================================")
print(auth_url)
print("==========================================================\n")
print("Waiting for OAuth callback on port 8080...")

server = http.server.HTTPServer(("0.0.0.0", 8080), CallbackHandler)
server.timeout = 300

while auth_code is None:
    server.handle_request()

server.server_close()
print("Got auth code, exchanging for token...")

credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
r = requests.post(
    "https://api.fitbit.com/oauth2/token",
    headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    },
    data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
    },
    timeout=30,
)

if r.status_code != 200:
    print(f"Token exchange failed: {r.status_code} {r.text}", file=sys.stderr)
    sys.exit(1)

j = r.json()
token_data = {
    "access_token": j["access_token"],
    "refresh_token": j["refresh_token"],
    "expires_at": int(time.time()) + j.get("expires_in", 28800),
}

with open(TOKEN_FILE, "w") as f:
    json.dump(token_data, f, indent=2)

print(f"Token saved to {TOKEN_FILE}")
print("Authorization complete.")
