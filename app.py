# app.py (PostgreSQL + SQLAlchemy version)
from mailbox import Message
from flask import Flask, Response, render_template, request, redirect, send_from_directory, url_for, session, flash
from flask_mail import *
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF
import random
import os
import tempfile

# Models and database operations
from models import (
    db,
    insert_user, get_user_by_email, get_emails_by_role_and_dept, get_emails_by_role,
    get_name_by_email, get_all_users, get_all_reimbursements, insert_reimbursement,
    get_reimbursement_by_email, get_pending_requests_for_teacher, get_pending_requests_for_hod,
    get_pending_requests_for_principal, get_pending_requests_for_md, get_pending_requests_for_accountant,
    update_teacher_approval, update_hod_approval, update_principal_approval,
    update_md_approval, update_accountant_approval, get_request_details,
    User, Reimbursement
)
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS

app = Flask(__name__)
app.secret_key = os.urandom(24)
load_dotenv()

# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
mail = Mail(app)

# Uploads config
UPLOAD_FILE = 'uploads'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'pdf'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FILE
if not os.path.exists(UPLOAD_FILE):
    os.makedirs(UPLOAD_FILE)

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
print("📦 SQLALCHEMY_DATABASE_URI =", app.config['SQLALCHEMY_DATABASE_URI'])


db.init_app(app)

with app.app_context():
    db.create_all()

def normalize_statuses():
    with app.app_context():
        records = Reimbursement.query.all()
        for r in records:
            if r.teacher_status.lower() == 'approved':
                r.teacher_status = 'Approved'
            if r.hod_status.lower() == 'approved':
                r.hod_status = 'Approved'
            if r.principal_status.lower() == 'approved':
                r.principal_status = 'Approved'
            if r.md_status.lower() == 'approved':
                r.md_status = 'Approved'
            if r.accountant_status.lower() == 'pending':
                r.accountant_status = 'Pending'
        db.session.commit()

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login')) 

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']

        # ✅ Check if already registered
        if get_user_by_email(email):
            flash('📝 You have already registered. Please login instead.', 'warning')
            return redirect(url_for('login'))

        # ✅ Continue if not registered
        if not (email.endswith('fcrit.ac.in') or email.endswith('gmail.com')):
            flash('❌ Only college or Gmail IDs allowed', 'danger')
            return redirect(url_for('register'))

        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['email'] = email

        msg = Message('Your OTP', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Your OTP is {otp}'
        mail.send(msg)

        flash("📩 OTP sent to your email.", 'info')
        return redirect(url_for('verify'))

    return render_template('register.html')

                    

@app.route('/verify', methods=['GET','POST'])
def verify():
    if request.method == 'POST':
        ent_otp = request.form['otp']
        if ent_otp == session.get('otp'):
            flash('Email verified successfully', 'success')
            return redirect(url_for('complete_registration'))  # ✅ go to next step
        else:
            flash('Invalid OTP', 'danger')
    return render_template('otp.html')


@app.route('/complete_registration', methods=['GET', 'POST'])
def complete_registration():
    email = session.get('email')

    if not email:
        flash("Session expired. Please restart registration.", "warning")
        return redirect(url_for('register'))

    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        role = request.form['role']
        department = request.form.get('department', 'None')  # 'None' for Principal, MD, Accountant

        if get_user_by_email(email):
            flash('User already exists. Please login.', 'warning')
            return redirect(url_for('login'))

        password_hash = generate_password_hash(password)
        insert_user(name, email, password_hash, role, department)

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('complete_registration.html')


@app.route('/login', methods=['GET', 'POST'])    
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user_by_email(email)

        if user and check_password_hash(user.password_hash, password):

            session['department'] = user.department
            session['user_id'] = user.id
            session['role'] = user.role
            session['email'] = user.email
        # ✅ Correct: index 2 is email
            flash('Login successful', 'success')
            return redirect(url_for(f"{user.role.lower()}_dashboard"))
        else:
            flash('Invalid credentials', 'danger')

    return render_template('login.html')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/student/apply', methods=['GET', 'POST'])
def student_apply():
    amount = None
    if request.method == 'POST':
        purpose = request.form['purpose']
        amount = float(request.form['amount'])

        letter = request.files['letter']
        certificate = request.files['certificate']
        brochure = request.files['brochure']
        bill = request.files['bill']

        email = session.get('email')
        department = session.get('department')  # ✅ get student's department

        if not email:
            flash("⚠️ Session expired. Please log in again.", "warning")
            return redirect(url_for('login'))

        def save_file(file_obj, label):
            if file_obj and allowed_file(file_obj.filename):
                filename = secure_filename(f"{label}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_obj.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file_obj.save(filepath)
                return filename
            return None

        letter_filename = save_file(letter, 'letter')
        cert_filename = save_file(certificate, 'certificate')
        brochure_filename = save_file(brochure, 'brochure')
        bill_filename = save_file(bill, 'bill')

        insert_reimbursement(email, purpose, amount, letter_filename, cert_filename, brochure_filename, bill_filename)

        # ✅ Notify Teacher(s) of the same department
        teacher_emails = get_emails_by_role_and_dept('Teacher', department)
        if teacher_emails:
            msg = Message(
                "New Reimbursement Request",
                sender=app.config['MAIL_USERNAME'],
                recipients=teacher_emails
            )
            msg.body = f"A student from the {department} department has submitted a reimbursement request for: {purpose}.\nPlease login to review."
            mail.send(msg)

        flash("✅ Reimbursement request submitted successfully!", "success")
        return redirect(url_for('student_apply'))

    return render_template('student_form.html')


# Dummy dashboards

@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'Admin':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))

    users = get_all_users()
    reimbursements = get_all_reimbursements()
    return render_template('admin_dashboard.html', users=users, reimbursements=reimbursements)


