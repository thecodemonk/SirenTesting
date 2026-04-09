from datetime import date, datetime, timedelta, timezone
from flask_login import UserMixin
from .extensions import db, login_manager


class Siren(db.Model):
    __tablename__ = 'sirens'

    id = db.Column(db.Integer, primary_key=True)
    siren_id = db.Column(db.Text, unique=True, nullable=False)
    name = db.Column(db.Text, nullable=False)
    location_text = db.Column(db.Text)
    location_url = db.Column(db.Text)
    coordinates = db.Column(db.Text)  # lat,lng e.g. "42.9634,-82.4368"
    year_in_service = db.Column(db.Text)
    siren_type = db.Column(db.Text, default='FIXED')  # FIXED or ROTATE
    active = db.Column(db.Boolean, default=True)
    needs_retest = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    tests = db.relationship('Test', backref='siren', lazy='select',
                            order_by='Test.test_date.desc()')
    assignments = db.relationship('Assignment', backref='siren', lazy='select')

    maintenance_log = db.relationship('SirenMaintenanceLog', backref='siren', lazy='select',
                                      order_by='SirenMaintenanceLog.created_at.desc()')

    def __repr__(self):
        return f'<Siren {self.siren_id}: {self.name}>'


class SirenMaintenanceLog(db.Model):
    __tablename__ = 'siren_maintenance_log'

    id = db.Column(db.Integer, primary_key=True)
    siren_id = db.Column(db.Integer, db.ForeignKey('sirens.id'), nullable=False, index=True)
    author = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Test(db.Model):
    __tablename__ = 'tests'

    id = db.Column(db.Integer, primary_key=True)
    siren_id = db.Column(db.Integer, db.ForeignKey('sirens.id'), nullable=False)
    test_date = db.Column(db.Date, nullable=False)
    observer = db.Column(db.Text, nullable=False)
    passed = db.Column(db.Boolean, nullable=False)
    sound_ok = db.Column(db.Boolean, nullable=False)
    rotation_ok = db.Column(db.Boolean, nullable=True)  # NULL for FIXED type
    vegetation_damage_ok = db.Column(db.Boolean, nullable=False)
    notes = db.Column(db.Text)
    photo_filename = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.Index('ix_tests_siren_date', 'siren_id', 'test_date'),
    )

    def __repr__(self):
        return f'<Test siren={self.siren_id} date={self.test_date} passed={self.passed}>'


class Assignment(db.Model):
    __tablename__ = 'assignments'

    id = db.Column(db.Integer, primary_key=True)
    siren_id = db.Column(db.Integer, db.ForeignKey('sirens.id'), nullable=False)
    volunteer_name = db.Column(db.Text, nullable=False)
    test_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Text, default='CLAIMED')  # CLAIMED / COMPLETED / RELEASED
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    member = db.relationship('Member', backref='assignments')

    def __repr__(self):
        return f'<Assignment siren={self.siren_id} volunteer={self.volunteer_name}>'


class AdminUser(db.Model, UserMixin):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.Text, unique=True, nullable=False)
    email = db.Column(db.Text, unique=True, nullable=False)
    display_name = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def get_id(self):
        return f'admin:{self.id}'

    def __repr__(self):
        return f'<AdminUser {self.email}>'


class TestSchedule(db.Model):
    __tablename__ = 'test_schedules'

    id = db.Column(db.Integer, primary_key=True)
    test_date = db.Column(db.Date, nullable=False)
    test_time = db.Column(db.Text, default='13:00')
    description = db.Column(db.Text, default='Monthly Test')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<TestSchedule {self.test_date} {self.description}>'


# --- Member Management ---

