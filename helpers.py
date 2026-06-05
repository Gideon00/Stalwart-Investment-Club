import os
import sqlite3
from functools import wraps
from flask import session, redirect, url_for, flash

DATABASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'club.db')


def get_db():
    """Open a sqlite3 connection with Row factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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