@app.route('/export_reimbursements')
def export_reimbursements():
    if session.get('role') != 'Admin':
        flash("Access denied", "danger")
        return redirect(url_for('login'))

    data = get_all_reimbursements()  # This function should return a list of tuples
    output = []

    # Header
    output.append(['Email', 'Purpose', 'Amount', 'Status', 'Submitted At', 'Teacher Status', 'HOD Status', 'Principal Status', 'MD Status', 'Accountant Status'])

    for row in data:
        output.append(list(row))

    # Create CSV
    def generate():
        for row in output:
            yield ','.join(str(cell) for cell in row) + '\n'

    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=reimbursements.csv"})

@app.route('/student_dashboard')
def student_dashboard():
    email = session.get('email')
    if not email:
        flash("Please log in again.", "warning")
        return redirect(url_for('login'))

    reimbursements = get_reimbursement_by_email(email)
    username = showName()
    return render_template('student.html', reimbursements=reimbursements, username=username )

def showName():
    email = session.get('email')
    return get_name_by_email(email)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if session.get('role') not in ['Teacher', 'HOD', 'Principal', 'MD', 'Accountant', 'Student']:
        flash("Access denied", "danger")
        return redirect(url_for('login'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)



# ------------------ TEACHER ------------------
@app.route('/teacher_dashboard')
def teacher_dashboard():
    if session.get('role') != 'Teacher':
        flash('Access Denied', 'danger')
        return redirect(url_for('login'))
    
    department = session.get('department')
    requests = get_pending_requests_for_teacher(department)
    return render_template('teacher_dashboard.html', requests=requests)


@app.route('/teacher_approve/<int:req_id>', methods=['POST'])
def teacher_approve(req_id):
    if session.get('role') != 'Teacher':
        flash('Access Denied', 'danger')
        return redirect(url_for('login'))

    remarks = request.form['remarks']
    action = request.form['action']

    # ✅ Always fetch department fresh from DB to avoid session mismatch
    teacher_email = session.get('email')
    user = User.query.filter_by(email=teacher_email).first()
    teacher_dept = user.department if user else "Unknown"

    if action == 'approve':
        update_teacher_approval(req_id, 'Approved', remarks)

        # Fetch HOD emails from actual department
        hod_emails = get_emails_by_role_and_dept('HOD', teacher_dept)

        if hod_emails:
            msg = Message(
                "Action Required: HOD Approval",
                sender=app.config['MAIL_USERNAME'],
                recipients=hod_emails
            )
            msg.body = f"A reimbursement request (ID: {req_id}) has been approved by the Teacher and awaits your review."
            mail.send(msg)

        flash('✅ Request approved and sent to HOD', 'success')

    elif action == 'reject':
        update_teacher_approval(req_id, 'Rejected', remarks)
        flash('❌ Request rejected', 'danger')

    return redirect(url_for('teacher_dashboard'))

# ------------------ HOD ------------------
@app.route('/hod_dashboard')
def hod_dashboard():
    if session.get('role') != 'HOD':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))

    department = session.get('department')
    requests = get_pending_requests_for_hod(department)
    return render_template('Hod_dashboard.html', requests=requests)


