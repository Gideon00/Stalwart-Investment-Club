import sqlite3
from werkzeug.security import check_password_hash
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from helpers import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_input = request.form.get('username', '').strip()
        password_input = request.form.get('password', '')

        # Basic presence check before hitting the database
        if not username_input or not password_input:
            flash("Username and password are required.", "error")
            return render_template('login.html')

        try:
            with get_db() as conn:
                db = conn.cursor()
                db.execute(
                    "SELECT * FROM members WHERE (username = ? OR email = ?) AND status = 'active'",
                    (username_input, username_input)
                )
                user = db.fetchone()

            # check_password_hash compares the submitted plain text against the stored hash
            if user and check_password_hash(user['password_hash'], password_input):
                session.clear()
                session['user_id']   = user['id']
                session['username']  = user['username']
                session['full_name'] = user['full_name']
                session['role']      = user['role']
                session['profile']      = user['profile_photo']
                flash(f"Welcome back, {user['full_name']}.", "success")
                return redirect(url_for('dashboard.view_dashboard'))
            else:
                # Same message for both wrong username and wrong password
                # — never tell an attacker which one failed
                flash("Invalid username or password.", "error")

        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "error")
            
    session.clear()  # Clear any existing session on GET or after failed login
    return render_template('login.html')
