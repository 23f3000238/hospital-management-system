# Simple Hospital Management System (HMS)

A beginner-friendly, minimal Hospital Management System built using:
- Python + Flask (backend)
- Jinja2 (templating)
- Bootstrap 5 (CDN) for responsive UI
- SQLite (file database: `data/hms.db`)

This project is intended as a learning example — code is kept simple and commented so beginners can follow the flow.

**Where the DB is created**: `data/hms.db` is created automatically on first run. If you want a fresh start, delete that file and restart the app.

**Seeded test accounts**
- Admin: `admin@example.com` / `admin123`
- Doctor: `doctor@example.com` / `doctor123`
- Patient: `patient@example.com` / `patient123`

Getting started (Windows PowerShell)
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set FLASK_APP=app.py; flask run
```

Unix / macOS
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
FLASK_APP=app.py flask run
```

Or run directly (development mode):
```powershell
python app.py
```

What this project implements
- User roles: **admin**, **doctor**, **patient** (session-based auth using `flask_login`). Patients can self-register.
- Database tables (created programmatically): `users`, `doctors`, `patients`, `appointments`, `treatments`.
- Patient features:
	- Register and login
	- Search doctors by specialization and desired date
	- Book, reschedule, and cancel appointments
	- View upcoming & past appointments
	- View treatment details for completed appointments
- Doctor features:
	- View assigned appointments (day/week ordering)
	- Set availability (days and time range)
	- Mark appointments Completed or Cancelled
	- Record diagnosis, prescription, and notes for Completed appointments (saved to `treatments`)
- Admin features:
	- Dashboard summary (counts of doctors, patients, appointments)
	- Add doctors (with availability), delete users (doctors/patients)

Business rules and validations
- Double-booking prevention: the app prevents creating or rescheduling to a date/time where the doctor already has a Booked appointment.
- Availability enforcement: if a doctor sets availability days and a time range, booking and rescheduling will enforce those constraints.
- Appointment lifecycle: Booked → Completed or Cancelled. Treatments may only be added when an appointment is Completed.
- Basic server-side validation is implemented; forms also use HTML5 validation attributes.

API endpoints (simple JSON examples)
- `GET /api/appointments` — returns appointments for the current user (or all, if admin)
- `POST /api/appointments` — create an appointment (patients only). Payload: `{"doctor_id":1,"date":"YYYY-MM-DD","time":"HH:MM"}`

Notes, troubleshooting, and improvements
- If you change model fields during development, the app attempts a lightweight runtime migration to add new `doctors` columns. If migration fails or you prefer a clean DB, delete `data/hms.db` and restart the app.
- Development secret key is in `app.py` as `SECRET_KEY='dev-secret-key-change-me'`. Replace it for any real deployment.
- Time comparisons use simple `HH:MM` strings (24-hour format). This is adequate for a demo but consider using timezone-aware datetimes for production.
- SQLAlchemy/Flask warnings in the console are expected in development mode; they do not prevent the app from running.

Next steps you might want to add
- Frontend: show available time slots when searching a doctor
- Admin: full edit forms for doctors & patients
- Validation: stronger server-side validation and clearer error messages
- Tests: add unit/integration tests for booking and availability logic
