import os
from dotenv import load_dotenv
from cs50 import SQL
from functools import wraps
from flask import session, redirect, url_for, flash


load_dotenv()


def get_db():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in .env file")
    return SQL(db_url)


def login_required(f):
    """Decorator — redirects to login if no active session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access that page.", "error")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator — restricts route to admin role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access that page.", "error")
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash("You don't have permission to access that page.", "error")
            return redirect(url_for('dashboard.view_dashboard'))
        return f(*args, **kwargs)
    return decorated


def log_audit(db, action, table_name, record_id, description, member_id=None):
    """
    Call this after any significant DB write, before conn.commit().
    db      — your cursor object
    action  — 'create' / 'update' / 'delete' / 'refund'
    """
    db.execute("""
        INSERT INTO audit_logs (member_id, action, table_name, record_id, description)
        VALUES (?, ?, ?, ?, ?)
    """, (member_id, action, table_name, record_id, description))
