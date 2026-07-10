from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, SelectField, TextAreaField, HiddenField, DateTimeLocalField,
)
from wtforms.validators import DataRequired, Length, Optional

DAMAGE_TYPES = [
    ('Wind', 'Wind'),
    ('Hail', 'Hail'),
    ('Tornado', 'Tornado / Funnel Cloud'),
    ('Flooding', 'Flooding'),
    ('Structure', 'Structure Damage'),
    ('Tree', 'Downed Tree / Debris'),
    ('Power', 'Power Lines Down'),
    ('Other', 'Other'),
]


class DamageReportForm(FlaskForm):
    reporter_name = StringField('Your Name / Callsign',
                                validators=[DataRequired(), Length(max=100)])
    damage_type = SelectField('Type of Damage', choices=DAMAGE_TYPES,
                              validators=[DataRequired()])
    occurred_at = DateTimeLocalField('When (approx.)', format='%Y-%m-%dT%H:%M',
                                     validators=[Optional()])
    location_text = StringField('Location description',
                                validators=[Optional(), Length(max=300)])
    # Set by the map picker / browser geolocation; "lat,lng"
    coordinates = HiddenField()
    description = TextAreaField('What are you seeing?',
                               validators=[Optional(), Length(max=2000)])
    photo = FileField('Photo', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic'], 'Images only')
    ])
    # Honeypot — should be left empty by humans
    website = HiddenField()
