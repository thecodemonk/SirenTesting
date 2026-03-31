from flask import redirect, url_for, flash, session, current_app, request
from flask_login import login_user, logout_user
from . import auth_bp
from ..extensions import oauth, db, limiter
from ..models import AdminUser

google = None


def _get_google():
    global google
    if google is None:
        google = oauth.register(
            name='google',
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
    return google


@auth_bp.route('/login')
@limiter.limit("10/minute")
def login():
    google = _get_google()
    redirect_uri = url_for('auth.callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@auth_bp.route('/callback')
def callback():
    google = _get_google()
    token = google.authorize_access_token()
    userinfo = token.get('userinfo')
    if not userinfo:
        flash('Authentication failed.', 'danger')
        return redirect(url_for('public.dashboard'))

    email = userinfo.get('email', '')
    domain = email.split('@')[-1] if '@' in email else ''
    allowed_domain = current_app.config.get('GOOGLE_WORKSPACE_DOMAIN', '')

    if domain != allowed_domain:
        flash('Access restricted to organization members.', 'danger')
        return redirect(url_for('public.dashboard'))

    google_id = userinfo['sub']
    user = AdminUser.query.filter_by(google_id=google_id).first()
    if user is None:
        user = AdminUser(
            google_id=google_id,
            email=email,
            display_name=userinfo.get('name', email),
        )
        db.session.add(user)
    else:
        user.email = email
        user.display_name = userinfo.get('name', email)
    db.session.commit()

    login_user(user)
    flash('Logged in successfully.', 'success')
    return redirect(url_for('admin.sirens'))


@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('public.dashboard'))
