from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user
from ..models import Member


def member_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, Member):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('members.login'))
        return f(*args, **kwargs)
    return decorated_function


def siren_editor_required(f):
    """Require an authenticated member with the can_edit_sirens permission."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, Member):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('members.login'))
        if not current_user.can_edit_sirens:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
