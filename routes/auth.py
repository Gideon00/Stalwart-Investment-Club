
from werkzeug.security import check_password_hash
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from helpers import get_db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_input = request.form.get('username', '').strip()
        password_input = request.form.get('password', '')

        if not username_input or not password_input:
            flash("Username and password are required.", "error")
            return render_template('login.html')

        try:
            db = get_db()
            user_rows = db.execute(
                "SELECT * FROM members WHERE (username = :u OR email = :e) AND status = 'active'",
                u=username_input,
                e=username_input
            )
            user = user_rows[0] if user_rows else None

            if user and check_password_hash(user['password_hash'], password_input):
                session.clear()
                session['user_id']   = user['id']
                session['username']  = user['username']
                session['full_name'] = user['full_name']
                session['role']      = user['role']
                session['profile']   = user['profile_photo']
                flash(f"Welcome back, {user['full_name']}.", "success")
                return redirect(url_for('dashboard.view_dashboard'))
            else:
                flash("Invalid username or password.", "error")

        except Exception as e:
            flash(f"Database error: {str(e)}", "error")

        return render_template('login.html')

    # GET — clear session and show the form
    session.clear()
    return render_template('login.html')
