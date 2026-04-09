import csv
import io
import os
import re
import tempfile
from datetime import date, datetime

from flask import (
    abort, render_template, request, flash, redirect, url_for,
    Response, stream_with_context, session, current_app, jsonify,
)
from flask_login import current_user
from .decorators import admin_required
from .forms import (
    SirenForm, TestForm, AssignmentForm,
    EventForm, CommLogForm, CommLogEntryForm,
    MemberAdminForm, TaskBookLevelForm, TaskBookTaskForm,
)
from . import admin_bp
from ..extensions import db
from ..models import (
    Siren, SirenMaintenanceLog, Test, Assignment, TestSchedule, AdminUser,
    Member, MemberEquipmentItem, EquipmentType, MemberTraining, TrainingType,
    Event, EventAttendance,
    CommLog, CommLogEntry,
    TaskBookLevel, TaskBookTask, MemberTaskBookProgress,
)
from ..utils import generate_first_mondays, save_test_photo, delete_test_photo


# --- Sirens ---

@admin_bp.route('/')
@admin_bp.route('/sirens')
@admin_required
def sirens():
    all_sirens = Siren.query.order_by(Siren.siren_id).all()
    return render_template('admin/sirens.html', sirens=all_sirens)


@admin_bp.route('/sirens/add', methods=['GET', 'POST'])
@admin_required
def siren_add():
    form = SirenForm()
    if form.validate_on_submit():
        siren = Siren(
            siren_id=form.siren_id.data.strip(),
            name=form.name.data.strip(),
            location_text=form.location_text.data.strip() if form.location_text.data else None,
            location_url=form.location_url.data.strip() if form.location_url.data else None,
            year_in_service=form.year_in_service.data.strip() if form.year_in_service.data else None,
            siren_type=form.siren_type.data,
            active=form.active.data,
            needs_retest=form.needs_retest.data,
        )
        db.session.add(siren)
        db.session.commit()
        flash(f'Siren {siren.siren_id} added.', 'success')
        return redirect(url_for('admin.sirens'))
    return render_template('admin/siren_form.html', form=form, siren=None)