class Member(db.Model, UserMixin):
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    callsign = db.Column(db.Text)
    email = db.Column(db.Text, unique=True, nullable=False)
    phone = db.Column(db.Text)
    street = db.Column(db.Text)
    city = db.Column(db.Text)
    state = db.Column(db.Text)
    zip_code = db.Column(db.Text)
    country = db.Column(db.Text, default='US')
    emergency_contact = db.Column(db.Text)
    preferred_comm = db.Column(db.Text, default='email')  # call, text, email
    phone_privacy = db.Column(db.Boolean, default=True)
    # Member-controlled program interests (self-service via profile)
    interest_skywarn = db.Column(db.Boolean, default=False)
    interest_ares_auxcomm = db.Column(db.Boolean, default=False)
    interest_siren_testing = db.Column(db.Boolean, default=False)
    # Admin-controlled program active flags — gate state report counts and pickers
    arpsc_active = db.Column(db.Boolean, default=False)
    skywarn_active = db.Column(db.Boolean, default=False)
    siren_testing_active = db.Column(db.Boolean, default=False)
    # Audit timestamps so historical state reports remain accurate after toggles
    arpsc_activated_at = db.Column(db.Date)
    arpsc_deactivated_at = db.Column(db.Date)
    skywarn_activated_at = db.Column(db.Date)
    skywarn_deactivated_at = db.Column(db.Date)
    siren_testing_activated_at = db.Column(db.Date)
    siren_testing_deactivated_at = db.Column(db.Date)
    background_check = db.Column(db.Boolean, default=False)
    mi_volunteer_registry = db.Column(db.Boolean, default=False)
    # Member permissions (admin-controlled)
    can_edit_sirens = db.Column(db.Boolean, default=False)
    # Overall record status — False means archived (left org / deceased)
    active = db.Column(db.Boolean, default=True)
    archived_at = db.Column(db.Date)
    last_active_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    equipment_items = db.relationship('MemberEquipmentItem', backref='member', lazy='select',
                                      cascade='all, delete-orphan')
    trainings = db.relationship('MemberTraining', backref='member', lazy='select',
                                order_by='MemberTraining.completion_date.desc()')
    event_attendance = db.relationship('EventAttendance', backref='member', lazy='select')
    task_book_progress = db.relationship('MemberTaskBookProgress',
                                         foreign_keys='MemberTaskBookProgress.member_id',
                                         backref='member', lazy='select')

    def get_id(self):
        return f'member:{self.id}'

    def __repr__(self):
        return f'<Member {self.callsign or self.name}>'


class EquipmentType(db.Model):
    __tablename__ = 'equipment_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    has_details = db.Column(db.Boolean, default=False)  # show a details/notes field
    display_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<EquipmentType {self.name}>'


class MemberEquipmentItem(db.Model):
    __tablename__ = 'member_equipment_items'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    equipment_type_id = db.Column(db.Integer, db.ForeignKey('equipment_types.id'), nullable=False)
    details = db.Column(db.Text)  # e.g. "50W", "4 hours", free text

    equipment_type = db.relationship('EquipmentType', lazy='select')

    __table_args__ = (
        db.UniqueConstraint('member_id', 'equipment_type_id', name='uq_member_equipment'),
    )


class TrainingType(db.Model):
    __tablename__ = 'training_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    has_expiration = db.Column(db.Boolean, default=False)
    expiration_years = db.Column(db.Integer)  # NULL if no expiration
    display_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<TrainingType {self.name}>'


class MemberTraining(db.Model):
    __tablename__ = 'member_trainings'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)
    training_type = db.Column(db.Text, nullable=False)
    completion_date = db.Column(db.Date, nullable=False)
    expiration_date = db.Column(db.Date)  # NULL = never expires
    certificate_number = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self):
        if self.expiration_date is None:
            return False
        return self.expiration_date < date.today()

    @property
    def is_expiring_soon(self):
        if self.expiration_date is None:
            return False
        return (not self.is_expired and
                self.expiration_date <= date.today() + timedelta(days=90))

    @property
    def status(self):
        if self.is_expired:
            return 'expired'
        if self.is_expiring_soon:
            return 'expiring_soon'
        return 'current'


# --- Task Books ---

