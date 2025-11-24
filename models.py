from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin'|'doctor'|'patient'

    doctor = db.relationship('Doctor', backref='user', uselist=False)
    patient = db.relationship('Patient', backref='user', uselist=False)


class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    specialization = db.Column(db.String(120))
    # Human-friendly availability text (fallback)
    availability_text = db.Column(db.String(255))
    # Structured availability: comma-separated short day names e.g. 'Mon,Tue,Wed'
    availability_days = db.Column(db.String(80))
    # Availability time range (HH:MM)
    available_from = db.Column(db.String(5))
    available_to = db.Column(db.String(5))

    appointments = db.relationship('Appointment', backref='doctor', cascade='all, delete-orphan')


class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    contact_no = db.Column(db.String(50))
    age = db.Column(db.Integer)

    appointments = db.relationship('Appointment', backref='patient', cascade='all, delete-orphan')


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    time = db.Column(db.String(5), nullable=False)   # HH:MM
    status = db.Column(db.String(20), default='Booked')
    notes = db.Column(db.Text)

    treatment = db.relationship('Treatment', backref='appointment', uselist=False, cascade='all, delete-orphan')


class Treatment(db.Model):
    __tablename__ = 'treatments'
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    diagnosis = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
