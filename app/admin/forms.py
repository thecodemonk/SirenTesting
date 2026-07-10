from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, SelectField, BooleanField, TextAreaField, DateField,
    FloatField, DateTimeLocalField, IntegerField,
)
from wtforms.validators import DataRequired, Length, Optional, Regexp, NumberRange


class SirenForm(FlaskForm):
    siren_id = StringField('Siren ID', validators=[DataRequired(), Length(max=20)])
    name = StringField('Name', validators=[DataRequired(), Length(max=200)])
    location_text = StringField('Location', validators=[Optional(), Length(max=500)])
    location_url = StringField('Map Link', validators=[
        Optional(), Length(max=1000),
        Regexp(r'^https?://', message='Must be an http:// or https:// URL')
    ])
    coordinates = StringField('GPS Coordinates', validators=[Optional(), Length(max=50)])
    year_in_service = StringField('Year in Service', validators=[Optional(), Length(max=20)])
    siren_type = SelectField('Type', choices=[('FIXED', 'Fixed'), ('ROTATE', 'Rotate')])
    active = BooleanField('Active', default=True)
    needs_retest = BooleanField('Needs Retest')


class TestForm(FlaskForm):
    siren_id = SelectField('Siren', coerce=int, validators=[DataRequired()])
    test_date = DateField('Test Date', validators=[DataRequired()])
    observer = StringField('Observer', validators=[DataRequired(), Length(max=100)])
    passed = BooleanField('Passed')
    sound_ok = BooleanField('Sound')
    rotation_ok = BooleanField('Rotation')
    vegetation_damage_ok = BooleanField('Vegetation and/or Damage')
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=2000)])
    photo = FileField('Test Photo', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic'], 'Images only')
    ])


class AssignmentForm(FlaskForm):
    siren_id = SelectField('Siren', coerce=int, validators=[DataRequired()])
    volunteer_name = StringField('Volunteer Name / Callsign', validators=[DataRequired(), Length(max=100)])
    test_date = SelectField('Test Date', validators=[DataRequired()])


# --- Events ---

class EventForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    event_type = SelectField('Type', choices=[
        ('Meeting', 'Meeting'),
        ('Net', 'Net'),
        ('Info Net', 'Info Net'),
        ('Simplex Net', 'Simplex Net'),
        ('Training', 'Training'),
        ('Exercise', 'Exercise'),
        ('Public Service Event', 'Public Service Event'),
        ('Public Safety Incident', 'Public Safety Incident'),
        ('SKYWARN Activation', 'SKYWARN Activation'),
        ('Deployment', 'Deployment'),
        ('Siren Test', 'Siren Test'),
        ('General/Misc', 'General/Misc'),
    ], validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('ARPSC', 'ARPSC'),
        ('SKYWARN', 'SKYWARN'),
        ('Siren Test', 'Siren Test'),
    ], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    duration_hours = FloatField('Default Duration (hours)', validators=[
        DataRequired(), NumberRange(min=0, max=72)
    ], default=1.0)
    has_nts_liaison = BooleanField('Had NTS Liaison')


# --- Comm Logs ---

class CommLogForm(FlaskForm):
    incident_name = StringField('Incident Name', validators=[DataRequired(), Length(max=200)])
    activation_number = StringField('Activation Number', validators=[Optional(), Length(max=50)])
    op_period_start = DateTimeLocalField('Op Period Start', format='%Y-%m-%dT%H:%M',
                                         validators=[DataRequired()])
    op_period_end = DateTimeLocalField('Op Period End', format='%Y-%m-%dT%H:%M',
                                       validators=[DataRequired()])
    net_name_or_position = StringField('Net Name / Position / Tactical Call',
                                       validators=[Optional(), Length(max=200)])
    operator_name = StringField('Radio Operator Name', validators=[DataRequired(), Length(max=100)])
    operator_callsign = StringField('Radio Operator Call Sign',
                                     validators=[Optional(), Length(max=20)])
    prepared_by = StringField('Prepared By', validators=[Optional(), Length(max=100)])
    prepared_date = DateField('Date Prepared', validators=[Optional()])
    event_id = SelectField('Link to Event', coerce=int, validators=[Optional()])


class CommLogEntryForm(FlaskForm):
    time = DateTimeLocalField('Time', format='%Y-%m-%dT%H:%M',
                               validators=[DataRequired()])
    from_callsign = StringField('From Call Sign', validators=[Optional(), Length(max=20)])
    from_msg_num = StringField('From Msg #', validators=[Optional(), Length(max=20)])
    to_callsign = StringField('To Call Sign', validators=[Optional(), Length(max=20)])
    to_msg_num = StringField('To Msg #', validators=[Optional(), Length(max=20)])
    message = TextAreaField('Message', validators=[Optional(), Length(max=2000)])


# --- Members Admin ---

class MemberAdminForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=200)])
    callsign = StringField('Call Sign', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Length(max=200)])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    street = StringField('Street', validators=[Optional(), Length(max=200)])
    city = StringField('City', validators=[Optional(), Length(max=100)])
    state = StringField('State', validators=[Optional(), Length(max=50)])
    zip_code = StringField('ZIP Code', validators=[Optional(), Length(max=20)])
    country = StringField('Country', validators=[Optional(), Length(max=100)])
    emergency_contact = StringField('Emergency Contact', validators=[Optional(), Length(max=200)])
    preferred_comm = SelectField('Preferred Comm',
                                 choices=[('email', 'Email'), ('call', 'Call'), ('text', 'Text')])
    phone_privacy = BooleanField('Phone Privacy')
    # Member-controlled interest flags
    interest_skywarn = BooleanField('SKYWARN')
    interest_ares_auxcomm = BooleanField('ARES / AUXCOMM')
    interest_siren_testing = BooleanField('Siren Testing')
    # Admin-controlled program active flags — these gate state report counts and pickers
    arpsc_active = BooleanField('ARPSC Active')
    skywarn_active = BooleanField('SKYWARN Active')
    siren_testing_active = BooleanField('Siren Testing Active')
    background_check = BooleanField('Background Check')
    mi_volunteer_registry = BooleanField('MI Volunteer Registry')
    can_edit_sirens = BooleanField('Can Edit Sirens')
    active = BooleanField('Active (not archived)')
    notes = TextAreaField('Admin Notes', validators=[Optional(), Length(max=2000)])


# --- Task Books ---

class TaskBookLevelForm(FlaskForm):
    name = StringField('Level Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    display_order = IntegerField('Display Order', validators=[Optional()], default=0)


class TaskBookTaskForm(FlaskForm):
    name = StringField('Task Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    display_order = IntegerField('Display Order', validators=[Optional()], default=0)


class StormForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=200)])
    event_date = DateField('Date', validators=[DataRequired()])
    nws_event_type = StringField('NWS Event Type', validators=[Optional(), Length(max=100)])
    status = SelectField('Status', choices=[('ACTIVE', 'Active'), ('ARCHIVED', 'Archived')])
    center_coordinates = StringField('Map Center (lat,lng)', validators=[Optional(), Length(max=50)])
    # Optional link to an Event so SkyWarn activations flow to the state report
    event_id = SelectField('Linked Event', coerce=int, validators=[Optional()])
    summary = TextAreaField('Summary', validators=[Optional(), Length(max=4000)])
    # SkyWarn Work Sheet header
    net_control_name = StringField('Net Control Name', validators=[Optional(), Length(max=100)])
    net_control_callsign = StringField('Callsign', validators=[Optional(), Length(max=20)])
    freq_main = StringField('Main Freq.', validators=[Optional(), Length(max=60)])
    freq_north = StringField('North Freq.', validators=[Optional(), Length(max=60)])
    freq_south = StringField('South Freq.', validators=[Optional(), Length(max=60)])
    freq_dtx = StringField('DTX Tx', validators=[Optional(), Length(max=60)])


NET_CONDITIONS = [
    ('Standby', 'Standby'), ('Green', 'Green'), ('Yellow', 'Yellow'),
    ('Red', 'Red'), ('Close', 'Close'),
]
STATION_ROLES = [
    ('Spotter', 'Spotter'), ('MICON liaison', 'MICON liaison'),
    ('NWSchat', 'NWSchat'), ('Radar', 'Radar'), ('GroupMe', 'GroupMe'),
    ('NCS', 'NCS'),
]
PASSED_VIA = [
    ('', '—'), ('NWS', 'NWS'), ('HSEM', 'HSEM'), ('NWSchat', 'NWSchat'),
    ('GroupMe', 'GroupMe'), ('Phone', 'Phone'), ('Other', 'Other'),
]


class WatchWarningForm(FlaskForm):
    tsm_watch = BooleanField('TSM Watch')
    tsm_warning = BooleanField('TSM Warning')
    tdo_watch = BooleanField('TDO Watch')
    tdo_warning = BooleanField('TDO Warning')
    county = StringField('County', validators=[Optional(), Length(max=60)])
    start_time = StringField('Start', validators=[Optional(), Length(max=20)])
    end_time = StringField('End', validators=[Optional(), Length(max=20)])


class NetConditionForm(FlaskForm):
    condition = SelectField('Condition', choices=NET_CONDITIONS, validators=[DataRequired()])
    reason = StringField('Reason', validators=[Optional(), Length(max=300)])
    time = StringField('Time', validators=[Optional(), Length(max=20)])


class NetStationForm(FlaskForm):
    role = SelectField('Role', choices=STATION_ROLES, validators=[DataRequired()])
    station = StringField('Station', validators=[DataRequired(), Length(max=30)])
    location = StringField('Location', validators=[Optional(), Length(max=200)])
    time_in = StringField('In', validators=[Optional(), Length(max=20)])
    time_out = StringField('Out', validators=[Optional(), Length(max=20)])


class AdminDamageReportForm(FlaskForm):
    """Admin entry of storm damage relayed through a net (T-E-L format)."""
    reporter_name = StringField('Station / Reporter', validators=[DataRequired(), Length(max=100)])
    occurred_at = DateTimeLocalField('Time', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    damage_type = SelectField('Effect', validators=[DataRequired()])
    location_text = StringField('Location', validators=[Optional(), Length(max=300)])
    passed_via = SelectField('Passed Via', choices=PASSED_VIA, validators=[Optional()])
    description = TextAreaField('Details', validators=[Optional(), Length(max=2000)])
