from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from wtforms.validators import DataRequired, Length, Optional
from .models import User, Choir
from wtforms import StringField, SelectMultipleField, SubmitField

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class AddUserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=80)])
    role = SelectField('Role', choices=[('member', 'Member'), ('organizer', 'Organizer')], default='member', validators=[DataRequired()])
    choirs = QuerySelectMultipleField('Choirs', query_factory=lambda: Choir.query.all(), get_label='name')
    
class ProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=80)])
    dob = DateField('Date of Birth', format='%Y-%m-%d', validators=[Optional()])
    mobile = StringField('Mobile', validators=[Optional(), Length(max=15)])
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField('Password', validators=[Optional(), Length(min=6, max=80)])
    role = SelectField('Role', choices=[('member', 'Member'), ('organizer', 'Organizer')], default='member', validators=[DataRequired()])
    choirs = QuerySelectMultipleField('Choirs', query_factory=lambda: Choir.query.all(), get_label='name')

class AddAttendanceForm(FlaskForm):
    user_id = QuerySelectField(
        'User',
        query_factory=lambda: User.query.all(),
        get_label='name',
        allow_blank=True,
        validators=[DataRequired()]
    )
    choir_id = QuerySelectField(
        'Choir',
        query_factory=lambda: Choir.query.all(),
        get_label='name',
        allow_blank=True,
        validators=[DataRequired()]
    )
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    status = SelectField('Status', choices=[('present', 'Present'), ('absent', 'Absent')], validators=[DataRequired()])
    submit = SubmitField('Add Attendance')

class AttendanceFilterForm(FlaskForm):
    user = QuerySelectField(
        'User',
        query_factory=lambda: User.query.all(),
        get_label='name',
        allow_blank=True
    )
    date = DateField('Date', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Filter')

class AddChoirForm(FlaskForm):
    name = StringField('Choir Name', validators=[DataRequired()])
    members = SelectMultipleField('Members', coerce=int)  # Allow selection of multiple members
    submit = SubmitField('Submit')