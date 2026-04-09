from datetime import date, timedelta

from flask import render_template, request, flash, redirect, url_for
from flask_login import current_user

from . import members_bp
from .decorators import member_required, siren_editor_required
from .forms import ProfileForm, TrainingForm, SirenEditForm, MaintenanceNoteForm
from ..extensions import db
from ..models import (
    Member, MemberEquipmentItem, EquipmentType, MemberTraining, TrainingType,
    EventAttendance, Event, TaskBookLevel, MemberTaskBookProgress,
    Siren, SirenMaintenanceLog,
)


@members_bp.route('/profile', methods=['GET', 'POST'])
@member_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        form.populate_obj(current_user)
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('members.profile'))
    return render_template('members/profile.html', form=form)


@members_bp.route('/equipment', methods=['GET', 'POST'])
@member_required
def equipment():
    equipment_types = EquipmentType.query.order_by(EquipmentType.display_order).all()

    if request.method == 'POST':
        # Clear existing items and rebuild from form
        MemberEquipmentItem.query.filter_by(member_id=current_user.id).delete()
        for et in equipment_types:
            checkbox_key = f'equip_{et.id}'
            details_key = f'details_{et.id}'
            if checkbox_key in request.form:
                item = MemberEquipmentItem(
                    member_id=current_user.id,
                    equipment_type_id=et.id,
                    details=request.form.get(details_key, '').strip() or None,
                )
                db.session.add(item)
        db.session.commit()
        flash('Equipment updated.', 'success')
        return redirect(url_for('members.equipment'))

    # Build lookup of current items
    current_items = {item.equipment_type_id: item for item in current_user.equipment_items}
    return render_template('members/equipment.html',
                           equipment_types=equipment_types, current_items=current_items)


@members_bp.route('/training')
@member_required
def training():
    trainings = MemberTraining.query.filter_by(
        member_id=current_user.id
    ).order_by(MemberTraining.completion_date.desc()).all()
    training_types = TrainingType.query.order_by(TrainingType.display_order).all()
    form = TrainingForm()
    # Populate choices from DB
    form.training_type.choices = [(t.name, t.name) for t in training_types] + [('Other', 'Other')]
    # Build expiration map for JS
    exp_map = {t.name: t.expiration_years for t in training_types if t.has_expiration and t.expiration_years}
    return render_template('members/training.html', trainings=trainings, form=form, exp_map=exp_map)


@members_bp.route('/training/add', methods=['POST'])
@member_required
def training_add():
    training_types = TrainingType.query.order_by(TrainingType.display_order).all()
    form = TrainingForm()
    form.training_type.choices = [(t.name, t.name) for t in training_types] + [('Other', 'Other')]

    if form.validate_on_submit():
        training_type = form.training_type.data
        if training_type == 'Other' and form.custom_type.data:
            training_type = form.custom_type.data.strip()

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
                expiration_date = add_years(form.completion_date.data, tt.expiration_years)

        training = MemberTraining(
            member_id=current_user.id,
            training_type=training_type,
            completion_date=form.completion_date.data,
            expiration_date=expiration_date,
            certificate_number=form.certificate_number.data.strip() if form.certificate_number.data else None,
            notes=form.notes.data.strip() if form.notes.data else None,
        )
        db.session.add(training)
        db.session.commit()
        flash(f'{training_type} training record added.', 'success')
    else:
        flash('Please fix the errors below.', 'danger')
    return redirect(url_for('members.training'))


@members_bp.route('/training/<int:id>/delete', methods=['POST'])
@member_required
def training_delete(id):
    training = MemberTraining.query.filter_by(
        id=id, member_id=current_user.id
    ).first_or_404()
    db.session.delete(training)
    db.session.commit()
    flash('Training record removed.', 'info')
    return redirect(url_for('members.training'))


@members_bp.route('/taskbooks')
@member_required
def taskbooks():
    levels = TaskBookLevel.query.order_by(TaskBookLevel.display_order).all()

    # Build progress lookup: {task_id: MemberTaskBookProgress}
    progress_records = MemberTaskBookProgress.query.filter_by(
        member_id=current_user.id
    ).all()
    progress_map = {p.task_id: p for p in progress_records}

    return render_template('members/taskbooks.html',
                           levels=levels, progress_map=progress_map)


@members_bp.route('/activity')
@member_required
def activity():
    records = (
        db.session.query(EventAttendance, Event)
        .join(Event)
        .filter(EventAttendance.member_id == current_user.id)
        .order_by(Event.date.desc())
        .all()
    )
    return render_template('members/activity.html', records=records)


# --- Siren Management (requires can_edit_sirens permission) ---

@members_bp.route('/sirens')
@siren_editor_required
def sirens():
    from ..utils import get_all_siren_statuses
    all_sirens = Siren.query.order_by(Siren.siren_id).all()
    statuses, last_tests = get_all_siren_statuses(all_sirens)
    return render_template('members/sirens.html', sirens=all_sirens,
                           statuses=statuses, last_tests=last_tests)


@members_bp.route('/sirens/<int:id>/edit', methods=['GET', 'POST'])
@siren_editor_required
def siren_edit(id):
    from flask import abort
    siren = db.session.get(Siren, id) or abort(404)
    form = SirenEditForm(obj=siren)
    note_form = MaintenanceNoteForm()

    if form.validate_on_submit() and 'save_siren' in request.form:
        siren.active = form.active.data
        siren.needs_retest = form.needs_retest.data
        db.session.commit()
        flash(f'Siren {siren.siren_id} updated.', 'success')
        return redirect(url_for('members.siren_edit', id=id))

    return render_template('members/siren_edit.html', siren=siren,
                           form=form, note_form=note_form)


@members_bp.route('/sirens/<int:id>/notes', methods=['POST'])
@siren_editor_required
def siren_add_note(id):
    from flask import abort
    siren = db.session.get(Siren, id) or abort(404)
    form = MaintenanceNoteForm()
    if form.validate_on_submit():
        log = SirenMaintenanceLog(
            siren_id=siren.id,
            author=current_user.name,
            note=form.note.data.strip(),
        )
        db.session.add(log)
        db.session.commit()
        flash('Maintenance note added.', 'success')
    return redirect(url_for('members.siren_edit', id=id))
