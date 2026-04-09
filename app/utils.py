import os
from datetime import date, timedelta

from flask import current_app
from PIL import Image
from sqlalchemy import func
from .extensions import db
from .models import Test, Assignment

MAX_PHOTO_SIZE = (1200, 1200)
THUMB_SIZE = (200, 200)
Image.MAX_IMAGE_PIXELS = 25_000_000  # Guard against decompression bombs


def get_all_siren_statuses(sirens, year=None):
    """Compute statuses and last test dates for all sirens in batch.
    Returns (statuses_dict, last_tests_dict) using only 4 queries total."""
    if year is None:
        year = date.today().year

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    today = date.today()
    overdue_cutoff = today - timedelta(days=365)

    siren_ids = [s.id for s in sirens]
    siren_map = {s.id: s for s in sirens}

    # Query 1: Latest test per siren this year (with pass/fail)
    latest_this_year_sub = (
        db.session.query(
            Test.siren_id,
            func.max(Test.test_date).label('max_date'),
        )
        .filter(Test.siren_id.in_(siren_ids))
        .filter(Test.test_date.between(year_start, year_end))
        .group_by(Test.siren_id)
        .subquery()
    )
    latest_this_year = (
        db.session.query(Test.siren_id, Test.passed)
        .join(latest_this_year_sub, db.and_(
            Test.siren_id == latest_this_year_sub.c.siren_id,
            Test.test_date == latest_this_year_sub.c.max_date,
        ))
        .all()
    )
    year_results = {row.siren_id: row.passed for row in latest_this_year}

    # Query 2: Latest test date per siren (any year)
    latest_ever = (
        db.session.query(
            Test.siren_id,
            func.max(Test.test_date).label('max_date'),
        )
        .filter(Test.siren_id.in_(siren_ids))
        .group_by(Test.siren_id)
        .all()
    )
    last_test_dates = {row.siren_id: row.max_date for row in latest_ever}

    # Query 3: Sirens with claimed assignments for upcoming tests
    assigned_siren_ids = set(
        row[0] for row in
        db.session.query(Assignment.siren_id)
        .filter(Assignment.siren_id.in_(siren_ids))
        .filter(Assignment.status == 'CLAIMED')
        .filter(Assignment.test_date >= today)
        .distinct()
        .all()
    )

    # Compute statuses
    # Priority: failed > flagged > passed > overdue > assigned > untested
    # "Flagged" (needs_retest) overrides "passed" so admins can mark a
    # previously-passing siren for recheck and have it show on the dashboard.
    statuses = {}
    for sid in siren_ids:
        if sid in year_results and not year_results[sid]:
            statuses[sid] = 'failed'
        elif siren_map[sid].needs_retest:
            statuses[sid] = 'flagged'
        elif sid in year_results:
            statuses[sid] = 'passed'
        elif sid not in last_test_dates or last_test_dates[sid] < overdue_cutoff:
            statuses[sid] = 'overdue'
        elif sid in assigned_siren_ids:
            statuses[sid] = 'assigned'
        else:
            statuses[sid] = 'untested'

    return statuses, last_test_dates


def get_siren_status(siren, year=None):
    """Compute status for a single siren (used on detail page)."""
    statuses, _ = get_all_siren_statuses([siren], year)
    return statuses.get(siren.id, 'untested')


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
    if img.format not in ('JPEG', 'PNG', 'GIF', 'WEBP', 'MPO'):
        raise ValueError(f'Unsupported image format: {img.format}')
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


def get_inactive_members(threshold_days=365):
    """Return members who are admin-active in at least one program but have
    had no event attendance in the last threshold_days. Excluded:
    - Pending registrations (interests only, no admin-active flag)
    - Members created within the threshold period (new, not inactive)
    - Members whose last_active_date is within the threshold (catches
      siren-test activity that wasn't linked to EventAttendance)"""
    from .models import Member, EventAttendance, Event
    from datetime import datetime as dt
    cutoff = date.today() - timedelta(days=threshold_days)

    # Subquery: members who have attendance after cutoff
    active_member_ids = (
        db.session.query(EventAttendance.member_id)
        .join(Event)
        .filter(Event.date >= cutoff)
        .distinct()
        .subquery()
    )

    return Member.query.filter(
        Member.active == True,
        db.or_(
            Member.arpsc_active == True,
            Member.skywarn_active == True,
            Member.siren_testing_active == True,
        ),
        ~Member.id.in_(db.select(active_member_ids.c.member_id)),
        # Don't flag members who joined recently — they're new, not inactive
        Member.created_at < dt(cutoff.year, cutoff.month, cutoff.day),
        # Also honour last_active_date as a fallback (set by siren test
        # attendance even when observer→member matching fails for events)
        db.or_(
            Member.last_active_date == None,
            Member.last_active_date < cutoff,
        ),
    ).order_by(Member.name).all()


def add_years(d, years):
    """Add `years` to a date, clamping Feb 29 to Feb 28 in non-leap result years.
    Plain `d.replace(year=d.year + years)` raises ValueError on that case, which
    bites training-record expiration math when someone completes training on a
    leap day."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def stamp_program_audit_dates(member, prior_state):
    """Stamp arpsc/skywarn/siren_testing activation+deactivation dates and
    archived_at based on transitions from prior_state to member's current
    field values. Caller is responsible for committing.

    `prior_state` is a dict with keys 'arpsc', 'skywarn', 'siren_testing',
    'active' holding the booleans that were set BEFORE the form populated
    the member. Without this snapshot, historical state reports go wrong
    after the very first toggle."""
    today = date.today()
    for prog in ('arpsc', 'skywarn', 'siren_testing'):
        now_active = getattr(member, f'{prog}_active')
        was_active = prior_state.get(prog)
        if now_active and not was_active:
            setattr(member, f'{prog}_activated_at', today)
            setattr(member, f'{prog}_deactivated_at', None)
        elif (not now_active) and was_active:
            setattr(member, f'{prog}_deactivated_at', today)
    # Overall record archive flag
    was_active = prior_state.get('active')
    if member.active and not was_active:
        member.archived_at = None
    elif (not member.active) and was_active:
        member.archived_at = today


def snapshot_member_program_state(member):
    """Capture the current program-active and archive booleans on a member.
    Companion to stamp_program_audit_dates — call this before populating the
    form/CSV row, then pass the result back to stamp_ after."""
    return {
        'arpsc': member.arpsc_active,
        'skywarn': member.skywarn_active,
        'siren_testing': member.siren_testing_active,
        'active': member.active,
    }


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
