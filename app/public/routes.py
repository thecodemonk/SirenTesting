from datetime import date
from collections import Counter
from itertools import groupby

import requests as http_requests
from flask import render_template, request, flash, redirect, url_for, current_app
from . import public_bp
from .forms import SignupForm
from ..extensions import db, limiter
from ..models import Siren, Test, Assignment, TestSchedule
from ..utils import get_all_siren_statuses, get_siren_status, notify_admins


@public_bp.route('/')
def dashboard():
    current_year = date.today().year
    # Build year list from earliest test to current year
    years = list(range(current_year, current_year - 10, -1))
    selected_year = request.args.get('year', current_year, type=int)
    selected_year = max(current_year - 10, min(selected_year, current_year + 1))

    sirens = Siren.query.filter_by(active=True).order_by(Siren.siren_id).all()
    statuses, last_tests = get_all_siren_statuses(sirens, selected_year)

    status_counts = Counter(statuses.values())
    # Ensure all keys exist
    for key in ('passed', 'failed', 'overdue', 'flagged', 'assigned', 'untested'):
        status_counts.setdefault(key, 0)

    return render_template('public/dashboard.html',
                           sirens=sirens,
                           statuses=statuses,
                           last_tests=last_tests,
                           status_counts=status_counts,
                           years=years,
                           selected_year=selected_year)


@public_bp.route('/siren/<siren_id>')
def siren_detail(siren_id):
    siren = Siren.query.filter_by(siren_id=siren_id).first_or_404()
    status = get_siren_status(siren)

    tests = Test.query.filter_by(siren_id=siren.id).order_by(Test.test_date.desc()).all()

    # Group tests by year
    tests_by_year = []
    for year, group in groupby(tests, key=lambda t: t.test_date.year):
        tests_by_year.append((year, list(group)))

    return render_template('public/siren_detail.html',
                           siren=siren,
                           status=status,
                           tests_by_year=tests_by_year)


@public_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def signup():
    form = SignupForm()

    # Populate siren choices
    sirens = Siren.query.filter_by(active=True).order_by(Siren.siren_id).all()
    form.siren_id.choices = [(s.id, f'{s.siren_id} — {s.name}') for s in sirens]

    # Populate upcoming test dates
    today = date.today()
    upcoming = (
        TestSchedule.query
        .filter(TestSchedule.test_date >= today)
        .order_by(TestSchedule.test_date)
        .all()
    )
    form.test_date.choices = [
        (s.test_date.isoformat(), f'{s.test_date.strftime("%b %d, %Y")} — {s.description}')
        for s in upcoming
    ]

    # Pre-select siren from query param
    if request.method == 'GET' and request.args.get('siren'):
        form.siren_id.data = request.args.get('siren', type=int)

    if form.validate_on_submit():
        # Honeypot check
        if form.website.data:
            flash('Signup received. Thank you!', 'success')
            return redirect(url_for('public.signup'))

        # reCAPTCHA verification
        recaptcha_secret = current_app.config.get('RECAPTCHA_SECRET_KEY')
        if recaptcha_secret:
            token = request.form.get('g-recaptcha-response', '')
            resp = http_requests.post('https://www.google.com/recaptcha/api/siteverify', data={
                'secret': recaptcha_secret,
                'response': token,
                'remoteip': request.remote_addr,
            }, timeout=5)
            if not resp.json().get('success'):
                flash('Please complete the CAPTCHA.', 'danger')
                return render_template('public/signup.html', form=form)

        siren_id = form.siren_id.data
        test_date_str = form.test_date.data
        test_date_val = date.fromisoformat(test_date_str)

        # Double-booking check
        existing = Assignment.query.filter_by(
            siren_id=siren_id,
            test_date=test_date_val,
            status='CLAIMED'
        ).first()
        if existing:
            flash('This siren is already claimed for that test date. Please pick another.', 'warning')
            return render_template('public/signup.html', form=form)

        assignment = Assignment(
            siren_id=siren_id,
            volunteer_name=form.volunteer_name.data.strip(),
            test_date=test_date_val,
            status='CLAIMED',
        )
        db.session.add(assignment)
        db.session.commit()

        # Notify admins
        siren = db.session.get(Siren, siren_id)
        notify_admins(
            subject=f'Volunteer signup: {siren.siren_id} — {siren.name}',
            body=(
                f'Volunteer: {assignment.volunteer_name}\n'
                f'Siren: {siren.siren_id} — {siren.name}\n'
                f'Test date: {test_date_val.strftime("%b %d, %Y")}\n'
            ),
        )

        flash('Thank you for signing up! Your assignment has been recorded.', 'success')
        return redirect(url_for('public.dashboard'))

    return render_template('public/signup.html', form=form)
