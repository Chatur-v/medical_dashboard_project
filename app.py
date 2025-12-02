from flask import Flask, render_template, request, redirect, url_for, flash, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Appointment, Prescription, generate_password, generate_id
from config import Config
from flask_mail import Mail, Message
import qrcode
from io import BytesIO
import base64
from datetime import datetime

# === FLASK APP SETUP ===
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# === BULLETPROOF DATABASE INITIALIZATION ===
def init_db_on_first_request():
    if 'db_initialized' not in g:
        db.create_all()
        if not User.query.filter_by(role='admin').first():
            admin_pass = generate_password()
            admin = User(
                id='AID001',
                username='admin',
                password=generate_password_hash(admin_pass),
                role='admin',
                email='admin@hospital.com',
                name='Hospital Admin'
            )
            db.session.add(admin)
            db.session.commit()
            print(f"\nADMIN CREATED: username=admin, password={admin_pass}\n")
        g.db_initialized = True

@app.before_request
def before_request():
    init_db_on_first_request()


# === ROUTES ===
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            else:
                return redirect(url_for('patient_dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# === ADMIN ROUTES ===
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    doctors = User.query.filter_by(role='doctor').all()
    patients = User.query.filter_by(role='patient').all()
    appointments = Appointment.query.all()
    return render_template('admin/dashboard.html', doctors=doctors, patients=patients, appointments=appointments)

@app.route('/admin/add_doctor', methods=['GET', 'POST'])
@login_required
def add_doctor():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        specialty = request.form['specialty']
        username = email.split('@')[0]
        password = generate_password()
        doc_id = generate_id('DID')

        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(request.url)

        doctor = User(
            id=doc_id,
            username=username,
            password=generate_password_hash(password),
            role='doctor',
            email=email,
            name=name,
            specialty=specialty
        )
        db.session.add(doctor)
        db.session.commit()

        msg = Message("Doctor Account Created", recipients=[email])
        msg.body = f"""
Hello Dr. {name},

Your account has been created!

Username: {username}
Password: {password}
ID: {doc_id}

Login at: http://127.0.0.1:5000
        """
        try:
            mail.send(msg)
            flash('Doctor added and email sent!')
        except:
            flash('Doctor added (email failed)')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/add_doctor.html')

@app.route('/admin/add_patient', methods=['GET', 'POST'])
@login_required
def add_patient():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        username = email.split('@')[0]
        password = generate_password()
        pat_id = generate_id('PID')

        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(request.url)

        patient = User(
            id=pat_id,
            username=username,
            password=generate_password_hash(password),
            role='patient',
            email=email,
            name=name
        )
        db.session.add(patient)
        db.session.commit()

        msg = Message("Patient Account Created", recipients=[email])
        msg.body = f"""
Hello {name},

Your account has been created!

Username: {username}
Password: {password}
ID: {pat_id}

Login at: http://127.0.0.1:5000
        """
        try:
            mail.send(msg)
            flash('Patient added and email sent!')
        except:
            flash('Patient added (email failed)')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/add_patient.html')

@app.route('/admin/book_appointment', methods=['GET', 'POST'])
@login_required
def admin_book_appointment():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    doctors = User.query.filter_by(role='doctor').all()
    patients = User.query.filter_by(role='patient').all()
    if request.method == 'POST':
        date_str = request.form['date']  # e.g., "2025-11-12T14:30"
        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format')
            return redirect(request.url)

        appt = Appointment(
            patient_id=request.form['patient_id'],
            doctor_id=request.form['doctor_id'],
            date=appointment_date,
            reason=request.form['reason']
        )
        db.session.add(appt)
        db.session.commit()
        flash('Appointment booked!')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/book_appointment.html', doctors=doctors, patients=patients)


# === DOCTOR ROUTES ===
@app.route('/doctor')
@login_required
def doctor_dashboard():
    if current_user.role != 'doctor':
        return redirect(url_for('login'))
    appointments = Appointment.query.filter_by(doctor_id=current_user.id).all()
    return render_template('doctor/dashboard.html', appointments=appointments)

@app.route('/doctor/add_report/<int:appt_id>', methods=['POST'])
@login_required
def add_report(appt_id):
    if current_user.role != 'doctor':
        return redirect(url_for('login'))
    appt = Appointment.query.get_or_404(appt_id)
    if appt.doctor_id != current_user.id:
        flash('Unauthorized')
        return redirect(url_for('doctor_dashboard'))
    appt.report = request.form['report']
    appt.status = 'Completed'
    db.session.commit()
    flash('Report added')
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/prescribe/<int:appt_id>', methods=['GET', 'POST'])
@login_required
def prescribe(appt_id):
    if current_user.role != 'doctor':
        return redirect(url_for('login'))
    appt = Appointment.query.get_or_404(appt_id)
    if appt.doctor_id != current_user.id:
        flash('Unauthorized')
        return redirect(url_for('doctor_dashboard'))

    if request.method == 'POST':
        prescription = Prescription(
            appointment_id=appt.id,
            medications=request.form['medications'],
            instructions=request.form['instructions']
        )
        db.session.add(prescription)
        db.session.commit()

        qr_data = f"""
PRESCRIPTION
------------
Patient: {appt.patient.name}
Doctor: Dr. {current_user.name}
Date: {appt.date.strftime('%Y-%m-%d %H:%M')}
------------
Medications:
{prescription.medications}
------------
Instructions:
{prescription.instructions or 'None'}
------------
Verify: {url_for('view_prescription', token=prescription.id, _external=True)}
        """.strip()

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return render_template('doctor/prescription_qr.html',
                             qr_code=img_str, prescription=prescription, appt=appt)

    return render_template('doctor/prescribe.html', appt=appt)


# === PATIENT ROUTES ===
@app.route('/patient')
@login_required
def patient_dashboard():
    if current_user.role != 'patient':
        return redirect(url_for('login'))
    doctors = User.query.filter_by(role='doctor').all()
    appointments = Appointment.query.filter_by(patient_id=current_user.id).all()
    return render_template('patient/dashboard.html', doctors=doctors, appointments=appointments)

@app.route('/patient/book_appointment', methods=['GET', 'POST'])
@login_required
def patient_book_appointment():
    if current_user.role != 'patient':
        return redirect(url_for('login'))
    doctors = User.query.filter_by(role='doctor').all()
    if request.method == 'POST':
        date_str = request.form['date']
        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format')
            return redirect(request.url)

        appt = Appointment(
            patient_id=current_user.id,
            doctor_id=request.form['doctor_id'],
            date=appointment_date,
            reason=request.form['reason']
        )
        db.session.add(appt)
        db.session.commit()
        flash('Appointment booked!')
        return redirect(url_for('patient_dashboard'))
    return render_template('patient/book_appointment.html', doctors=doctors)

# === PUBLIC ROUTE ===
@app.route('/prescription/<int:token>')
def view_prescription(token):
    prescription = Prescription.query.get_or_404(token)
    appt = prescription.appointment
    return render_template('public/prescription_view.html', prescription=prescription, appt=appt)


# === RUN APP ===
if __name__ == '__main__':
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000')
    app.run(debug=True)