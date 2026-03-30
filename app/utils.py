from datetime import date, timedelta
from flask import current_app
from .extensions import db
from .models import Test, Assignment


def get_siren_status(siren, year=None):
    """Compute runtime status for a siren. Returns one of:
    failed, overdue, flagged, assigned, passed, untested."""
    if year is None:
        year = date.today().year

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    today = date.today()

    # Most recent test this year
    latest_test = (
        Test.query
        .filter_by(siren_id=siren.id)
        .filter(Test.test_date.between(year_start, year_end))
        .order_by(Test.test_date.desc())
        .first()
    )

    if latest_test and not latest_test.passed:
        return 'failed'

    if latest_test and latest_test.passed:
        return 'passed'

    # No test this year — check if overdue (no test at all in over 12 months)
    last_test_ever = (
        Test.query
        .filter_by(siren_id=siren.id)
        .order_by(Test.test_date.desc())
        .first()
    )
    if last_test_ever is None or last_test_ever.test_date < today - timedelta(days=365):
        return 'overdue'

    # Manually flagged for recheck
    if siren.needs_retest:
        return 'flagged'

    # Check for CLAIMED assignment for upcoming test
    has_assignment = (
        Assignment.query
        .filter_by(siren_id=siren.id, status='CLAIMED')
        .filter(Assignment.test_date >= today)
        .first()
    )
    if has_assignment:
        return 'assigned'

    return 'untested'


def get_all_siren_statuses(sirens, year=None):
    """Compute statuses for a list of sirens. Returns dict of siren.id -> status."""
    return {siren.id: get_siren_status(siren, year) for siren in sirens}


def notify_admins(subject, body):
    """Send email notification to all admin users. Fire-and-forget."""
    from .models import AdminUser
    from .gmail import send_email
    try:
        admins = AdminUser.query.all()
        recipients = [a.email for a in admins if a.email]
        if not recipients:
            return
        send_email(subject, body, recipients)
    except Exception as e:
        current_app.logger.error(f'Failed to send admin notification: {e}')


def generate_first_mondays(year):
    """Generate first Monday of each month for a given year."""
    dates = []
    for month in range(1, 13):
        d = date(year, month, 1)
        # Monday is weekday 0
        days_ahead = 0 - d.weekday()
        if days_ahead < 0:
            days_ahead += 7
        first_monday = d + timedelta(days=days_ahead)
        dates.append(first_monday)
    return dates
