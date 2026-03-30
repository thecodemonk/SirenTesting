#!/usr/bin/env python3
"""One-time script to authorize Gmail API access.

Run this locally (not on the server) — it opens a browser for Google sign-in.
After authorizing, it saves a refresh token to instance/gmail_token.json.
Copy that file to the server's instance/ directory.

Usage:
    python scripts/gmail_auth.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_PATH = os.path.join('instance', 'gmail_token.json')


def main():
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if not client_id or not client_secret:
        print('Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env')
        sys.exit(1)

    # Build client config from env vars (no separate client_secrets.json needed)
    client_config = {
        'installed': {
            'client_id': client_id,
            'client_secret': client_secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': ['http://localhost'],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8090)

    os.makedirs('instance', exist_ok=True)
    with open(TOKEN_PATH, 'w') as f:
        f.write(creds.to_json())

    print(f'Authorization successful! Token saved to {TOKEN_PATH}')
    print(f'Sign-in account: this token will send email as whatever account you just authorized.')
    print()
    print('For deployment, copy instance/gmail_token.json to the server.')


if __name__ == '__main__':
    main()
