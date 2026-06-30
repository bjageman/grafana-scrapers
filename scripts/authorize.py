#!/usr/bin/env python3
import os
import sys
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.location.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.read'
]

def main():
    # If variables are not set in environment, try to read them from env file or console
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables must be set.", file=sys.stderr)
        print("You can run it like: GOOGLE_CLIENT_ID=xxx GOOGLE_CLIENT_SECRET=yyy python3 authorize.py", file=sys.stderr)
        sys.exit(1)
        
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    
    # We create the tokens folder if not exists
    os.makedirs("/app/tokens", exist_ok=True)
    
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    
    print("\n=========================================================================")
    print("Please open the following authorization URL in your web browser:")
    print("=========================================================================\n")
    
    # Run the local server flow but do not open the browser automatically
    # Bind to 0.0.0.0 on port 8080 (or AUTH_PORT) so it works when mapped/forwarded from outside the container
    auth_port = int(os.getenv("AUTH_PORT", "8080"))
    creds = flow.run_local_server(
        host='localhost',
        port=auth_port,
        bind_addr='0.0.0.0',
        open_browser=False
    )
    
    token_data = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    
    token_file = "/app/tokens/google_token.json"
    with open(token_file, "w") as f:
        json.dump(token_data, f, indent=2)
        
    print("\n=========================================================================")
    print(f"Successfully authorized and saved credentials to {token_file}!")
    print("=========================================================================\n")

if __name__ == "__main__":
    main()
