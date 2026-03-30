from datetime import datetime, timezone
from flask_login import UserMixin
from .extensions import db, login_manager


class Siren(db.Model):
    __tablename__ = 'sirens'

    id = db.Column(db.Integer, primary_key=True)
    siren_id = db.Column(db.Text, unique=True, nullable=False)
    name = db.Column(db.Text, nullable=False)
    location_text = db.Column(db.Text)
    location_url = db.Column(db.Text)
    year_in_service = db.Column(db.Text)
    siren_type = db.Column(db.Text, default='FIXED')  # FIXED or ROTATE
    active = db.Column(db.Boolean, default=True)
    needs_retest = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    tests = db.relationship('Test', backref='siren', lazy='dynamic',
                            order_by='Test.test_date.desc()')
    assignments = db.relationship('Assignment', backref='siren', lazy='dynamic')

    def __repr__(self):
        return f'<Siren {self.siren_id}: {self.name}>'


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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Assignment siren={self.siren_id} volunteer={self.volunteer_name}>'


class AdminUser(db.Model, UserMixin):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.Text, unique=True, nullable=False)
    email = db.Column(db.Text, unique=True, nullable=False)
    display_name = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

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


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(AdminUser, int(user_id))
