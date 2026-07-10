from datetime import date


def status_class(status):
    """Map siren status to Bootstrap contextual class."""
    return {
        'failed': 'table-danger',
        'overdue': 'table-warning',
        'assigned': 'table-info',
        'flagged': 'table-info',
        'passed': 'table-success',
        'untested': '',
    }.get(status, '')


def format_date(value, fmt='%b %d, %Y'):
    """Format a date or datetime object."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return value.strftime(fmt)


def yesno(value):
    """Convert boolean to Yes/No/N/A."""
    if value is None:
        return 'N/A'
    return 'Yes' if value else 'No'


def status_badge(status):
    """Map siren status to badge CSS class name."""
    return {
        'failed': 'failed',
        'overdue': 'overdue',
        'assigned': 'assigned',
        'flagged': 'flagged',
        'passed': 'passed',
        'untested': 'untested',
    }.get(status, 'untested')


def training_status_badge(training):
    """Map training status to badge HTML."""
    status = training.status
    if status == 'expired':
        return 'bg-danger'
    elif status == 'expiring_soon':
        return 'bg-warning text-dark'
    return 'bg-success'


def alert_class(severity):
    """Map an NWS alert severity to a Bootstrap contextual class."""
    return {
        'Extreme': 'danger',
        'Severe': 'danger',
        'Moderate': 'warning',
        'Minor': 'info',
    }.get(severity, 'secondary')


def register_filters(app):
    app.jinja_env.filters['status_class'] = status_class
    app.jinja_env.filters['status_badge'] = status_badge
    app.jinja_env.filters['format_date'] = format_date
    app.jinja_env.filters['yesno'] = yesno
    app.jinja_env.filters['training_status_badge'] = training_status_badge
    app.jinja_env.filters['alert_class'] = alert_class