@app.route('/hod_approve/<int:req_id>', methods=['POST'])
def hod_approve(req_id):
    if session.get('role') != 'HOD':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))

    remarks = request.form['remarks']
    action = request.form['action']

    if action == 'approve':
        update_hod_approval(req_id, 'Approved', remarks)
        principal_emails = get_emails_by_role('Principal')  # ✅

        if principal_emails:
            msg = Message(
                "Action Required: Principal Approval",
                sender=app.config['MAIL_USERNAME'],
                recipients=principal_emails
            )
            msg.body = f"Request {req_id} has been approved by HOD. Please review and take action."
            mail.send(msg)
        flash('✅ Request approved and sent to Principal', 'success')
    elif action == 'reject':
        update_hod_approval(req_id, 'Rejected', remarks)
        flash('❌ Request rejected', 'danger')

    return redirect(url_for('hod_dashboard'))


# ------------------ PRINCIPAL ------------------
@app.route('/principal_dashboard')
def principal_dashboard():
    if session.get('role') != 'Principal':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))
    requests = get_pending_requests_for_principal()
    return render_template('Principal_dashboard.html', requests=requests)

@app.route('/principal_approve/<int:req_id>', methods=['POST'])
def principal_approve(req_id):
    if session.get('role') != 'Principal':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))

    remarks = request.form['remarks']
    action = request.form['action']

    if action == 'approve':
        update_principal_approval(req_id, 'Approved', remarks)
        md_emails = get_emails_by_role('MD')
        if md_emails:
            msg = Message(
                "Action Required: MD Approval",
                sender=app.config['MAIL_USERNAME'],
                recipients=md_emails
            )
            msg.body = f"Request {req_id} has been approved by Principal. Please review and take action."
            mail.send(msg)
        flash('✅ Request approved and sent to MD', 'success')
    elif action == 'reject':
        update_principal_approval(req_id, 'Rejected', remarks)
        flash('❌ Request rejected', 'danger')

    return redirect(url_for('principal_dashboard'))


# ------------------ MD ------------------
@app.route('/md_dashboard')
def md_dashboard():
    if session.get('role') != 'MD':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))
    requests = get_pending_requests_for_md()
    return render_template('md_dashboard.html', requests=requests)

@app.route('/md_approve/<int:req_id>', methods=['POST'])
def md_approve(req_id):
    if session.get('role') != 'MD':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))

    remarks = request.form['remarks']
    action = request.form['action']

    if action == 'approve':
        update_md_approval(req_id, 'Approved', remarks)
        accountant_emails = get_emails_by_role('Accountant')
        if accountant_emails:
            msg = Message(
                "Action Required: Accountant Final Check",
                sender=app.config['MAIL_USERNAME'],
                recipients=accountant_emails
            )
            msg.body = f"Request {req_id} has been approved by MD. Please process this reimbursement."
            mail.send(msg)
        flash('✅ Request approved and sent to Accountant', 'success')
    elif action == 'reject':
        update_md_approval(req_id, 'Rejected', remarks)
        flash('❌ Request rejected', 'danger')

    return redirect(url_for('md_dashboard'))