@admin_bp.route('/sirens/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def siren_edit(id):
    siren = db.session.get(Siren, id) or abort(404)
    form = SirenForm(obj=siren)
    if form.validate_on_submit():
        form.populate_obj(siren)
        db.session.commit()
        flash(f'Siren {siren.siren_id} updated.', 'success')
        return redirect(url_for('admin.sirens'))
    return render_template('admin/siren_form.html', form=form, siren=siren)


@admin_bp.route('/sirens/<int:id>/notes', methods=['POST'])
@admin_required
def siren_add_note(id):
    siren = db.session.get(Siren, id) or abort(404)
    note = request.form.get('note', '').strip()
    if note:
        log = SirenMaintenanceLog(
            siren_id=siren.id,
            author=current_user.display_name or current_user.email,
            note=note,
        )
        db.session.add(log)
        db.session.commit()
        flash('Maintenance note added.', 'success')
    return redirect(url_for('admin.siren_edit', id=id))


# --- Tests ---

@admin_bp.route('/tests')
@admin_required
def tests():
    all_tests = (
        Test.query
        .join(Siren)
        .order_by(Test.test_date.desc())
        .all()
    )
    return render_template('admin/tests.html', tests=all_tests)


@admin_bp.route('/tests/add', methods=['GET', 'POST'])
@admin_required
def test_add():
    form = TestForm()
    active_sirens = Siren.query.filter_by(active=True).order_by(Siren.siren_id).all()
    form.siren_id.choices = [
        (s.id, f'{s.siren_id} — {s.name}')
        for s in active_sirens
    ]
    # Store siren types for JS conditional rotation field
    siren_types = {s.id: s.siren_type for s in active_sirens}

    # Pre-fill from query params (e.g. coming from assignment "Log Result")
    assignment_id = request.args.get('assignment', type=int)
    if request.method == 'GET':
        if request.args.get('siren'):
            form.siren_id.data = request.args.get('siren', type=int)
        if request.args.get('date'):
            form.test_date.data = date.fromisoformat(request.args['date'])
        if request.args.get('observer'):
            form.observer.data = request.args['observer']

    if form.validate_on_submit():
        siren = db.session.get(Siren, form.siren_id.data)
        rotation_ok = form.rotation_ok.data if siren.siren_type == 'ROTATE' else None

        test = Test(
            siren_id=form.siren_id.data,
            test_date=form.test_date.data,
            observer=form.observer.data.strip(),
            passed=form.passed.data,
            sound_ok=form.sound_ok.data,
            rotation_ok=rotation_ok,
            vegetation_damage_ok=form.vegetation_damage_ok.data,
            notes=form.notes.data.strip() if form.notes.data else None,
        )
        db.session.add(test)

        # Auto-clear needs_retest on pass
        if test.passed and siren.needs_retest:
            siren.needs_retest = False

        # Auto-complete the linked assignment, or find a matching one by
        # siren+date so the helper below can use its member_id FK directly
        # instead of re-matching the observer string.
        linked_assignment = db.session.get(Assignment, assignment_id) if assignment_id else None
        if not linked_assignment:
            linked_assignment = Assignment.query.filter_by(
                siren_id=siren.id,
                test_date=test.test_date,
                status='CLAIMED',
            ).first()
        if linked_assignment and linked_assignment.status == 'CLAIMED':
            linked_assignment.status = 'COMPLETED'

        db.session.commit()

        # Save photo after commit so we have the test ID
        if form.photo.data:
            test.photo_filename = save_test_photo(form.photo.data, test.id)
            db.session.commit()

        # Auto-create event for siren test
        _create_siren_test_event(test, siren, assignment=linked_assignment)

        flash('Test result recorded.', 'success')
        if assignment_id:
            return redirect(url_for('admin.assignments'))
        return redirect(url_for('admin.tests'))

    return render_template('admin/test_form.html', form=form, siren_types=siren_types,
                           editing=False)


def _create_siren_test_event(test, siren, assignment=None):
    """Add the test's observer as an attendee on the Siren Test event for
    test.test_date, creating that event if no one has logged a test for
    that date yet.

    A scheduled siren test is a single ~30-minute event during which
    multiple volunteers each test a different siren. Net control then
    enters all the results afterward. We want exactly one Event per test
    date with all the volunteers as attendees — not one event per test
    result.

    Observer-to-member resolution prefers the linked Assignment's
    member_id FK when available (set when a logged-in member self-served
    via the public signup form), and falls back to fuzzy string matching
    on callsign then name otherwise. If everything misses we flash a
    warning so the admin notices and can manually fix it — much better
    than silently dropping attendance credit for the volunteer."""
    event = Event.query.filter_by(
        date=test.test_date,
        event_type='Siren Test',
        category='Siren Test',
    ).first()

    if event is None:
        event = Event(
            date=test.test_date,
            event_type='Siren Test',
            category='Siren Test',
            description='Siren Test',
            duration_hours=0.5,
            created_by_id=current_user.id if current_user.is_authenticated else None,
            siren_test_id=test.id,
        )
        db.session.add(event)
        db.session.flush()  # Get event.id

    # Resolve the observer to a Member.
    observer_member = None
    # 1. Cleanest path: the assignment was claimed by a logged-in member,
    #    so we already have a real FK. No string matching needed.
    if assignment and assignment.member_id:
        observer_member = db.session.get(Member, assignment.member_id)
    # 2. Fallback: case-insensitive exact match against callsign...
    if observer_member is None and test.observer:
        observer_member = Member.query.filter(
            db.func.lower(Member.callsign) == test.observer.strip().lower()
        ).first()
    # 3. ...then against name.
    if observer_member is None and test.observer:
        observer_member = Member.query.filter(
            db.func.lower(Member.name) == test.observer.strip().lower()
        ).first()

    if observer_member:
        # An observer who tested multiple sirens during one event should
        # get 0.5h credit once, not 0.5h × N. Skip if already attending.
        already = EventAttendance.query.filter_by(
            event_id=event.id, member_id=observer_member.id
        ).first()
        if already is None:
            db.session.add(EventAttendance(
                event_id=event.id,
                member_id=observer_member.id,
                hours=0.5,
            ))
        if not observer_member.last_active_date or observer_member.last_active_date < test.test_date:
            observer_member.last_active_date = test.test_date
    else:
        # Don't lose the work silently — surface a flash so the admin can
        # manually add the volunteer to the event's attendance.
        flash(
            f'Test recorded, but no member matched observer "{test.observer}". '
            f'No attendance credit was created — open the event for '
            f'{test.test_date.strftime("%b %d, %Y")} and add them manually.',
            'warning'
        )

    db.session.commit()
    return event


@admin_bp.route('/tests/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def test_edit(id):
    test = db.session.get(Test, id) or abort(404)
    form = TestForm(obj=test)
    active_sirens = Siren.query.filter_by(active=True).order_by(Siren.siren_id).all()
    # Include the test's siren even if inactive
    siren_ids = {s.id for s in active_sirens}
    if test.siren.id not in siren_ids:
        active_sirens.insert(0, test.siren)
    form.siren_id.choices = [
        (s.id, f'{s.siren_id} — {s.name}')
        for s in active_sirens
    ]
    siren_types = {s.id: s.siren_type for s in active_sirens}

    if form.validate_on_submit():
        siren = db.session.get(Siren, form.siren_id.data)
        test.siren_id = form.siren_id.data
        test.test_date = form.test_date.data
        test.observer = form.observer.data.strip()
        test.passed = form.passed.data
        test.sound_ok = form.sound_ok.data
        test.rotation_ok = form.rotation_ok.data if siren.siren_type == 'ROTATE' else None
        test.vegetation_damage_ok = form.vegetation_damage_ok.data
        test.notes = form.notes.data.strip() if form.notes.data else None

        if form.photo.data:
            # Remove old photo if replacing
            if test.photo_filename:
                delete_test_photo(test.photo_filename)
            test.photo_filename = save_test_photo(form.photo.data, test.id)

        db.session.commit()
        flash('Test result updated.', 'success')
        return redirect(url_for('admin.tests'))

    return render_template('admin/test_form.html', form=form, siren_types=siren_types,
                           editing=True, test=test)


@admin_bp.route('/tests/<int:id>/delete', methods=['POST'])
@admin_required
def test_delete(id):
    test = db.session.get(Test, id) or abort(404)
    if test.photo_filename:
        delete_test_photo(test.photo_filename)
    db.session.delete(test)
    db.session.commit()
    flash('Test result deleted.', 'info')
    return redirect(url_for('admin.tests'))


# --- Assignments ---

@admin_bp.route('/assignments')
@admin_required
def assignments():
    all_assignments = (
        Assignment.query
        .join(Siren)
        .order_by(Assignment.test_date.desc())
        .all()
    )
    return render_template('admin/assignments.html', assignments=all_assignments)


@admin_bp.route('/assignments/<int:id>/action', methods=['POST'])
@admin_required
def assignment_action(id):
    assignment = db.session.get(Assignment, id) or abort(404)
    action = request.form.get('action')
    if action == 'complete':
        assignment.status = 'COMPLETED'
        flash('Assignment marked as completed.', 'success')
    elif action == 'release':
        assignment.status = 'RELEASED'
        flash('Assignment released.', 'info')
    db.session.commit()
    return redirect(url_for('admin.assignments'))


@admin_bp.route('/assignments/add', methods=['GET', 'POST'])
@admin_required
def assignment_add():
    form = AssignmentForm()
    sirens = Siren.query.filter_by(active=True).order_by(Siren.siren_id).all()
    form.siren_id.choices = [
        (s.id, f'{s.siren_id} — {s.name}')
        for s in sirens
    ]

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

    if form.validate_on_submit():
        test_date_val = date.fromisoformat(form.test_date.data)

        existing = Assignment.query.filter_by(
            siren_id=form.siren_id.data,
            test_date=test_date_val,
            status='CLAIMED',
        ).first()
        if existing:
            flash('This siren is already claimed for that test date.', 'warning')
            return render_template('admin/assignment_form.html', form=form)

        assignment = Assignment(
            siren_id=form.siren_id.data,
            volunteer_name=form.volunteer_name.data.strip(),
            test_date=test_date_val,
            status='CLAIMED',
        )
        db.session.add(assignment)
        db.session.commit()
        flash(f'Assignment created for {assignment.volunteer_name}.', 'success')
        return redirect(url_for('admin.assignments'))

    return render_template('admin/assignment_form.html', form=form)


@admin_bp.route('/assignments/<int:id>/delete', methods=['POST'])
@admin_required
def assignment_delete(id):
    assignment = db.session.get(Assignment, id) or abort(404)
    db.session.delete(assignment)
    db.session.commit()
    flash('Assignment deleted.', 'info')
    return redirect(url_for('admin.assignments'))


# --- Schedule ---

@admin_bp.route('/schedule')
@admin_required
def schedule():
    schedules = TestSchedule.query.order_by(TestSchedule.test_date).all()
    return render_template('admin/schedule.html',
                           schedules=schedules,
                           current_year=date.today().year)


@admin_bp.route('/schedule/generate', methods=['POST'])
@admin_required
def schedule_generate():
    year = request.form.get('year', date.today().year, type=int)
    dates = generate_first_mondays(year)
    added = 0
    for d in dates:
        existing = TestSchedule.query.filter_by(test_date=d).first()
        if not existing:
            db.session.add(TestSchedule(test_date=d, test_time='13:00', description='Monthly Test'))
            added += 1
    db.session.commit()
    flash(f'Generated {added} new monthly test dates for {year}.', 'success')
    return redirect(url_for('admin.schedule'))


@admin_bp.route('/schedule/add', methods=['POST'])
@admin_required
def schedule_add():
    test_date_str = request.form.get('test_date')
    test_time = request.form.get('test_time', '13:00')
    description = request.form.get('description', 'Special Test')
    try:
        test_date_val = date.fromisoformat(test_date_str)
    except (ValueError, TypeError):
        flash('Invalid date.', 'danger')
        return redirect(url_for('admin.schedule'))

    db.session.add(TestSchedule(
        test_date=test_date_val,
        test_time=test_time,
        description=description,
    ))
    db.session.commit()
    flash('Test date added.', 'success')
    return redirect(url_for('admin.schedule'))


@admin_bp.route('/schedule/<int:id>/delete', methods=['POST'])
@admin_required
def schedule_delete(id):
    entry = db.session.get(TestSchedule, id) or abort(404)
    db.session.delete(entry)
    db.session.commit()
    flash('Test date removed.', 'info')
    return redirect(url_for('admin.schedule'))


# =====================================================
# MEMBERS ADMIN
# =====================================================

@admin_bp.route('/members')
@admin_required
def members():
    query = Member.query
    search = request.args.get('q', '').strip()
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(Member.name.ilike(like), Member.callsign.ilike(like), Member.email.ilike(like))
        )
    # Program filter — narrows by *_active flag (admin gate), not by interest
    filter_program = request.args.get('program', '')
    if filter_program == 'arpsc':
        query = query.filter(Member.arpsc_active == True, Member.active == True)
    elif filter_program == 'skywarn':
        query = query.filter(Member.skywarn_active == True, Member.active == True)
    elif filter_program == 'siren_testing':
        query = query.filter(Member.siren_testing_active == True, Member.active == True)
    elif filter_program == 'archived':
        query = query.filter(Member.active == False)
    elif filter_program == 'pending':
        # Members with at least one interest checked but no admin-active flag
        query = query.filter(
            Member.active == True,
            Member.arpsc_active == False,
            Member.skywarn_active == False,
            Member.siren_testing_active == False,
            db.or_(
                Member.interest_skywarn == True,
                Member.interest_ares_auxcomm == True,
                Member.interest_siren_testing == True,
            ),
        )
    else:
        # Default view excludes archived members
        query = query.filter(Member.active == True)
    all_members = query.order_by(Member.name).all()

    # Stats strip — totals across the whole org regardless of current filter
    stats = {
        'arpsc': Member.query.filter_by(active=True, arpsc_active=True).count(),
        'skywarn': Member.query.filter_by(active=True, skywarn_active=True).count(),
        'siren_testing': Member.query.filter_by(active=True, siren_testing_active=True).count(),
        'archived': Member.query.filter_by(active=False).count(),
    }

    # Find admin accounts that don't have a matching member record
    member_emails = {m.email.lower() for m in Member.query.with_entities(Member.email).all()}
    admin_emails_without_member = [
        a for a in AdminUser.query.all()
        if a.email.lower() not in member_emails
    ]

    return render_template('admin/members_list.html', members=all_members,
                           search=search, filter_program=filter_program, stats=stats,
                           admin_emails_without_member=admin_emails_without_member)


@admin_bp.route('/members/add-admins', methods=['POST'])
@admin_required
def members_add_admins():
    member_emails = {m.email.lower() for m in Member.query.with_entities(Member.email).all()}
    admins = AdminUser.query.all()
    added = 0
    for admin in admins:
        if admin.email.lower() not in member_emails:
            member = Member(
                name=admin.display_name or admin.email.split('@')[0],
                email=admin.email,
                active=True,
            )
            db.session.add(member)
            added += 1
    db.session.commit()
    flash(f'Created {added} member record(s) from admin accounts.', 'success')
    return redirect(url_for('admin.members'))


@admin_bp.route('/members/inactive')
@admin_required
def members_inactive():
    from ..utils import get_inactive_members
    inactive = get_inactive_members(
        current_app.config.get('INACTIVITY_THRESHOLD_DAYS', 365)
    )
    return render_template('admin/members_inactive.html', members=inactive)


@admin_bp.route('/members/<int:id>')
@admin_required
def member_detail(id):
    member = db.session.get(Member, id) or abort(404)
    # Eager load equipment types to avoid N+1
    db.session.query(MemberEquipmentItem).options(
        db.joinedload(MemberEquipmentItem.equipment_type)
    ).filter_by(member_id=id).all()

    trainings = MemberTraining.query.filter_by(member_id=id).order_by(
        MemberTraining.completion_date.desc()).all()

    # Get true total hours (separate query, no limit)
    total_hours = db.session.query(
        db.func.coalesce(db.func.sum(EventAttendance.hours), 0)
    ).filter(EventAttendance.member_id == id).scalar()

    # Recent activity (limited for display)
    attendance = (
        db.session.query(EventAttendance, Event)
        .join(Event)
        .filter(EventAttendance.member_id == id)
        .order_by(Event.date.desc())
        .limit(50)
        .all()
    )

    # Task book progress — eager load tasks
    levels = TaskBookLevel.query.options(
        db.joinedload(TaskBookLevel.tasks)
    ).order_by(TaskBookLevel.display_order).all()
    progress_records = MemberTaskBookProgress.query.filter_by(member_id=id).all()
    progress_map = {p.task_id: p for p in progress_records}

    training_types = TrainingType.query.order_by(TrainingType.display_order).all()

    return render_template('admin/member_detail.html', member=member,
                           trainings=trainings, attendance=attendance,
                           total_hours=total_hours, levels=levels,
                           progress_map=progress_map, training_types=training_types)


@admin_bp.route('/members/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def member_edit(id):
    member = db.session.get(Member, id) or abort(404)
    form = MemberAdminForm(obj=member)
    if form.validate_on_submit():
        from ..utils import snapshot_member_program_state, stamp_program_audit_dates
        prior = snapshot_member_program_state(member)
        form.populate_obj(member)
        stamp_program_audit_dates(member, prior)
        db.session.commit()
        flash(f'Member {member.name} updated.', 'success')
        return redirect(url_for('admin.member_detail', id=id))
    return render_template('admin/member_form.html', form=form, member=member)


@admin_bp.route('/members/<int:id>/toggle-active', methods=['POST'])
@admin_required
def member_toggle_active(id):
    """Archive or restore a member. Archiving = active=False + stamp archived_at.
    The member stays in past attendance/reports but disappears from pickers and
    current state-report counts."""
    member = db.session.get(Member, id) or abort(404)
    member.active = not member.active
    member.archived_at = date.today() if not member.active else None
    db.session.commit()
    status = 'restored' if member.active else 'archived'
    flash(f'{member.name} {status}.', 'info')
    return redirect(url_for('admin.member_detail', id=id))


@admin_bp.route('/members/<int:id>/equipment', methods=['GET', 'POST'])
@admin_required
def member_equipment(id):
    member = db.session.get(Member, id) or abort(404)
    equipment_types = EquipmentType.query.order_by(EquipmentType.display_order).all()

    if request.method == 'POST':
        MemberEquipmentItem.query.filter_by(member_id=member.id).delete()
        for et in equipment_types:
            if f'equip_{et.id}' in request.form:
                item = MemberEquipmentItem(
                    member_id=member.id,
                    equipment_type_id=et.id,
                    details=request.form.get(f'details_{et.id}', '').strip() or None,
                )
                db.session.add(item)
        db.session.commit()
        flash(f'Equipment updated for {member.name}.', 'success')
        return redirect(url_for('admin.member_detail', id=member.id))

    current_items = {item.equipment_type_id: item for item in member.equipment_items}
    return render_template('admin/member_equipment.html', member=member,
                           equipment_types=equipment_types, current_items=current_items)


@admin_bp.route('/members/<int:id>/training/add', methods=['POST'])
@admin_required
def member_training_add(id):
    member = db.session.get(Member, id) or abort(404)
    training_type = request.form.get('training_type', '').strip()
    if training_type == 'Other':
        custom = request.form.get('custom_type', '').strip()
        if custom:
            training_type = custom

    completion_date_str = request.form.get('completion_date', '')
    try:
        completion_date_val = date.fromisoformat(completion_date_str)
    except (ValueError, TypeError):
        flash('Invalid date.', 'danger')
        return redirect(url_for('admin.member_detail', id=id))

    # Check for explicit expiration override, otherwise auto-compute
    exp_str = request.form.get('expiration_date', '').strip()
    expiration_date = None
    if exp_str:
        try:
            expiration_date = date.fromisoformat(exp_str)
        except ValueError:
            pass
    if not expiration_date:
        tt = TrainingType.query.filter_by(name=training_type).first()
        if tt and tt.has_expiration and tt.expiration_years:
            from ..utils import add_years
            expiration_date = add_years(completion_date_val, tt.expiration_years)

    training = MemberTraining(
        member_id=member.id,
        training_type=training_type,
        completion_date=completion_date_val,
        expiration_date=expiration_date,
        certificate_number=request.form.get('certificate_number', '').strip() or None,
    )
    db.session.add(training)
    db.session.commit()
    flash(f'{training_type} training added for {member.name}.', 'success')
    return redirect(url_for('admin.member_detail', id=id))


@admin_bp.route('/members/<int:id>/training/<int:training_id>/delete', methods=['POST'])
@admin_required
def member_training_delete(id, training_id):
    training = MemberTraining.query.filter_by(id=training_id, member_id=id).first_or_404()
    db.session.delete(training)
    db.session.commit()
    flash('Training record removed.', 'info')
    return redirect(url_for('admin.member_detail', id=id))


# =====================================================
# EVENTS & ATTENDANCE
# =====================================================

@admin_bp.route('/events')
@admin_required
def events():
    query = Event.query
    cat = request.args.get('category')
    if cat:
        query = query.filter(Event.category == cat)
    etype = request.args.get('type')
    if etype:
        query = query.filter(Event.event_type == etype)
    all_events = query.options(db.joinedload(Event.attendance)).order_by(Event.date.desc()).all()
    return render_template('admin/events.html', events=all_events,
                           filter_category=cat, filter_type=etype)


@admin_bp.route('/events/add', methods=['GET', 'POST'])
@admin_required
def event_add():
    form = EventForm()
    if form.validate_on_submit():
        event = Event(
            date=form.date.data,
            event_type=form.event_type.data,
            category=form.category.data,
            description=form.description.data.strip() if form.description.data else None,
            duration_hours=form.duration_hours.data,
            has_nts_liaison=form.has_nts_liaison.data,
            created_by_id=current_user.id,
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created.', 'success')
        return redirect(url_for('admin.event_attendance', id=event.id))
    return render_template('admin/event_form.html', form=form, event=None)


@admin_bp.route('/events/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def event_edit(id):
    event = db.session.get(Event, id) or abort(404)
    form = EventForm(obj=event)
    if form.validate_on_submit():
        form.populate_obj(event)
        if form.description.data:
            event.description = form.description.data.strip()
        db.session.commit()
        flash('Event updated.', 'success')
        return redirect(url_for('admin.events'))
    return render_template('admin/event_form.html', form=form, event=event)


@admin_bp.route('/events/<int:id>/delete', methods=['POST'])
@admin_required
def event_delete(id):
    event = db.session.get(Event, id) or abort(404)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'info')
    return redirect(url_for('admin.events'))


@admin_bp.route('/events/<int:id>/attendance')
@admin_required
def event_attendance(id):
    event = db.session.get(Event, id) or abort(404)

    # Filtering is done client-side so toggling a pill doesn't reload the
    # page (which would discard any in-progress attendance ticks). The route
    # just hands the template every active member tagged with their program
    # flags via data attributes; the JS in the template hides/shows rows
    # based on which pills are toggled. We still preselect pills based on
    # the event's category for the common case.
    members = Member.query.filter_by(active=True).order_by(Member.name).all()
    current_attendance = {a.member_id: a for a in event.attendance}

    category_defaults = {
        'SKYWARN': {'skywarn'},
        'ARPSC': {'arpsc'},
        'Siren Test': {'siren_testing'},
    }
    default_programs = category_defaults.get(event.category, {'all'})

    return render_template('admin/event_attendance.html', event=event,
                           members=members, current_attendance=current_attendance,
                           default_programs=default_programs)


@admin_bp.route('/events/<int:event_id>/attendance/upsert', methods=['POST'])
@admin_required
def event_attendance_upsert(event_id):
    """Per-row attendance autosave. The picker fires this on every checkbox
    change and on hours-field blur, so an admin can fill in attendance just
    by ticking boxes — no Save button required. Returns JSON; on failure the
    JS reverts the row's UI state."""
    event = db.session.get(Event, event_id) or abort(404)

    try:
        member_id = int(request.form.get('member_id', 0))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Invalid member_id'}), 400

    member = db.session.get(Member, member_id)
    if not member or not member.active:
        return jsonify({'ok': False, 'error': 'Member not found or archived'}), 404

    attending = request.form.get('attending') == 'true'

    try:
        hours = float(request.form.get('hours') or event.duration_hours or 0)
    except (TypeError, ValueError):
        hours = float(event.duration_hours or 0)
    if hours < 0:
        hours = 0.0

    existing = EventAttendance.query.filter_by(
        event_id=event.id, member_id=member.id
    ).first()

    if attending:
        if existing:
            existing.hours = hours
        else:
            db.session.add(EventAttendance(
                event_id=event.id, member_id=member.id, hours=hours,
            ))
        if not member.last_active_date or member.last_active_date < event.date:
            member.last_active_date = event.date
    else:
        if existing:
            db.session.delete(existing)

    db.session.commit()
    return jsonify({'ok': True, 'attending': attending, 'hours': hours})


# =====================================================
# COMM LOGS
# =====================================================

@admin_bp.route('/commlogs')
@admin_required
def commlogs():
    all_logs = CommLog.query.options(db.joinedload(CommLog.entries)).order_by(CommLog.op_period_start.desc()).all()
    return render_template('admin/commlogs.html', commlogs=all_logs)


@admin_bp.route('/commlogs/add', methods=['GET', 'POST'])
@admin_required
def commlog_add():
    form = CommLogForm()
    _populate_commlog_event_choices(form)

    if form.validate_on_submit():
        log = CommLog(
            incident_name=form.incident_name.data.strip(),
            activation_number=form.activation_number.data.strip() if form.activation_number.data else None,
            op_period_start=form.op_period_start.data,
            op_period_end=form.op_period_end.data,
            net_name_or_position=form.net_name_or_position.data.strip() if form.net_name_or_position.data else None,
            operator_name=form.operator_name.data.strip(),
            operator_callsign=form.operator_callsign.data.strip() if form.operator_callsign.data else None,
            prepared_by=form.prepared_by.data.strip() if form.prepared_by.data else None,
            prepared_date=form.prepared_date.data,
            event_id=form.event_id.data if form.event_id.data else None,
        )
        db.session.add(log)
        db.session.commit()
        flash('Comm log created.', 'success')
        return redirect(url_for('admin.commlog_entries', id=log.id))
    return render_template('admin/commlog_form.html', form=form, commlog=None)


@admin_bp.route('/commlogs/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def commlog_edit(id):
    log = db.session.get(CommLog, id) or abort(404)
    form = CommLogForm(obj=log)
    _populate_commlog_event_choices(form)

    if form.validate_on_submit():
        form.populate_obj(log)
        if log.incident_name:
            log.incident_name = log.incident_name.strip()
        if log.operator_name:
            log.operator_name = log.operator_name.strip()
        log.event_id = form.event_id.data if form.event_id.data else None
        db.session.commit()
        flash('Comm log updated.', 'success')
        return redirect(url_for('admin.commlogs'))
    return render_template('admin/commlog_form.html', form=form, commlog=log)


@admin_bp.route('/commlogs/<int:id>/delete', methods=['POST'])
@admin_required
def commlog_delete(id):
    log = db.session.get(CommLog, id) or abort(404)
    db.session.delete(log)
    db.session.commit()
    flash('Comm log deleted.', 'info')
    return redirect(url_for('admin.commlogs'))


@admin_bp.route('/commlogs/<int:id>/entries', methods=['GET', 'POST'])
@admin_required
def commlog_entries(id):
    log = db.session.get(CommLog, id) or abort(404)
    form = CommLogEntryForm()

    if form.validate_on_submit():
        entry = CommLogEntry(
            comm_log_id=log.id,
            time=form.time.data,
            from_callsign=form.from_callsign.data.strip() if form.from_callsign.data else None,
            from_msg_num=form.from_msg_num.data.strip() if form.from_msg_num.data else None,
            to_callsign=form.to_callsign.data.strip() if form.to_callsign.data else None,
            to_msg_num=form.to_msg_num.data.strip() if form.to_msg_num.data else None,
            message=form.message.data.strip() if form.message.data else None,
        )
        db.session.add(entry)
        db.session.commit()
        flash('Entry added.', 'success')
        return redirect(url_for('admin.commlog_entries', id=log.id))

    entries = CommLogEntry.query.filter_by(comm_log_id=log.id).order_by(CommLogEntry.time).all()
    return render_template('admin/commlog_entries.html', commlog=log, entries=entries, form=form)


@admin_bp.route('/commlogs/<int:id>/entries/<int:entry_id>/delete', methods=['POST'])
@admin_required
def commlog_entry_delete(id, entry_id):
    entry = CommLogEntry.query.filter_by(id=entry_id, comm_log_id=id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash('Entry removed.', 'info')
    return redirect(url_for('admin.commlog_entries', id=id))


@admin_bp.route('/commlogs/<int:id>/pdf')
@admin_required
def commlog_pdf(id):
    log = db.session.get(CommLog, id) or abort(404)
    from ..pdf import generate_ics309_pdf
    pdf_buffer = generate_ics309_pdf(log)
    safe_name = re.sub(r'[^\w\s-]', '', log.incident_name).strip().replace(' ', '_')
    return Response(
        pdf_buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline; filename="ICS-309_{safe_name}.pdf"'},
    )


def _populate_commlog_event_choices(form):
    """Populate the event_id dropdown for comm log forms."""
    events = Event.query.order_by(Event.date.desc()).limit(50).all()
    form.event_id.choices = [(0, '— None —')] + [
        (e.id, f'{e.date.strftime("%Y-%m-%d")} — {e.event_type}: {e.description or ""}')
        for e in events
    ]


# =====================================================
# TASK BOOKS
# =====================================================

@admin_bp.route('/taskbooks')
@admin_required
def taskbooks():
    levels = TaskBookLevel.query.order_by(TaskBookLevel.display_order).all()
    return render_template('admin/taskbooks.html', levels=levels)


@admin_bp.route('/taskbooks/add', methods=['GET', 'POST'])
@admin_required
def taskbook_add():
    form = TaskBookLevelForm()
    if form.validate_on_submit():
        level = TaskBookLevel(
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            display_order=form.display_order.data or 0,
        )
        db.session.add(level)
        db.session.commit()
        flash(f'Task book level "{level.name}" created.', 'success')
        return redirect(url_for('admin.taskbook_edit', id=level.id))
    return render_template('admin/taskbook_form.html', form=form, level=None, tasks=[])


@admin_bp.route('/taskbooks/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def taskbook_edit(id):
    level = db.session.get(TaskBookLevel, id) or abort(404)
    form = TaskBookLevelForm(obj=level)
    task_form = TaskBookTaskForm()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_level' and form.validate_on_submit():
            form.populate_obj(level)
            if level.name:
                level.name = level.name.strip()
            db.session.commit()
            flash('Level updated.', 'success')
        elif action == 'add_task' and task_form.validate_on_submit():
            max_order = db.session.query(db.func.max(TaskBookTask.display_order)).filter_by(
                level_id=level.id).scalar() or 0
            task = TaskBookTask(
                level_id=level.id,
                name=task_form.name.data.strip(),
                description=task_form.description.data.strip() if task_form.description.data else None,
                display_order=max_order + 1,
            )
            db.session.add(task)
            db.session.commit()
            flash(f'Task "{task.name}" added.', 'success')
        elif action == 'delete_task':
            task_id = request.form.get('task_id', type=int)
            task = TaskBookTask.query.filter_by(id=task_id, level_id=level.id).first()
            if task:
                db.session.delete(task)
                db.session.commit()
                flash('Task removed.', 'info')

        return redirect(url_for('admin.taskbook_edit', id=level.id))

    tasks = TaskBookTask.query.filter_by(level_id=level.id).order_by(
        TaskBookTask.display_order).all()
    return render_template('admin/taskbook_form.html', form=form, level=level,
                           tasks=tasks, task_form=task_form)


@admin_bp.route('/taskbooks/<int:id>/delete', methods=['POST'])
@admin_required
def taskbook_delete(id):
    level = db.session.get(TaskBookLevel, id) or abort(404)
    db.session.delete(level)
    db.session.commit()
    flash('Task book level deleted.', 'info')
    return redirect(url_for('admin.taskbooks'))


@admin_bp.route('/taskbooks/<int:id>/import', methods=['POST'])
@admin_required
def taskbook_import(id):
    level = db.session.get(TaskBookLevel, id) or abort(404)
    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a CSV file.', 'danger')
        return redirect(url_for('admin.taskbook_edit', id=level.id))

    try:
        content = file.stream.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        flash('CSV file must be UTF-8 encoded.', 'danger')
        return redirect(url_for('admin.taskbook_edit', id=level.id))
    reader = csv.DictReader(io.StringIO(content))
    max_order = db.session.query(db.func.max(TaskBookTask.display_order)).filter_by(
        level_id=level.id).scalar() or 0

    added = 0
    for row in reader:
        name = (row.get('name') or row.get('task_name', '')).strip()
        if not name:
            continue
        description = (row.get('description') or row.get('task_description', '')).strip()
        max_order += 1
        task = TaskBookTask(
            level_id=level.id,
            name=name,
            description=description or None,
            display_order=max_order,
        )
        db.session.add(task)
        added += 1

    db.session.commit()
    flash(f'Imported {added} tasks.', 'success')
    return redirect(url_for('admin.taskbook_edit', id=level.id))


@admin_bp.route('/taskbooks/member/<int:member_id>/<int:level_id>', methods=['GET', 'POST'])
@admin_required
def taskbook_member(member_id, level_id):
    member = db.session.get(Member, member_id) or abort(404)
    level = db.session.get(TaskBookLevel, level_id) or abort(404)
    tasks = TaskBookTask.query.filter_by(level_id=level.id).order_by(
        TaskBookTask.display_order).all()

    if request.method == 'POST':
        for task in tasks:
            checkbox_key = f'task_{task.id}'
            officer1_key = f'officer1_{task.id}'
            officer2_key = f'officer2_{task.id}'
            date_key = f'date_{task.id}'

            progress = MemberTaskBookProgress.query.filter_by(
                member_id=member.id, task_id=task.id).first()

            if checkbox_key in request.form:
                completed_date_str = request.form.get(date_key, '')
                try:
                    completed_date = date.fromisoformat(completed_date_str) if completed_date_str else date.today()
                except ValueError:
                    completed_date = date.today()

                officer1_id = request.form.get(officer1_key, type=int) or None
                officer2_id = request.form.get(officer2_key, type=int) or None

                if progress:
                    progress.completed_date = completed_date
                    progress.officer1_id = officer1_id
                    progress.officer2_id = officer2_id
                else:
                    progress = MemberTaskBookProgress(
                        member_id=member.id,
                        task_id=task.id,
                        completed_date=completed_date,
                        officer1_id=officer1_id,
                        officer2_id=officer2_id,
                    )
                    db.session.add(progress)
            else:
                if progress:
                    db.session.delete(progress)

        db.session.commit()
        flash('Task book progress updated.', 'success')
        return redirect(url_for('admin.taskbook_member',
                                member_id=member.id, level_id=level.id))

    progress_records = MemberTaskBookProgress.query.filter_by(member_id=member.id).all()
    progress_map = {p.task_id: p for p in progress_records}
    # Officers must be ARPSC-active. Pending registrations and Skywarn-only
    # spotters can't sign off on task book tasks.
    officers = (
        Member.query
        .filter_by(active=True, arpsc_active=True)
        .order_by(Member.name)
        .all()
    )

    return render_template('admin/taskbook_member.html', member=member, level=level,
                           tasks=tasks, progress_map=progress_map, officers=officers)


# =====================================================
# CONFIGURATION — Equipment Types & Training Types
# =====================================================

@admin_bp.route('/config/equipment-types', methods=['GET', 'POST'])
@admin_required
def config_equipment_types():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                max_order = db.session.query(db.func.max(EquipmentType.display_order)).scalar() or 0
                et = EquipmentType(
                    name=name,
                    has_details='has_details' in request.form,
                    display_order=max_order + 1,
                )
                db.session.add(et)
                db.session.commit()
                flash(f'Equipment type "{name}" added.', 'success')
        elif action == 'update':
            et_id = request.form.get('type_id', type=int)
            et = db.session.get(EquipmentType, et_id)
            if et:
                et.name = request.form.get('name', et.name).strip()
                et.display_order = request.form.get('display_order', et.display_order, type=int)
                et.has_details = 'has_details' in request.form
                db.session.commit()
                flash(f'Equipment type "{et.name}" updated.', 'success')
        elif action == 'delete':
            et_id = request.form.get('type_id', type=int)
            et = db.session.get(EquipmentType, et_id)
            if et:
                # Delete related member items first
                MemberEquipmentItem.query.filter_by(equipment_type_id=et.id).delete()
                db.session.delete(et)
                db.session.commit()
                flash(f'Equipment type "{et.name}" removed.', 'info')
        return redirect(url_for('admin.config_equipment_types'))

    types = EquipmentType.query.order_by(EquipmentType.display_order).all()
    return render_template('admin/config_equipment_types.html', types=types)


@admin_bp.route('/config/training-types', methods=['GET', 'POST'])
@admin_required
def config_training_types():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                max_order = db.session.query(db.func.max(TrainingType.display_order)).scalar() or 0
                has_exp = 'has_expiration' in request.form
                exp_years = request.form.get('expiration_years', type=int) if has_exp else None
                tt = TrainingType(
                    name=name,
                    has_expiration=has_exp,
                    expiration_years=exp_years,
                    display_order=max_order + 1,
                )
                db.session.add(tt)
                db.session.commit()
                flash(f'Training type "{name}" added.', 'success')
        elif action == 'update':
            tt_id = request.form.get('type_id', type=int)
            tt = db.session.get(TrainingType, tt_id)
            if tt:
                tt.name = request.form.get('name', tt.name).strip()
                tt.display_order = request.form.get('display_order', tt.display_order, type=int)
                tt.has_expiration = 'has_expiration' in request.form
                tt.expiration_years = request.form.get('expiration_years', type=int) if tt.has_expiration else None
                db.session.commit()
                flash(f'Training type "{tt.name}" updated.', 'success')
        elif action == 'delete':
            tt_id = request.form.get('type_id', type=int)
            tt = db.session.get(TrainingType, tt_id)
            if tt:
                db.session.delete(tt)
                db.session.commit()
                flash(f'Training type "{tt.name}" removed.', 'info')
        return redirect(url_for('admin.config_training_types'))

    types = TrainingType.query.order_by(TrainingType.display_order).all()
    return render_template('admin/config_training_types.html', types=types)


# =====================================================
# REPORTS
# =====================================================

@admin_bp.route('/reports')
@admin_required
def reports():
    year, month = _get_report_year_month()
    from ..reports import generate_monthly_report
    report = generate_monthly_report(year, month)
    return render_template('admin/reports.html', report=report, year=year, month=month)


def _get_report_year_month():
    """Read and validate year/month query params for the state report.
    Falls back to today's year/month for any invalid input. Prevents crashes
    from URL fuzzing or stale bookmarks with garbage params."""
    today = date.today()
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if year is None or year < 2000 or year > 2100:
        year = today.year
    if month is None or month < 1 or month > 12:
        month = today.month
    return year, month


@admin_bp.route('/reports/export')
@admin_required
def reports_export():
    year, month = _get_report_year_month()
    from ..reports import generate_monthly_report
    report = generate_monthly_report(year, month)

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Category', 'Count', 'Hours'])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for cat_key, cat_label in [
            ('drills', 'Drills'), ('public_service', 'Public Service Events'),
            ('public_safety', 'Public Safety Incidents'), ('skywarn', 'SKYWARN Activations'),
            ('total_public_safety', 'Total Public Safety'),
        ]:
            writer.writerow([
                cat_label, report[f'{cat_key}_count'], f'{report[f"{cat_key}_hours"]:.1f}'
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

        writer.writerow([])
        writer.writerow(['Active Members', report['active_members']])
        writer.writerow(['Nets with NTS Liaison', report['nets_with_nts_liaison']])
        writer.writerow(['Total Person-Hours', f'{report["total_person_hours"]:.1f}'])
        writer.writerow(['Dollar Value', f'${report["dollar_value"]:.2f}'])
        yield output.getvalue()

    filename = f'arpsc_report_{year}_{month:02d}.csv'
    return Response(
        stream_with_context(generate()),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


# =====================================================
# CSV EXPORT / IMPORT
# =====================================================

def _sanitize_csv_value(val):
    """Prevent CSV formula injection by prefixing dangerous values with a single quote."""
    if isinstance(val, str) and val and val[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + val
    return val


@admin_bp.route('/export/<table>')
@admin_required
def export_csv(table):
    if table == 'sirens':
        columns = ['siren_id', 'name', 'location_text', 'location_url', 'coordinates',
                    'year_in_service', 'siren_type', 'active', 'needs_retest']
        rows = Siren.query.order_by(Siren.siren_id).all()
    elif table == 'tests':
        columns = ['siren_id', 'test_date', 'observer', 'passed',
                    'sound_ok', 'rotation_ok', 'vegetation_damage_ok', 'notes']
        rows = Test.query.join(Siren).order_by(Test.test_date.desc()).all()
        def row_dict(t):
            d = {c: getattr(t, c) for c in columns}
            d['siren_id'] = t.siren.siren_id
            return d
    elif table == 'assignments':
        columns = ['siren_id', 'volunteer_name', 'test_date', 'status']
        rows = Assignment.query.join(Siren).order_by(Assignment.test_date.desc()).all()
        def row_dict(a):
            d = {c: getattr(a, c) for c in columns}
            d['siren_id'] = a.siren.siren_id
            return d
    elif table == 'schedules':
        columns = ['test_date', 'test_time', 'description']
        rows = TestSchedule.query.order_by(TestSchedule.test_date).all()
    elif table == 'members':
        columns = ['name', 'callsign', 'email', 'phone', 'city', 'state',
                    'interest_skywarn', 'interest_ares_auxcomm', 'interest_siren_testing',
                    'arpsc_active', 'skywarn_active', 'siren_testing_active',
                    'arpsc_activated_at', 'arpsc_deactivated_at',
                    'skywarn_activated_at', 'skywarn_deactivated_at',
                    'siren_testing_activated_at', 'siren_testing_deactivated_at',
                    'can_edit_sirens',
                    'active', 'archived_at', 'last_active_date']
        rows = Member.query.order_by(Member.name).all()
    elif table == 'events':
        columns = ['date', 'event_type', 'category', 'description', 'duration_hours', 'has_nts_liaison']
        rows = Event.query.order_by(Event.date.desc()).all()
    elif table == 'attendance':
        columns = ['event_date', 'event_type', 'event_description', 'member_name', 'member_callsign', 'hours']
        rows = (
            db.session.query(EventAttendance, Event, Member)
            .join(Event).join(Member)
            .order_by(Event.date.desc())
            .all()
        )
        def row_dict(r):
            att, evt, mem = r
            return {
                'event_date': evt.date, 'event_type': evt.event_type,
                'event_description': evt.description or '',
                'member_name': mem.name, 'member_callsign': mem.callsign or '',
                'hours': att.hours,
            }
    elif table == 'member_training':
        columns = ['member_name', 'member_email', 'training_type', 'completion_date',
                    'expiration_date', 'certificate_number', 'notes']
        rows = MemberTraining.query.join(Member).order_by(Member.name).all()
        def row_dict(t):
            return {
                'member_name': t.member.name, 'member_email': t.member.email,
                'training_type': t.training_type,
                'completion_date': t.completion_date,
                'expiration_date': t.expiration_date or '',
                'certificate_number': t.certificate_number or '',
                'notes': t.notes or '',
            }
    elif table == 'member_equipment':
        columns = ['member_name', 'member_email', 'equipment_type', 'details']
        rows = MemberEquipmentItem.query.join(Member).join(EquipmentType).order_by(Member.name).all()
        def row_dict(item):
            return {
                'member_name': item.member.name, 'member_email': item.member.email,
                'equipment_type': item.equipment_type.name,
                'details': item.details or '',
            }
    elif table == 'comm_logs':
        columns = ['incident_name', 'activation_number', 'op_period_start', 'op_period_end',
                    'net_name_or_position', 'operator_name', 'operator_callsign',
                    'prepared_by', 'prepared_date']
        rows = CommLog.query.order_by(CommLog.op_period_start.desc()).all()
    elif table == 'comm_log_entries':
        columns = ['incident_name', 'time', 'from_callsign', 'from_msg_num',
                    'to_callsign', 'to_msg_num', 'message']
        rows = CommLogEntry.query.join(CommLog).order_by(CommLog.op_period_start.desc(), CommLogEntry.time).all()
        def row_dict(e):
            return {
                'incident_name': e.comm_log.incident_name,
                'time': e.time, 'from_callsign': e.from_callsign or '',
                'from_msg_num': e.from_msg_num or '',
                'to_callsign': e.to_callsign or '',
                'to_msg_num': e.to_msg_num or '', 'message': e.message or '',
            }
    elif table == 'maintenance_log':
        columns = ['siren_id', 'author', 'note', 'created_at']
        rows = (SirenMaintenanceLog.query
                .join(Siren)
                .order_by(SirenMaintenanceLog.created_at.desc())
                .all())
        def row_dict(entry):
            return {
                'siren_id': entry.siren.siren_id,
                'author': entry.author,
                'note': entry.note,
                'created_at': entry.created_at,
            }
    elif table == 'equipment_types':
        columns = ['name', 'has_details', 'display_order']
        rows = EquipmentType.query.order_by(EquipmentType.display_order).all()
    elif table == 'training_types':
        columns = ['name', 'has_expiration', 'expiration_years', 'display_order']
        rows = TrainingType.query.order_by(TrainingType.display_order).all()
    else:
        flash('Unknown table.', 'danger')
        return redirect(url_for('admin.import_export'))

    # Tables that use custom row_dict
    custom_tables = ('tests', 'assignments', 'attendance', 'member_training',
                     'member_equipment', 'comm_log_entries', 'maintenance_log')

    def _sanitize_row(d):
        return {k: _sanitize_csv_value(v) for k, v in d.items()}

    def generate():
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        for row in rows:
            if table in custom_tables:
                writer.writerow(_sanitize_row(row_dict(row)))
            else:
                writer.writerow(_sanitize_row({c: getattr(row, c) for c in columns}))
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f'arpsc_{table}_{date.today().isoformat()}.csv'
    return Response(
        stream_with_context(generate()),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


# --- CSV Import ---

@admin_bp.route('/import-export')
@admin_required
def import_export():
    return render_template('admin/import_export.html',
                           preview_rows=None, preview_cols=None, import_id=None)


@admin_bp.route('/import/<table>', methods=['POST'])
@admin_required
def import_csv(table):
    allowed = ('sirens', 'tests', 'assignments', 'schedules',
               'members', 'events', 'member_training', 'attendance',
               'maintenance_log')
    if table not in allowed:
        flash('Unknown import type.', 'danger')
        return redirect(url_for('admin.import_export'))

    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a CSV file.', 'danger')
        return redirect(url_for('admin.import_export'))

    try:
        content = file.stream.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        flash('CSV file must be UTF-8 encoded. Open it in Excel/Numbers and "Save As" UTF-8 CSV.', 'danger')
        return redirect(url_for('admin.import_export'))

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        flash('CSV file is empty.', 'warning')
        return redirect(url_for('admin.import_export'))

    # Store in temp file for confirm step. Created AFTER the empty check so an
    # early return doesn't leak the file in /tmp.
    import_id = datetime.now().strftime('%Y%m%d%H%M%S')
    fd, tmp_path = tempfile.mkstemp(suffix='.csv', prefix='sirentracker_import_')
    with os.fdopen(fd, 'w', newline='') as f:
        f.write(content)

    session['import_path'] = tmp_path
    session['import_table'] = table

    return render_template('admin/import_export.html',
                           preview_rows=rows[:50],
                           preview_cols=reader.fieldnames,
                           import_id=import_id,
                           import_table=table)


def _to_bool(val):
    """Convert CSV string to bool."""
    if not val or val.strip() == '':
        return None
    return val.strip().lower() in ('true', '1', 'yes')


@admin_bp.route('/import/confirm', methods=['POST'])
@admin_required
def import_confirm():
    tmp_path = session.pop('import_path', None)
    table = session.pop('import_table', 'sirens')
    if not tmp_path or not os.path.exists(tmp_path):
        flash('Import session expired. Please upload again.', 'warning')
        return redirect(url_for('admin.import_export'))

    with open(tmp_path, 'r') as f:
        reader = csv.DictReader(f)
        added = 0
        updated = 0
        skipped = 0

        if table == 'sirens':
            for row in reader:
                ext_id = row.get('siren_id', '').strip()
                if not ext_id:
                    continue
                existing = Siren.query.filter_by(siren_id=ext_id).first()
                if existing:
                    existing.name = row.get('name', existing.name).strip()
                    existing.location_text = row.get('location_text', existing.location_text)
                    existing.location_url = row.get('location_url', existing.location_url)
                    existing.coordinates = row.get('coordinates', existing.coordinates)
                    existing.year_in_service = row.get('year_in_service', existing.year_in_service)
                    stype = (row.get('siren_type') or '').strip().upper()
                    existing.siren_type = stype if stype in ('FIXED', 'ROTATE') else existing.siren_type
                    if row.get('active', '').strip() != '':
                        existing.active = _to_bool(row['active']) if _to_bool(row['active']) is not None else existing.active
                    if row.get('needs_retest', '').strip() != '':
                        existing.needs_retest = _to_bool(row['needs_retest']) or False
                    updated += 1
                else:
                    stype = (row.get('siren_type') or '').strip().upper()
                    siren = Siren(
                        siren_id=ext_id,
                        name=row.get('name', ext_id).strip(),
                        location_text=row.get('location_text'),
                        location_url=row.get('location_url'),
                        coordinates=row.get('coordinates'),
                        year_in_service=row.get('year_in_service'),
                        siren_type=stype if stype in ('FIXED', 'ROTATE') else 'FIXED',
                        active=_to_bool(row.get('active', 'true')) if row.get('active', '').strip() != '' else True,
                        needs_retest=_to_bool(row.get('needs_retest', 'false')) or False,
                    )
                    db.session.add(siren)
                    added += 1

        elif table == 'tests':
            for row in reader:
                ext_id = row.get('siren_id', '').strip()
                if not ext_id:
                    continue
                siren = Siren.query.filter_by(siren_id=ext_id).first()
                if not siren:
                    skipped += 1
                    continue
                try:
                    test_date_val = date.fromisoformat(row['test_date'].strip())
                except (ValueError, KeyError):
                    skipped += 1
                    continue
                existing = Test.query.filter_by(
                    siren_id=siren.id, test_date=test_date_val).first()
                if existing:
                    skipped += 1
                    continue
                test = Test(
                    siren_id=siren.id,
                    test_date=test_date_val,
                    observer=row.get('observer', 'Unknown').strip(),
                    passed=_to_bool(row.get('passed', 'false')),
                    sound_ok=_to_bool(row.get('sound_ok', 'false')),
                    rotation_ok=_to_bool(row.get('rotation_ok')),
                    vegetation_damage_ok=_to_bool(row.get('vegetation_damage_ok', 'false')),
                    notes=row.get('notes', '').strip() or None,
                )
                db.session.add(test)
                added += 1

        elif table == 'assignments':
            for row in reader:
                ext_id = row.get('siren_id', '').strip()
                if not ext_id:
                    continue
                siren = Siren.query.filter_by(siren_id=ext_id).first()
                if not siren:
                    skipped += 1
                    continue
                try:
                    test_date_val = date.fromisoformat(row['test_date'].strip())
                except (ValueError, KeyError):
                    skipped += 1
                    continue
                assignment = Assignment(
                    siren_id=siren.id,
                    volunteer_name=row.get('volunteer_name', '').strip(),
                    test_date=test_date_val,
                    status=row.get('status', 'CLAIMED').strip().upper()
                           if row.get('status', '').strip().upper() in ('CLAIMED', 'COMPLETED', 'RELEASED')
                           else 'CLAIMED',
                )
                db.session.add(assignment)
                added += 1

        elif table == 'schedules':
            for row in reader:
                try:
                    test_date_val = date.fromisoformat(row['test_date'].strip())
                except (ValueError, KeyError):
                    skipped += 1
                    continue
                existing = TestSchedule.query.filter_by(
                    test_date=test_date_val).first()
                if existing:
                    skipped += 1
                    continue
                test_time = row.get('test_time', '13:00').strip()
                if not re.match(r'^\d{1,2}:\d{2}$', test_time):
                    test_time = '13:00'
                sched = TestSchedule(
                    test_date=test_date_val,
                    test_time=test_time,
                    description=row.get('description', 'Monthly Test').strip(),
                )
                db.session.add(sched)
                added += 1

        elif table == 'members':
            from ..utils import snapshot_member_program_state, stamp_program_audit_dates
            program_bool_cols = (
                'interest_skywarn', 'interest_ares_auxcomm', 'interest_siren_testing',
                'arpsc_active', 'skywarn_active', 'siren_testing_active',
                'can_edit_sirens',
            )
            for row in reader:
                email = (row.get('email') or '').strip().lower()
                if not email:
                    skipped += 1
                    continue
                existing = Member.query.filter(db.func.lower(Member.email) == email).first()
                if existing:
                    prior = snapshot_member_program_state(existing)
                    existing.name = row.get('name', existing.name).strip()
                    existing.callsign = row.get('callsign', existing.callsign or '').strip() or existing.callsign
                    existing.phone = row.get('phone', existing.phone or '').strip() or existing.phone
                    existing.city = row.get('city', existing.city or '').strip() or existing.city
                    existing.state = row.get('state', existing.state or '').strip() or existing.state
                    # Booleans: only apply when the cell is non-empty so a partial
                    # CSV doesn't accidentally clear flags. _to_bool handles
                    # 'true'/'false'/'yes'/'no'/'1'/'0'.
                    for col in program_bool_cols:
                        if row.get(col, '').strip() != '':
                            setattr(existing, col, _to_bool(row[col]) or False)
                    if row.get('active', '').strip() != '':
                        existing.active = _to_bool(row['active']) or False
                    stamp_program_audit_dates(existing, prior)
                    updated += 1
                else:
                    member = Member(
                        name=row.get('name', '').strip() or email,
                        callsign=row.get('callsign', '').strip() or None,
                        email=email,
                        phone=row.get('phone', '').strip() or None,
                        city=row.get('city', '').strip() or None,
                        state=row.get('state', '').strip() or None,
                        interest_skywarn=_to_bool(row.get('interest_skywarn', 'false')) or False,
                        interest_ares_auxcomm=_to_bool(row.get('interest_ares_auxcomm', 'false')) or False,
                        interest_siren_testing=_to_bool(row.get('interest_siren_testing', 'false')) or False,
                        arpsc_active=_to_bool(row.get('arpsc_active', 'false')) or False,
                        skywarn_active=_to_bool(row.get('skywarn_active', 'false')) or False,
                        siren_testing_active=_to_bool(row.get('siren_testing_active', 'false')) or False,
                        can_edit_sirens=_to_bool(row.get('can_edit_sirens', 'false')) or False,
                        active=_to_bool(row.get('active', 'true')) if row.get('active', '').strip() != '' else True,
                    )
                    today = date.today()
                    if member.arpsc_active:
                        member.arpsc_activated_at = today
                    if member.skywarn_active:
                        member.skywarn_activated_at = today
                    if member.siren_testing_active:
                        member.siren_testing_activated_at = today
                    if not member.active:
                        member.archived_at = today
                    db.session.add(member)
                    added += 1

        elif table == 'events':
            for row in reader:
                try:
                    event_date = date.fromisoformat(row['date'].strip())
                except (ValueError, KeyError):
                    skipped += 1
                    continue
                event_type = row.get('event_type', '').strip()
                category = row.get('category', '').strip()
                if not event_type or not category:
                    skipped += 1
                    continue
                event = Event(
                    date=event_date,
                    event_type=event_type,
                    category=category,
                    description=row.get('description', '').strip() or None,
                    duration_hours=float(row.get('duration_hours', 0) or 0),
                    has_nts_liaison=_to_bool(row.get('has_nts_liaison', 'false')),
                )
                db.session.add(event)
                added += 1

        elif table == 'member_training':
            for row in reader:
                email = (row.get('member_email') or '').strip().lower()
                member = Member.query.filter(db.func.lower(Member.email) == email).first() if email else None
                if not member:
                    skipped += 1
                    continue
                training_type = row.get('training_type', '').strip()
                if not training_type:
                    skipped += 1
                    continue
                try:
                    completion = date.fromisoformat(row['completion_date'].strip())
                except (ValueError, KeyError):
                    skipped += 1
                    continue
                exp_str = (row.get('expiration_date') or '').strip()
                expiration = None
                if exp_str:
                    try:
                        expiration = date.fromisoformat(exp_str)
                    except ValueError:
                        pass
                # Auto-compute expiration from TrainingType if not provided
                if not expiration:
                    tt = TrainingType.query.filter_by(name=training_type).first()
                    if tt and tt.has_expiration and tt.expiration_years:
                        from ..utils import add_years
                        expiration = add_years(completion, tt.expiration_years)
                training = MemberTraining(
                    member_id=member.id,
                    training_type=training_type,
                    completion_date=completion,
                    expiration_date=expiration,
                    certificate_number=row.get('certificate_number', '').strip() or None,
                    notes=row.get('notes', '').strip() or None,
                )
                db.session.add(training)
                added += 1

        elif table == 'attendance':
            for row in reader:
                # Match event by date + type + description
                try:
                    event_date = date.fromisoformat(row['event_date'].strip())
                except (ValueError, KeyError):
                    skipped += 1
                    continue
                event_type = row.get('event_type', '').strip()
                event = Event.query.filter_by(date=event_date, event_type=event_type).first()
                if not event:
                    skipped += 1
                    continue
                # Match member by email or name/callsign
                email = (row.get('member_email') or '').strip().lower()
                name = (row.get('member_name') or '').strip()
                callsign = (row.get('member_callsign') or '').strip()
                member = None
                if email:
                    member = Member.query.filter(db.func.lower(Member.email) == email).first()
                if not member and callsign:
                    member = Member.query.filter(db.func.lower(Member.callsign) == callsign.lower()).first()
                if not member and name:
                    member = Member.query.filter(db.func.lower(Member.name) == name.lower()).first()
                if not member:
                    skipped += 1
                    continue
                # Check for duplicate
                existing = EventAttendance.query.filter_by(
                    event_id=event.id, member_id=member.id).first()
                if existing:
                    skipped += 1
                    continue
                hours = float(row.get('hours', 0) or 0)
                att = EventAttendance(
                    event_id=event.id, member_id=member.id, hours=hours,
                )
                db.session.add(att)
                added += 1

        elif table == 'maintenance_log':
            for row in reader:
                ext_id = (row.get('siren_id') or '').strip()
                if not ext_id:
                    skipped += 1
                    continue
                siren = Siren.query.filter_by(siren_id=ext_id).first()
                if not siren:
                    skipped += 1
                    continue
                note_text = (row.get('note') or '').strip()
                if not note_text:
                    skipped += 1
                    continue
                author = (row.get('author') or '').strip() or 'Import'
                created_at = None
                if row.get('created_at', '').strip():
                    try:
                        created_at = datetime.fromisoformat(row['created_at'].strip())
                    except ValueError:
                        pass
                entry = SirenMaintenanceLog(
                    siren_id=siren.id,
                    author=author,
                    note=note_text,
                )
                if created_at:
                    entry.created_at = created_at
                db.session.add(entry)
                added += 1

        db.session.commit()

    os.unlink(tmp_path)
    parts = []
    if added:
        parts.append(f'{added} added')
    if updated:
        parts.append(f'{updated} updated')
    if skipped:
        parts.append(f'{skipped} skipped')
    flash(f'Import complete: {", ".join(parts)}.', 'success')
    return redirect(url_for('admin.import_export'))
