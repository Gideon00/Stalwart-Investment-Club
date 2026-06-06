from datetime import datetime
from werkzeug.security import generate_password_hash
from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from helpers import admin_required, get_db, log_audit, login_required

members_bp = Blueprint('members', __name__)


@members_bp.route('/members')
@login_required
def list_members():
    try:
        db = get_db()

        members_from_db = db.execute("SELECT * FROM members ORDER BY id DESC")

        # PostgreSQL returns date objects — format directly, no strptime needed
        for m in members_from_db:
            if m['date_joined']:
                if isinstance(m['date_joined'], str):
                    m['date_joined'] = datetime.strptime(m['date_joined'], '%Y-%m-%d').strftime('%d-%m-%Y')
                else:
                    m['date_joined'] = m['date_joined'].strftime('%d-%m-%Y')

        res_total = db.execute("SELECT COUNT(*) as count FROM members WHERE status = 'active'")
        total_members = res_total[0]['count']

        res_avg = db.execute("""
            SELECT COALESCE(AVG(total), 0) as avg
            FROM (
                SELECT SUM(amount) as total
                FROM contributions
                GROUP BY member_id
            ) AS contrib_totals
        """)
        avg_contribution = res_avg[0]['avg']

        res_active = db.execute("SELECT COUNT(*) as count FROM members WHERE status = 'active'")
        active_count = res_active[0]['count']

        active_share = round((active_count / total_members * 100), 1) if total_members > 0 else 0

        return render_template('members.html',
            active_page='members',
            members=members_from_db,
            total_members=total_members,
            avg_contribution=avg_contribution,
            active_share=active_share
        )

    except Exception as e:
        flash(f"Failed to load members: {str(e)}", "error")
        return render_template('members.html',
            active_page='members',
            members=[],
            total_members=0,
            avg_contribution=0,
            active_share=0
        )


@members_bp.route('/members/add', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':

        # 1. Extract fields
        full_name = (request.form.get('fullName') or '').strip().title()
        username  = (request.form.get('username') or '').strip()
        phone     = (request.form.get('phone') or '').strip()
        email     = (request.form.get('email') or '').strip()
        address   = (request.form.get('address') or '').strip()
        profile   = (request.form.get('profile') or '').strip()
        password  = request.form.get('password') or ''
        cpassword = request.form.get('Cpassword') or ''

        # 2. Validate passwords
        if password != cpassword:
            flash("Password and confirm password do not match.", "error")
            return render_template('add_member.html', active_page='members')

        db = get_db()

        # 3. Check uniqueness (Case-Insensitive)
        existing = db.execute(
            """
            SELECT id FROM members WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)
            """,
            username, email
        )
        if existing:
            flash("Username or email already taken. Please choose another.", "error")
            return render_template('add_member.html', active_page='members')

        # 4. Hash
        password_hash = generate_password_hash(password)

        # 5. Insert
        try:
            new_member_id = db.execute("""
                INSERT INTO members (
                    full_name, password_hash, username, phone, email, address, profile_photo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, full_name, password_hash, username, phone, email, address, profile)

            log_audit(
                db=db,
                action='create',
                table_name='members',
                record_id=new_member_id,
                description=f"New member account created for {full_name}",
                member_id=session.get('user_id')
            )

            flash(f"Account created for {full_name}.", "success")
            return redirect(url_for('members.list_members'))

        except Exception as e:
            error_msg = str(e).lower()
            if "unique" in error_msg or "duplicate key" in error_msg:
                flash("Username or email already exists. Please choose another.", "error")
            else:
                flash(f"Database error: {str(e)}", "error")
            return render_template('add_member.html', active_page='members')

    return render_template('add_member.html', active_page='members')


@members_bp.route('/contributions/record', methods=['GET', 'POST'])
@login_required
def record_contribution():
    db = get_db()

    if request.method == 'POST':
        member_id = request.form.get('member_id')
        amount = float(request.form.get('amount') or 0)
        method = request.form.get('method', 'Bank Transfer')
        reference = (request.form.get('reference') or '').strip()
        notes = (request.form.get('notes') or '').strip()

        if not member_id or amount <= 0:
            flash("Invalid input. Please check the amount and member selection.", "error")
            return redirect(url_for('members.record_contribution'))

        try:
            # 1. Verify member exists
            res_member = db.execute(
                "SELECT full_name FROM members WHERE id = %s", member_id
            )
            if not res_member:
                flash("Member not found.", "error")
                return redirect(url_for('members.record_contribution'))

            member_name = res_member[0]['full_name']

            # 2. Insert contribution
            new_contribution_id = db.execute("""
                INSERT INTO contributions (
                    member_id, amount, payment_method, reference, notes, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, member_id, amount, method, reference, notes, session['user_id'])

            # 3. Log transaction
            db.execute("""
                INSERT INTO transactions (
                    transaction_type, amount, description,
                    reference_id, reference_table, created_by
                ) VALUES ('contribution', %s, %s, %s, 'contributions', %s)
            """,
                amount,
                f"Contribution of ₦{amount:,.2f} via {method} by {member_name} — {reference}",
                new_contribution_id,
                session['user_id']
            )

            # 4. Audit log
            log_audit(
                db=db,
                action='create',
                table_name='contributions',
                record_id=new_contribution_id,
                description=f"Contribution of ₦{amount:,.2f} recorded for {member_name} (ID: {member_id})",
                member_id=session.get('user_id')
            )

            flash("Contribution recorded successfully.", "success")
            return redirect(url_for('transactions.list_transactions'))

        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('members.record_contribution'))

    # GET
    try:
        active_members = db.execute("""
            SELECT
                m.id,
                m.full_name,
                m.username,
                COALESCE(SUM(c.amount), 0) as total_contributions
            FROM members m
            LEFT JOIN contributions c ON c.member_id = m.id
            WHERE m.status = 'active'
            GROUP BY m.id
            ORDER BY m.full_name ASC
        """)
    except Exception:
        active_members = []

    return render_template('contribution.html', active_page='members', members_list=active_members)
