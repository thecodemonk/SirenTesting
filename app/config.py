import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError('SECRET_KEY environment variable is required')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "instance", "sirentracker.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_WORKSPACE_DOMAIN = os.environ.get('GOOGLE_WORKSPACE_DOMAIN')

    GMAIL_SENDER = os.environ.get('GMAIL_SENDER', '')

    RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY', '')
    RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')

    MEDIA_FOLDER = os.path.join(BASE_DIR, 'media', 'photos')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    # NWS active-alerts feed (Storm Center). No API key; User-Agent required.
    # NWS_ZONE is a county/zone UGC code — St. Clair County, MI is MIC147.
    NWS_ZONE = os.environ.get('NWS_ZONE', 'MIC147')
    NWS_USER_AGENT = os.environ.get('NWS_USER_AGENT', '(sccarpsc.org, noreply@sccarpsc.org)')

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    TIMEZONE = 'America/New_York'

    MAGIC_LINK_EXPIRY = 600  # 10 minutes
    MAGIC_LINK_SALT = 'member-auth'
    DOLLAR_VALUE_PER_HOUR = 34.79
    INACTIVITY_THRESHOLD_DAYS = 365


class DevConfig(BaseConfig):
    DEBUG = True


class ProdConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestConfig(BaseConfig):
    SECRET_KEY = 'testing-only'
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
