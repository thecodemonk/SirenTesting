import base64
import json
import os
from email.mime.text import MIMEText

from flask import current_app
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'gmail_token.json')
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def _get_credentials():
    """Load and refresh Gmail OAuth credentials from the stored token."""
    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError(
            f'Gmail token not found at {TOKEN_PATH}. '
            'Run: python scripts/gmail_auth.py'
        )

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())

    return creds


def send_email(subject, body, recipients):
    """Send an email via Gmail API. recipients is a list of email addresses."""
    creds = _get_credentials()
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)

    sender = current_app.config.get('GMAIL_SENDER', '')

    message = MIMEText(body)
    message['to'] = ', '.join(recipients)
    message['from'] = sender
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
