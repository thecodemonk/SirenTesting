from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, SelectField, BooleanField, TextAreaField, DateField,
)
from wtforms.validators import DataRequired, Length, Optional


class SirenForm(FlaskForm):
    siren_id = StringField('Siren ID', validators=[DataRequired(), Length(max=20)])
    name = StringField('Name', validators=[DataRequired(), Length(max=200)])
    location_text = StringField('Location', validators=[Optional(), Length(max=500)])
    location_url = StringField('Map Link', validators=[Optional(), Length(max=1000)])
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
