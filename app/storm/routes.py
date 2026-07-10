from datetime import datetime, timezone

import requests as http_requests
from flask import render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import current_user
from sqlalchemy import func

from . import storm_bp
from .forms import DamageReportForm
from ..extensions import db, limiter
from ..models import Storm, DamageReport, Member, AdminUser
from ..nws import get_active_alerts
from ..utils import save_damage_photo, notify_admins


def _report_point(r):
    """Build a map point dict from a report with parseable coordinates, or None."""
    if not r.coordinates:
        return None
    try:
        lat, lng = (float(x) for x in r.coordinates.split(','))
    except (ValueError, TypeError):
        return None
    thumb = None
    if r.photo_filename:
        thumb = url_for('media_photo', filename=r.photo_filename.replace('.jpg', '_thumb.jpg'))
    return {
        'lat': lat, 'lng': lng, 'type': r.damage_type,
        'desc': r.description or '', 'thumb': thumb,
        'url': url_for('storm.detail', id=r.storm_id) if r.storm_id else url_for('storm.hub'),
    }


def _alerts_geojson():
    """A GeoJSON FeatureCollection of active alerts that carry geometry."""
    features = []
    for a in get_active_alerts():
        if a.get('geometry'):
            features.append({
                'type': 'Feature',
                'geometry': a['geometry'],
                'properties': {'event': a.get('event'), 'severity': a.get('severity')},
            })
    return {'type': 'FeatureCollection', 'features': features}


@storm_bp.route('/')
def hub():
    """Storm Center landing page — NWS alerts (via context processor), map, and
    recent approved damage reports."""
    reports = (
        DamageReport.query
        .filter_by(status='APPROVED')
        .order_by(DamageReport.occurred_at.desc())
        .limit(50)
        .all()
    )
    map_data = {
        'points': [p for p in (_report_point(r) for r in reports) if p],
        'alerts': _alerts_geojson(),
    }
    return render_template('storm/hub.html', reports=reports, map_data=map_data)


@storm_bp.route('/report', methods=['GET', 'POST'])
@limiter.limit('10/minute')
def report():
    form = DamageReportForm()
    is_member = current_user.is_authenticated and isinstance(current_user, Member)
    is_admin = current_user.is_authenticated and isinstance(current_user, AdminUser)
    # Any signed-in user (member or admin) is trusted: pre-fill their name,
    # skip the CAPTCHA, and post immediately without moderation.
    is_trusted = is_member or is_admin

    if request.method == 'GET' and is_trusted and not form.reporter_name.data:
        if is_member:
            form.reporter_name.data = current_user.callsign or current_user.name
        else:
            form.reporter_name.data = current_user.display_name

    if form.validate_on_submit():
        # Honeypot — silently accept and drop
        if form.website.data:
            flash('Report received. Thank you!', 'success')
            return redirect(url_for('storm.hub'))

        # reCAPTCHA required for the anonymous path only (signed-in users are trusted)
        if not is_trusted:
            recaptcha_secret = current_app.config.get('RECAPTCHA_SECRET_KEY')
            if recaptcha_secret:
                token = request.form.get('g-recaptcha-response', '')
                resp = http_requests.post(
                    'https://www.google.com/recaptcha/api/siteverify',
                    data={
                        'secret': recaptcha_secret,
                        'response': token,
                        'remoteip': request.remote_addr,
                    }, timeout=5)
                if not resp.json().get('success'):
                    flash('Please complete the CAPTCHA.', 'danger')
                    return render_template('storm/report_form.html', form=form)

        # Attach to the current active storm if one exists; else admin buckets it
        active_storm = (
            Storm.query.filter_by(status='ACTIVE')
            .order_by(Storm.event_date.desc())
            .first()
        )

        report = DamageReport(
            storm_id=active_storm.id if active_storm else None,
            reporter_name=form.reporter_name.data.strip(),
            reporter_member_id=current_user.id if is_member else None,
            occurred_at=form.occurred_at.data or datetime.now(timezone.utc),
            damage_type=form.damage_type.data,
            description=form.description.data,
            coordinates=(form.coordinates.data or '').strip() or None,
            location_text=form.location_text.data,
            status='APPROVED' if is_trusted else 'PENDING',
            source='member' if is_member else ('admin' if is_admin else 'public'),
        )
        db.session.add(report)
        db.session.commit()

        if form.photo.data:
            filename, gps = save_damage_photo(form.photo.data, report.id)
            report.photo_filename = filename
            # Fall back to the photo's EXIF GPS if no pin was dropped
            if not report.coordinates and gps:
                report.coordinates = gps
            db.session.commit()

        notify_admins(
            subject=f'Storm damage report: {report.damage_type}',
            body=(
                f'Reporter: {report.reporter_name}\n'
                f'Type: {report.damage_type}\n'
                f'Location: {report.location_text or report.coordinates or "n/a"}\n'
                f'Status: {report.status}\n\n'
                f'{report.description or ""}\n'
            ),
        )

        if is_trusted:
            flash('Thank you — your damage report has been posted.', 'success')
        else:
            flash('Thank you — your report was submitted and will appear on the '
                  'map once an admin reviews it.', 'success')
        return redirect(url_for('storm.hub'))

    return render_template('storm/report_form.html', form=form)


@storm_bp.route('/history')
def history():
    storms = Storm.query.order_by(Storm.event_date.desc()).all()
    counts = dict(
        db.session.query(DamageReport.storm_id, func.count())
        .filter(DamageReport.status == 'APPROVED')
        .group_by(DamageReport.storm_id)
        .all()
    )
    return render_template('storm/history.html', storms=storms, counts=counts)


@storm_bp.route('/storm/<int:id>')
def detail(id):
    storm = db.session.get(Storm, id) or abort(404)
    reports = (
        DamageReport.query
        .filter_by(storm_id=storm.id, status='APPROVED')
        .order_by(DamageReport.occurred_at.desc())
        .all()
    )
    map_data = {
        'points': [p for p in (_report_point(r) for r in reports) if p],
        'alerts': {'type': 'FeatureCollection', 'features': []},
    }
    if storm.center_coordinates:
        try:
            lat, lng = (float(x) for x in storm.center_coordinates.split(','))
            map_data['center'] = [lat, lng]
        except (ValueError, TypeError):
            pass
    return render_template('storm/detail.html', storm=storm, reports=reports, map_data=map_data)