def generate_reimbursement_report(data, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    bold = styles["Heading4"]

    # Optional custom paragraph style for cleaner spacing
    para_style = ParagraphStyle(name="Custom", parent=normal, fontSize=10, leading=14)

    # Logo
    logo_path = "static/logo.png"  # Ensure this path is correct
    try:
        logo = Image(logo_path, width=60, height=60)
        logo.hAlign = 'LEFT'
        elements.append(logo)
    except:
        pass

    # Heading
    elements.append(Paragraph("<b>Fr. C Rodrigues Institute of Technology, Vashi</b>", styles["Heading1"]))
    elements.append(Paragraph("Reimbursement Final Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Student Info
    elements.append(Paragraph(f"<b>Student Name:</b> {data['student_name']}", para_style))
    elements.append(Paragraph(f"<b>Email:</b> {data['email']}", para_style))
    elements.append(Paragraph(f"<b>Department:</b> {data['department']}", para_style))
    if 'transaction_ref' in data:
        elements.append(Paragraph(f"<b>Transaction Ref:</b> {data['transaction_ref']}", para_style))
    elements.append(Spacer(1, 12))

    # Main table
    table_data = [[
        Paragraph("<b>Purpose</b>", para_style),
        Paragraph("<b>Amount (₹)</b>", para_style),
        Paragraph("<b>Status</b>", para_style),
        Paragraph("<b>Date Submitted</b>", para_style)
    ], [
        Paragraph(data['purpose'], para_style),
        f"₹{data['amount']}",
        data['accountant_status'],
        str(data['submitted_at']).split('.')[0]
    ]]

    table = Table(table_data, colWidths=[3.2 * inch, 1.2 * inch, 1.2 * inch, 2 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Remarks sections
    elements.append(Paragraph("<b>Accountant Remarks:</b>", bold))
    elements.append(Paragraph(data['accountant_remarks'], para_style))
    elements.append(Spacer(1, 8))

    # Optional other roles
    for role in ['teacher', 'hod', 'principal']:
        status_key = f"{role}_status"
        remarks_key = f"{role}_remarks"
        if data.get(status_key) or data.get(remarks_key):
            elements.append(Paragraph(f"<b>{role.upper()} Status:</b> {data.get(status_key, '')}", para_style))
            elements.append(Paragraph(f"<b>{role.upper()} Remarks:</b> {data.get(remarks_key, '')}", para_style))
            elements.append(Spacer(1, 8))

    elements.append(Spacer(1, 30))

    # Signature Line
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("__________________________", para_style))
    elements.append(Paragraph("Signature (Accounts Dept)", para_style))
    elements.append(Spacer(1, 20))



    # Footer
    elements.append(Spacer(1, 20))
    footer = Paragraph("<i>Generated by Reimbursement Portal - FCRIT</i>", para_style)
    elements.append(footer)

    doc.build(elements)
@app.route('/accountant_dashboard')
def accountant_dashboard():
    if session.get('role') != 'Accountant':
        flash('Access Denied', 'danger')
        return redirect(url_for('login'))
    requests = get_pending_requests_for_accountant()
    return render_template('accountant_dashboard.html', requests=requests)
@app.route('/accountant_approve/<int:req_id>', methods=['POST'])
def accountant_approve(req_id):
    if session.get('role') != 'Accountant':
        flash('Access Denied', 'danger')
        return redirect(url_for('login'))

    remarks = request.form['remarks']
    action = request.form['action']
    status = 'Approved' if action == 'approve' else 'Rejected'

    update_accountant_approval(req_id, status, remarks)

    # Get student record using SQLAlchemy
    form_data = Reimbursement.query.filter_by(id=req_id).first()
    if not form_data:
        flash("Reimbursement request not found", "danger")
        return redirect(url_for('accountant_dashboard'))

    student_email = form_data.email
    department = form_data.department
    student_name = User.query.filter_by(email=student_email).first().name

    # Send email to student
    msg = Message(
        'Reimbursement Status Update',
        sender=app.config['MAIL_USERNAME'],
        recipients=[student_email]
    )
    msg.body = f"""
Dear Student,

Your reimbursement request (ID: {req_id}) has been {'✅ approved and processed' if status == 'Approved' else '❌ rejected by the accountant'}.

Remarks: {remarks}

Thank you,
Accounts Department
"""
    mail.send(msg)

    if status == 'Approved':
        # Prepare PDF report
        form_keys = [
            'id', 'email', 'purpose', 'amount', 'letter', 'certificate',
            'brochure', 'bill', 'status', 'submitted_at',
            'teacher_status', 'teacher_remarks',
            'hod_status', 'hod_remarks',
            'principal_status', 'principal_remarks',
            'md_status', 'md_remarks',
            'accountant_status', 'accountant_remarks', 'department'
        ]
        form_values = [
            form_data.id, form_data.email, form_data.purpose, form_data.amount, form_data.letter, form_data.certificate,
            form_data.brochure, form_data.bill, form_data.status, form_data.submitted_at,
            form_data.teacher_status, form_data.teacher_remarks,
            form_data.hod_status, form_data.hod_remarks,
            form_data.principal_status, form_data.principal_remarks,
            form_data.md_status, form_data.md_remarks,
            form_data.accountant_status, form_data.accountant_remarks, form_data.department
        ]
        data_dict = dict(zip(form_keys, form_values))
        data_dict['student_name'] = student_name

        # Generate PDF in temporary path
        temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        generate_reimbursement_report(data_dict, temp_path)

        # Send email to teacher with PDF
        teacher_emails = get_emails_by_role_and_dept('Teacher', department)
        if teacher_emails:
            msg2 = Message(
                "✅ Final Reimbursement Report",
                sender=app.config['MAIL_USERNAME'],
                recipients=teacher_emails
            )
            msg2.body = f"""
Dear Faculty,

The reimbursement request (ID: {req_id}) from student {student_name} has been fully approved and processed.

Please find the attached report for your records.

Regards,
Reimbursement Portal
"""
            with open(temp_path, 'rb') as f:
                msg2.attach(f"Reimbursement_Report_{req_id}.pdf", "application/pdf", f.read())

            mail.send(msg2)

    flash('✅ Final status saved, student and teacher notified with report.', 'success')
    return redirect(url_for('accountant_dashboard'))


if __name__ == '__main__':
    normalize_statuses()
    app.run(debug=True)
