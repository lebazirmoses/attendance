from . import db
from flask_login import UserMixin
import uuid

from . import db
from flask_login import UserMixin
import uuid

# Define association table for the many-to-many relationship
user_choir_association = db.Table(
    'user_choir_association',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('choir_id', db.Integer, db.ForeignKey('choirs.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.String(36), unique=True, nullable=False, default=str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    dob = db.Column(db.Date, nullable=True)
    mobile = db.Column(db.String(15), nullable=True)
    role = db.Column(db.String(10), nullable=False, default="member")
    
    attendances = db.relationship('Attendance', back_populates='user')
    choirs = db.relationship('Choir', secondary=user_choir_association, back_populates='members')

class Choir(db.Model):
    __tablename__ = 'choirs'
    id = db.Column(db.Integer, primary_key=True)
    choir_id = db.Column(db.String(36), unique=True, nullable=False, default=str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    
    attendances = db.relationship('Attendance', back_populates='choir')
    members = db.relationship('User', secondary=user_choir_association, back_populates='choirs')


class Attendance(db.Model):
    __tablename__ = 'attendances'  # Specify the table name explicitly
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Change to 'users.id'
    choir_id = db.Column(db.Integer, db.ForeignKey('choirs.id'))  # Change to 'choirs.id'
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False)

    user = db.relationship('User', back_populates='attendances')
    choir = db.relationship('Choir', back_populates='attendances')
