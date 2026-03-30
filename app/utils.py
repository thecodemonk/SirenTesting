import os
from datetime import date, timedelta

from flask import current_app
from PIL import Image
from .extensions import db
from .models import Test, Assignment

MAX_PHOTO_SIZE = (1200, 1200)
THUMB_SIZE = (200, 200)


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


def save_test_photo(file_storage, test_id):
    """Resize and save an uploaded test photo. Returns the filename."""
    folder = current_app.config['MEDIA_FOLDER']
    filename = f'test_{test_id}.jpg'
    thumb_filename = f'test_{test_id}_thumb.jpg'

    img = Image.open(file_storage)
    # Auto-rotate based on EXIF orientation
    img = _fix_orientation(img)
    # Convert to RGB (handles PNG with alpha, etc.)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Save resized main image
    img.thumbnail(MAX_PHOTO_SIZE, Image.LANCZOS)
    img.save(os.path.join(folder, filename), 'JPEG', quality=85)

    # Save thumbnail
    img.thumbnail(THUMB_SIZE, Image.LANCZOS)
    img.save(os.path.join(folder, thumb_filename), 'JPEG', quality=80)

    return filename


def delete_test_photo(filename):
    """Delete a test photo and its thumbnail from disk."""
    folder = current_app.config['MEDIA_FOLDER']
    for f in (filename, filename.replace('.jpg', '_thumb.jpg')):
        path = os.path.join(folder, f)
        if os.path.exists(path):
            os.unlink(path)


def _fix_orientation(img):
    """Auto-rotate image based on EXIF orientation tag."""
    try:
        from PIL import ExifTags
        exif = img._getexif()
        if exif:
            for tag, value in exif.items():
                if ExifTags.TAGS.get(tag) == 'Orientation':
                    if value == 3:
                        img = img.rotate(180, expand=True)
                    elif value == 6:
                        img = img.rotate(270, expand=True)
                    elif value == 8:
                        img = img.rotate(90, expand=True)
                    break
    except (AttributeError, Exception):
        pass
    return img


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