class TaskBookLevel(db.Model):
    __tablename__ = 'task_book_levels'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    tasks = db.relationship('TaskBookTask', backref='level', lazy='select',
                            order_by='TaskBookTask.display_order',
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<TaskBookLevel {self.name}>'


class TaskBookTask(db.Model):
    __tablename__ = 'task_book_tasks'

    id = db.Column(db.Integer, primary_key=True)
    level_id = db.Column(db.Integer, db.ForeignKey('task_book_levels.id'), nullable=False)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)

    progress = db.relationship('MemberTaskBookProgress', backref='task', lazy='select',
                               cascade='all, delete-orphan')

    def __repr__(self):
        return f'<TaskBookTask {self.name}>'


class MemberTaskBookProgress(db.Model):
    __tablename__ = 'member_task_book_progress'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task_book_tasks.id'), nullable=False)
    completed_date = db.Column(db.Date)
    officer1_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    officer2_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    officer1 = db.relationship('Member', foreign_keys=[officer1_id])
    officer2 = db.relationship('Member', foreign_keys=[officer2_id])

    __table_args__ = (
        db.UniqueConstraint('member_id', 'task_id', name='uq_member_task'),
    )


# --- Events & Attendance ---

class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    event_type = db.Column(db.Text, nullable=False)
    category = db.Column(db.Text, nullable=False, index=True)  # ARPSC, SKYWARN, Siren Test
    description = db.Column(db.Text)
    duration_hours = db.Column(db.Float, default=0)
    has_nts_liaison = db.Column(db.Boolean, default=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    siren_test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    attendance = db.relationship('EventAttendance', backref='event', lazy='select',
                                 cascade='all, delete-orphan')
    created_by = db.relationship('AdminUser', backref='events_created')
    siren_test = db.relationship('Test', backref='event')
    comm_logs = db.relationship('CommLog', backref='event', lazy='select')

    @property
    def total_person_hours(self):
        return sum(a.hours for a in self.attendance)

    @property
    def participant_count(self):
        return len(self.attendance)

    def __repr__(self):
        return f'<Event {self.date} {self.event_type}>'


class EventAttendance(db.Model):
    __tablename__ = 'event_attendance'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)
    hours = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('event_id', 'member_id', name='uq_event_member'),
    )


# --- ICS-309 Comm Logs ---

class CommLog(db.Model):
    __tablename__ = 'comm_logs'

    id = db.Column(db.Integer, primary_key=True)
    incident_name = db.Column(db.Text, nullable=False)
    activation_number = db.Column(db.Text)
    op_period_start = db.Column(db.DateTime, nullable=False)
    op_period_end = db.Column(db.DateTime, nullable=False)
    net_name_or_position = db.Column(db.Text)
    operator_name = db.Column(db.Text, nullable=False)
    operator_callsign = db.Column(db.Text)
    prepared_by = db.Column(db.Text)
    prepared_date = db.Column(db.Date)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    entries = db.relationship('CommLogEntry', backref='comm_log', lazy='select',
                              order_by='CommLogEntry.time',
                              cascade='all, delete-orphan')

    def __repr__(self):
        return f'<CommLog {self.incident_name}>'


class CommLogEntry(db.Model):
    __tablename__ = 'comm_log_entries'

    id = db.Column(db.Integer, primary_key=True)
    comm_log_id = db.Column(db.Integer, db.ForeignKey('comm_logs.id'), nullable=False, index=True)
    time = db.Column(db.DateTime, nullable=False)
    from_callsign = db.Column(db.Text)
    from_msg_num = db.Column(db.Text)
    to_callsign = db.Column(db.Text)
    to_msg_num = db.Column(db.Text)
    message = db.Column(db.Text)

    def __repr__(self):
        return f'<CommLogEntry {self.time} {self.from_callsign}>'


# --- User loader for dual auth ---

@login_manager.user_loader
def load_user(user_id):
    """Sessions store IDs as 'admin:N' or 'member:N'. AdminUser.get_id() and
    Member.get_id() always emit one of those prefixes, so any other value
    means a stale or tampered cookie — return None to force re-auth."""
    user_id = str(user_id)
    if user_id.startswith('admin:'):
        return db.session.get(AdminUser, int(user_id.split(':')[1]))
    if user_id.startswith('member:'):
        return db.session.get(Member, int(user_id.split(':')[1]))
    return None
