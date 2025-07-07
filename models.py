from flask import session
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy


db= SQLAlchemy()

class User(db.Model):
    __tablename__= 'users'

    id=db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(100), nullable=False)




class Reimbursement(db.Model):
    __tablename__ = 'reimb_form'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    purpose = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    letter = db.Column(db.String(200), nullable=False)
    certificate = db.Column(db.String(200), nullable=False)
    brochure = db.Column(db.String(200), nullable=False)
    bill = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pending Teacher')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher_status = db.Column(db.String(50), default='Pending')
    teacher_remarks = db.Column(db.Text)
    hod_status = db.Column(db.String(50), default='Pending')
    hod_remarks = db.Column(db.Text)
    principal_status = db.Column(db.String(50), default='Pending')
    principal_remarks = db.Column(db.Text)
    md_status = db.Column(db.String(50), default='Pending')
    md_remarks = db.Column(db.Text)
    accountant_status = db.Column(db.String(50), default='Pending')
    accountant_remarks = db.Column(db.Text)

    department = db.Column(db.String(100), default='Unknown')


# db.py (PostgreSQL + SQLAlchemy version)
def insert_user(name, email, password_hash, role, department):
    user = User(name=name, email=email, password_hash=password_hash, role=role, department=department)
    db.session.add(user)
    db.session.commit()

def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def get_emails_by_role_and_dept(role, department):
    users = User.query.filter_by(role=role, department=department).all()
    return [user.email for user in users]

def get_emails_by_role(role):
    users = User.query.filter_by(role=role).all()
    return [user.email for user in users]

def get_name_by_email(email):
    user = User.query.filter_by(email=email).first()
    return user.name if user else None

def get_all_users():
    users = User.query.all()
    return [(u.name, u.email, u.role, u.department) for u in users]

# ---------------- Reimbursement Flow ----------------

def insert_reimbursement(email, purpose, amount, letter, certificate, brochure, bill):
    user = User.query.filter_by(email=email).first()
    department = user.department if user else "Unknown"
    reimb = Reimbursement(
        email=email, purpose=purpose, amount=amount,
        letter=letter, certificate=certificate, brochure=brochure, bill=bill,
        status='Pending Teacher', submitted_at=datetime.now(),
        department=department
    )
    db.session.add(reimb)
    db.session.commit()

def get_all_reimbursements():
    reimbursements = Reimbursement.query.all()
    return [(r.email, r.purpose, r.amount, r.status, r.submitted_at,
             r.teacher_status, r.hod_status, r.principal_status,
             r.md_status, r.accountant_status) for r in reimbursements]

def get_reimbursement_by_email(email):
    records = Reimbursement.query.filter_by(email=email).all()
    return [(r.purpose, r.amount, r.status, r.submitted_at) for r in records]

def get_pending_requests_for_teacher(department):
    return Reimbursement.query.filter_by(teacher_status='Pending', department=department).all()

def get_pending_requests_for_hod(department):
    return Reimbursement.query.filter_by(
        hod_status='Pending', teacher_status='Approved', department=department
    ).all()

def get_pending_requests_for_principal():
    return Reimbursement.query.filter_by(
        principal_status='Pending', teacher_status='Approved', hod_status='Approved'
    ).all()

def get_pending_requests_for_md():
    return Reimbursement.query.filter_by(
        md_status='Pending', teacher_status='Approved',
        hod_status='Approved', principal_status='Approved'
    ).all()

def get_pending_requests_for_accountant():
    return Reimbursement.query.filter_by(
        accountant_status='Pending', teacher_status='Approved',
        hod_status='Approved', principal_status='Approved', md_status='Approved'
    ).all()

# ---------------- Approval Updates ----------------

def update_teacher_approval(req_id, status, remarks):
    reimb = Reimbursement.query.get(req_id)
    if reimb:
        reimb.teacher_status = status
        reimb.teacher_remarks = remarks
        reimb.status = "Pending HOD" if status == "Approved" else "Rejected by Teacher"
        db.session.commit()

def update_hod_approval(req_id, status, remarks):
    reimb = Reimbursement.query.get(req_id)
    if reimb:
        reimb.hod_status = status
        reimb.hod_remarks = remarks
        reimb.status = "Pending Principal" if status == "Approved" else "Rejected by HOD"
        db.session.commit()

def update_principal_approval(req_id, status, remarks):
    reimb = Reimbursement.query.get(req_id)
    if reimb:
        reimb.principal_status = status
        reimb.principal_remarks = remarks
        reimb.status = "Pending MD" if status == "Approved" else "Rejected by Principal"
        db.session.commit()

def update_md_approval(req_id, status, remarks):
    reimb = Reimbursement.query.get(req_id)
    if reimb:
        reimb.md_status = status
        reimb.md_remarks = remarks
        reimb.status = "Pending Accountant" if status == "Approved" else "Rejected by MD"
        db.session.commit()

def update_accountant_approval(req_id, status, remarks):
    reimb = Reimbursement.query.get(req_id)
    if reimb:
        reimb.accountant_status = status
        reimb.accountant_remarks = remarks
        reimb.status = "Processed" if status == "Approved" else "Rejected by Accountant"
        db.session.commit()

# ---------------- Utility ----------------

def get_request_details(req_id):
    reimb = Reimbursement.query.get(req_id)
    return (reimb.email, reimb.department) if reimb else None
