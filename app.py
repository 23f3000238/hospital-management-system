import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Doctor, Patient, Appointment, Treatment
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'hms.db')


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev-secret-key-change-me'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_PATH
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)


    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))


    # Ensure DB directory exists and create tables/seeds immediately.
    # Some Flask versions may not provide `before_first_request` as a decorator,
    # so call the create_tables function directly to guarantee DB initialization.
    os.makedirs(DATA_DIR, exist_ok=True)
    create_tables(app)


    # ---------- Public Routes ----------
    @app.route('/')
    def index():
        return render_template('index.html')


    # ---------- Auth Routes ----------
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            contact_no = request.form.get('contact_no')
            age = request.form.get('age')

            if not (name and email and password):
                flash('Please provide name, email and password', 'danger')
                return redirect(url_for('register'))

            existing = User.query.filter_by(email=email).first()
            if existing:
                flash('Email already registered', 'warning')
                return redirect(url_for('register'))

            password_hash = generate_password_hash(password)
            user = User(name=name, email=email, password_hash=password_hash, role='patient')
            db.session.add(user)
            db.session.commit()

            patient = Patient(user_id=user.id, contact_no=contact_no or '', age=int(age) if age else None)
            db.session.add(patient)
            db.session.commit()

            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))

        return render_template('auth/register.html')


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                flash('Logged in successfully.', 'success')
                # Redirect by role
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user.role == 'doctor':
                    return redirect(url_for('doctor_dashboard'))
                else:
                    return redirect(url_for('patient_dashboard'))
            flash('Invalid credentials', 'danger')
        return render_template('auth/login.html')


    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out', 'info')
        return redirect(url_for('index'))


    # ---------- Patient Routes ----------
    @app.route('/patient')
    @login_required
    def patient_dashboard():
        if current_user.role != 'patient':
            flash('Access denied', 'danger')
            return redirect(url_for('index'))

        # Show upcoming and past appointments
        patient = current_user.patient
        today = datetime.utcnow().date().isoformat()
        appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.date.desc(), Appointment.time.desc()).all()
        return render_template('patient/dashboard.html', appointments=appointments)


    @app.route('/patient/search', methods=['GET', 'POST'])
    @login_required
    def patient_search_doctors():
        if current_user.role != 'patient':
            return redirect(url_for('index'))
        specialization = request.values.get('specialization', '')
        date = request.values.get('date', '')
        doctors = Doctor.query.join(User).filter(User.name.isnot(None))
        if specialization:
            doctors = doctors.filter(Doctor.specialization.ilike(f'%{specialization}%'))
        doctors = doctors.all()
        return render_template('patient/search.html', doctors=doctors, date=date, specialization=specialization)


    @app.route('/patient/book/<int:doctor_id>', methods=['POST'])
    @login_required
    def patient_book(doctor_id):
        if current_user.role != 'patient':
            return redirect(url_for('index'))
        date = request.form.get('date')
        time = request.form.get('time')
        notes = request.form.get('notes')

        if not (date and time):
            flash('Please provide date and time', 'warning')
            return redirect(request.referrer or url_for('patient_dashboard'))

        # Prevent double-booking
        exists = Appointment.query.filter_by(doctor_id=doctor_id, date=date, time=time, status='Booked').first()
        if exists:
            flash('Selected slot is already booked for that doctor', 'danger')
            return redirect(request.referrer or url_for('patient_dashboard'))

        # Enforce doctor's availability if set
        doctor = Doctor.query.get(doctor_id)
        if doctor:
            # check day
            try:
                wk = datetime.strptime(date, '%Y-%m-%d').strftime('%a')
            except Exception:
                wk = ''
            if doctor.availability_days:
                days = [d.strip() for d in doctor.availability_days.split(',') if d.strip()]
                if wk not in days:
                    flash('Doctor is not available on the selected day', 'danger')
                    return redirect(request.referrer or url_for('patient_dashboard'))
            if doctor.available_from and doctor.available_to:
                # simple string comparison works for HH:MM
                if not (doctor.available_from <= time <= doctor.available_to):
                    flash('Selected time is outside the doctor\'s availability', 'danger')
                    return redirect(request.referrer or url_for('patient_dashboard'))

        appointment = Appointment(doctor_id=doctor_id, patient_id=current_user.patient.id, date=date, time=time, status='Booked', notes=notes)
        db.session.add(appointment)
        db.session.commit()
        flash('Appointment booked', 'success')
        return redirect(url_for('patient_dashboard'))


    @app.route('/patient/appointment/<int:appt_id>/cancel', methods=['POST'])
    @login_required
    def patient_cancel(appt_id):
        appt = Appointment.query.get_or_404(appt_id)
        if current_user.role != 'patient' or appt.patient.user_id != current_user.id:
            flash('Access denied', 'danger')
            return redirect(url_for('index'))
        appt.status = 'Cancelled'
        db.session.commit()
        flash('Appointment cancelled', 'info')
        return redirect(url_for('patient_dashboard'))


    @app.route('/patient/appointment/<int:appt_id>/reschedule', methods=['POST'])
    @login_required
    def patient_reschedule(appt_id):
        appt = Appointment.query.get_or_404(appt_id)
        if current_user.role != 'patient' or appt.patient.user_id != current_user.id:
            flash('Access denied', 'danger')
            return redirect(url_for('index'))

        new_date = request.form.get('date')
        new_time = request.form.get('time')
        if not (new_date and new_time):
            flash('Provide new date/time', 'warning')
            return redirect(url_for('patient_dashboard'))

        exists = Appointment.query.filter_by(doctor_id=appt.doctor_id, date=new_date, time=new_time, status='Booked').first()
        if exists and exists.id != appt.id:
            flash('Selected slot is already booked', 'danger')
            return redirect(url_for('patient_dashboard'))

        # Enforce doctor's availability
        doctor = appt.doctor
        try:
            wk = datetime.strptime(new_date, '%Y-%m-%d').strftime('%a')
        except Exception:
            wk = ''
        if doctor and doctor.availability_days:
            days = [d.strip() for d in doctor.availability_days.split(',') if d.strip()]
            if wk not in days:
                flash('Doctor is not available on the selected day', 'danger')
                return redirect(url_for('patient_dashboard'))
        if doctor and doctor.available_from and doctor.available_to:
            if not (doctor.available_from <= new_time <= doctor.available_to):
                flash('Selected time is outside the doctor\'s availability', 'danger')
                return redirect(url_for('patient_dashboard'))

        appt.date = new_date
        appt.time = new_time
        appt.status = 'Booked'
        db.session.commit()
        flash('Appointment rescheduled', 'success')
        return redirect(url_for('patient_dashboard'))


    # ---------- Doctor Routes ----------
    @app.route('/doctor')
    @login_required
    def doctor_dashboard():
        if current_user.role != 'doctor':
            flash('Access denied', 'danger')
            return redirect(url_for('index'))
        doctor = current_user.doctor
        # Show upcoming appointments
        appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.date.asc(), Appointment.time.asc()).all()
        return render_template('doctor/dashboard.html', appointments=appointments)


    @app.route('/doctor/availability', methods=['GET', 'POST'])
    @login_required
    def doctor_availability():
        if current_user.role != 'doctor':
            flash('Access denied', 'danger')
            return redirect(url_for('index'))
        doctor = current_user.doctor
        if request.method == 'POST':
            days = request.form.getlist('days')
            available_from = request.form.get('available_from')
            available_to = request.form.get('available_to')
            doctor.availability_days = ','.join(days)
            doctor.available_from = available_from
            doctor.available_to = available_to
            db.session.commit()
            flash('Availability updated', 'success')
            return redirect(url_for('doctor_dashboard'))
        return render_template('doctor/availability.html', doctor=doctor)


    @app.route('/doctor/appointment/<int:appt_id>/status', methods=['POST'])
    @login_required
    def doctor_update_status(appt_id):
        if current_user.role != 'doctor':
            return redirect(url_for('index'))
        appt = Appointment.query.get_or_404(appt_id)
        if appt.doctor.user_id != current_user.id:
            flash('Access denied', 'danger')
            return redirect(url_for('doctor_dashboard'))

        new_status = request.form.get('status')
        if new_status not in ['Completed', 'Cancelled', 'Booked']:
            flash('Invalid status', 'warning')
            return redirect(url_for('doctor_dashboard'))

        appt.status = new_status
        db.session.commit()
        flash('Appointment status updated', 'success')
        return redirect(url_for('doctor_dashboard'))


    @app.route('/doctor/appointment/<int:appt_id>/treatment', methods=['GET', 'POST'])
    @login_required
    def doctor_treatment(appt_id):
        if current_user.role != 'doctor':
            return redirect(url_for('index'))
        appt = Appointment.query.get_or_404(appt_id)
        if appt.doctor.user_id != current_user.id:
            flash('Access denied', 'danger')
            return redirect(url_for('doctor_dashboard'))

        if request.method == 'POST':
            diagnosis = request.form.get('diagnosis')
            prescription = request.form.get('prescription')
            notes = request.form.get('notes')

            # Only allow creating treatment if appointment is Completed
            if appt.status != 'Completed':
                flash('Appointment must be marked Completed to add treatment', 'warning')
                return redirect(url_for('doctor_dashboard'))

            # If existing, update; else create
            if appt.treatment:
                appt.treatment.diagnosis = diagnosis
                appt.treatment.prescription = prescription
                appt.treatment.notes = notes
            else:
                t = Treatment(appointment_id=appt.id, diagnosis=diagnosis, prescription=prescription, notes=notes)
                db.session.add(t)
            db.session.commit()
            flash('Treatment saved', 'success')
            return redirect(url_for('doctor_dashboard'))

        return render_template('doctor/treatment.html', appointment=appt)


    # Patient view treatment
    @app.route('/patient/appointment/<int:appt_id>/treatment')
    @login_required
    def patient_view_treatment(appt_id):
        if current_user.role != 'patient':
            flash('Access denied', 'danger')
            return redirect(url_for('index'))
        appt = Appointment.query.get_or_404(appt_id)
        if appt.patient.user_id != current_user.id:
            flash('Access denied', 'danger')
            return redirect(url_for('patient_dashboard'))
        if not appt.treatment:
            flash('No treatment recorded for this appointment', 'warning')
            return redirect(url_for('patient_dashboard'))
        return render_template('patient/treatment.html', appointment=appt)


    # ---------- Admin Routes ----------
    @app.route('/admin')
    @login_required
    def admin_dashboard():
        if current_user.role != 'admin':
            flash('Access denied', 'danger')
            return redirect(url_for('index'))
        doctors_count = Doctor.query.count()
        patients_count = Patient.query.count()
        appointments_count = Appointment.query.count()
        doctors = Doctor.query.all()
        patients = Patient.query.all()
        return render_template('admin/dashboard.html', doctors_count=doctors_count, patients_count=patients_count, appointments_count=appointments_count, doctors=doctors, patients=patients)


    @app.route('/admin/doctor/add', methods=['POST'])
    @login_required
    def admin_add_doctor():
        if current_user.role != 'admin':
            return redirect(url_for('index'))
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        specialization = request.form.get('specialization')
        availability_text = request.form.get('availability_text')
        availability_days = request.form.get('availability_days')
        available_from = request.form.get('available_from')
        available_to = request.form.get('available_to')

        if not (name and email and password):
            flash('Provide name, email, password', 'warning')
            return redirect(url_for('admin_dashboard'))

        if User.query.filter_by(email=email).first():
            flash('Email already used', 'danger')
            return redirect(url_for('admin_dashboard'))

        user = User(name=name, email=email, password_hash=generate_password_hash(password), role='doctor')
        db.session.add(user)
        db.session.commit()
        doctor = Doctor(user_id=user.id, specialization=specialization or '', availability_text=availability_text or '', availability_days=availability_days or '', available_from=available_from or '', available_to=available_to or '')
        db.session.add(doctor)
        db.session.commit()
        flash('Doctor added', 'success')
        return redirect(url_for('admin_dashboard'))


    @app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
    @login_required
    def admin_delete_user(user_id):
        if current_user.role != 'admin':
            return redirect(url_for('index'))
        user = User.query.get_or_404(user_id)
        # prevent deleting admin self
        if user.email == 'admin@example.com':
            flash('Cannot delete seeded admin', 'warning')
            return redirect(url_for('admin_dashboard'))
        db.session.delete(user)
        db.session.commit()
        flash('User deleted', 'info')
        return redirect(url_for('admin_dashboard'))


    # ---------- Simple JSON API ----------
    @app.route('/api/appointments', methods=['GET'])
    @login_required
    def api_get_appointments():
        # Return appointments for current user (doctor or patient)
        if current_user.role == 'patient':
            appts = Appointment.query.filter_by(patient_id=current_user.patient.id).all()
        elif current_user.role == 'doctor':
            appts = Appointment.query.filter_by(doctor_id=current_user.doctor.id).all()
        else:
            appts = Appointment.query.all()
        data = []
        for a in appts:
            data.append({'id': a.id, 'doctor_id': a.doctor_id, 'patient_id': a.patient_id, 'date': a.date, 'time': a.time, 'status': a.status})
        return jsonify(data)


    @app.route('/api/appointments', methods=['POST'])
    @login_required
    def api_create_appointment():
        payload = request.get_json() or {}
        doctor_id = payload.get('doctor_id')
        date = payload.get('date')
        time = payload.get('time')
        if current_user.role != 'patient':
            return jsonify({'error': 'Only patients can create appointments via API'}), 403
        exists = Appointment.query.filter_by(doctor_id=doctor_id, date=date, time=time, status='Booked').first()
        if exists:
            return jsonify({'error': 'Slot already booked'}), 400
        appt = Appointment(doctor_id=doctor_id, patient_id=current_user.patient.id, date=date, time=time, status='Booked')
        db.session.add(appt)
        db.session.commit()
        return jsonify({'ok': True, 'id': appt.id}), 201


    return app


