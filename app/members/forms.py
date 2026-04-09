from flask_wtf import FlaskForm
from wtforms import (
    StringField, BooleanField, TextAreaField, SelectField,
    SelectMultipleField, DateField, HiddenField,
)
from wtforms.validators import DataRequired, Email, Length, Optional
from wtforms.widgets import CheckboxInput, ListWidget


class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])


class VerifyForm(FlaskForm):
    code = StringField('6-Digit Code', validators=[DataRequired(), Length(min=6, max=6)])


class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=200)])
    callsign = StringField('Call Sign (Ham or GMRS)', validators=[Optional(), Length(max=20)])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    street = StringField('Street Address', validators=[Optional(), Length(max=200)])
    city = StringField('City', validators=[Optional(), Length(max=100)])
    state = StringField('State', validators=[Optional(), Length(max=50)])
    zip_code = StringField('ZIP Code', validators=[Optional(), Length(max=20)])
    country = StringField('Country', validators=[Optional(), Length(max=100)], default='US')
    emergency_contact = StringField('Emergency Contact (name & phone)',
                                    validators=[Optional(), Length(max=200)])
    preferred_comm = SelectField('Preferred Communication',
                                 choices=[('email', 'Email'), ('call', 'Call'), ('text', 'Text')])
    phone_privacy = BooleanField('Keep my phone number private', default=True)
    interest_skywarn = BooleanField('SKYWARN')
    interest_ares_auxcomm = BooleanField('ARES / AUXCOMM')
    interest_siren_testing = BooleanField('Siren Testing')


class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=200)])
    callsign = StringField('Call Sign', validators=[Optional(), Length(max=20)])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    street = StringField('Street Address', validators=[Optional(), Length(max=200)])
    city = StringField('City', validators=[Optional(), Length(max=100)])
    state = StringField('State', validators=[Optional(), Length(max=50)])
    zip_code = StringField('ZIP Code', validators=[Optional(), Length(max=20)])
    country = StringField('Country', validators=[Optional(), Length(max=100)])
    emergency_contact = StringField('Emergency Contact',
                                    validators=[Optional(), Length(max=200)])
    preferred_comm = SelectField('Preferred Communication',
                                 choices=[('email', 'Email'), ('call', 'Call'), ('text', 'Text')])
    phone_privacy = BooleanField('Keep my phone number private')
    interest_skywarn = BooleanField('SKYWARN')
    interest_ares_auxcomm = BooleanField('ARES / AUXCOMM')
    interest_siren_testing = BooleanField('Siren Testing')


class SirenEditForm(FlaskForm):
    """Limited siren edit form for members with can_edit_sirens permission."""
    active = BooleanField('Active')
    needs_retest = BooleanField('Needs Retest')


class MaintenanceNoteForm(FlaskForm):
    note = TextAreaField('Note', validators=[DataRequired(), Length(max=2000)])


class TrainingForm(FlaskForm):
    training_type = SelectField('Training Type', choices=[
        ('IS-100', 'IS-100'), ('IS-200', 'IS-200'),
        ('IS-700', 'IS-700'), ('IS-800', 'IS-800'),
        ('ICS-300', 'ICS-300'), ('ICS-400', 'ICS-400'),
        ('EC-001', 'EC-001'), ('EC-016', 'EC-016'),
        ('AUXCOMM', 'AUXCOMM'), ('SKYWARN', 'SKYWARN'),
        ('Other', 'Other'),
    ], validators=[DataRequired()])
    custom_type = StringField('Custom Training Name', validators=[Optional(), Length(max=200)])
    completion_date = DateField('Completion Date', validators=[DataRequired()])
    certificate_number = StringField('Certificate Number',
                                     validators=[Optional(), Length(max=100)])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])