def create_tables(app):
    # Create DB and seed default users if not present
    with app.app_context():
        db.create_all()

        # Ensure new doctor columns exist for older DBs by using SQLite ALTER TABLE
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(doctors)")
            cols = [r[1] for r in cur.fetchall()]
            if 'availability_days' not in cols:
                cur.execute("ALTER TABLE doctors ADD COLUMN availability_days TEXT")
            if 'available_from' not in cols:
                cur.execute("ALTER TABLE doctors ADD COLUMN available_from TEXT")
            if 'available_to' not in cols:
                cur.execute("ALTER TABLE doctors ADD COLUMN available_to TEXT")
            conn.commit()
            conn.close()
        except Exception:
            # If anything fails, continue; new DBs will have columns from model
            pass

        # Seed admin
        if not User.query.filter_by(email='admin@example.com').first():
            admin = User(name='Admin', email='admin@example.com', password_hash=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)

        # Seed doctor
        if not User.query.filter_by(email='doctor@example.com').first():
            doctor_user = User(name='Dr. Smith', email='doctor@example.com', password_hash=generate_password_hash('doctor123'), role='doctor')
            db.session.add(doctor_user)
            db.session.commit()
            # seed structured availability: Mon-Fri 09:00-17:00
            doctor = Doctor(user_id=doctor_user.id, specialization='General Medicine', availability_text='Mon-Fri 09:00-17:00', availability_days='Mon,Tue,Wed,Thu,Fri', available_from='09:00', available_to='17:00')
            db.session.add(doctor)

        # Seed patient
        if not User.query.filter_by(email='patient@example.com').first():
            patient_user = User(name='John Patient', email='patient@example.com', password_hash=generate_password_hash('patient123'), role='patient')
            db.session.add(patient_user)
            db.session.commit()
            patient = Patient(user_id=patient_user.id, contact_no='1234567890', age=30)
            db.session.add(patient)

        db.session.commit()

        # Seed a past completed appointment with treatment
        # Find doctor and patient ids
        doc = Doctor.query.first()
        pat = Patient.query.first()
        if doc and pat:
            past = Appointment.query.filter_by(doctor_id=doc.id, patient_id=pat.id, status='Completed').first()
            if not past:
                appt = Appointment(doctor_id=doc.id, patient_id=pat.id, date='2023-01-10', time='10:00', status='Completed', notes='Follow-up visit')
                db.session.add(appt)
                db.session.commit()
                t = Treatment(appointment_id=appt.id, diagnosis='Common Cold', prescription='Rest, fluids, paracetamol', notes='Patient recovered well')
                db.session.add(t)
                db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
