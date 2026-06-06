from datetime import datetime
import os
import sqlite3
from werkzeug.security import generate_password_hash
from flask import Blueprint, render_template, request, redirect, session, url_for, flash

from helpers import admin_required, get_db, log_audit, login_required

members_bp = Blueprint('members', __name__)

@members_bp.route('/members')
@login_required
def list_members():
    try:
        # Get the CS50 SQL execution object
        db = get_db()

        # Fetch all members
        # CS50 automatically returns a list of mutable dictionaries
        members_from_db = db.execute("SELECT * FROM members ORDER BY id DESC")

        # Convert date format for display
        for m in members_from_db:
            # No need for m = dict(m); CS50 dicts are already standard and mutable!
            if m['date_joined']:
                m['date_joined'] = datetime.strptime(m['date_joined'], '%Y-%m-%d').strftime('%d-%m-%Y')

        # Total members count
        res_total = db.execute("SELECT COUNT(*) as count FROM members WHERE status = 'active'")
        total_members = res_total[0]['count']

        # Average contribution per member
        res_avg = db.execute("""
            SELECT COALESCE(AVG(total), 0) as avg
            FROM (
                SELECT SUM(amount) as total
                FROM contributions
                GROUP BY member_id
            )
        """)
        avg_contribution = res_avg[0]['avg']

        # Active members count (for percentage calculation)
        res_active = db.execute("""
            SELECT COUNT(*) as count FROM members WHERE status = 'active'
        """)
        active_count = res_active[0]['count']

        active_share = round((active_count / total_members * 100), 1) if total_members > 0 else 0

        return render_template('members.html',
            active_page='members',
            members=members_from_db,  # Pass the updated list directly
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

        # 1. Extract form fields
        full_name = request.form.get('fullName', '').strip().title()
        username  = request.form.get('username', '').strip()
        phone     = request.form.get('phone', '').strip()
        email     = request.form.get('email', '').strip()
        address   = request.form.get('address', '').strip()
        profile   = request.form.get('profile', '').strip()
        password  = request.form.get('password', '')
        cpassword = request.form.get('Cpassword', '')

        # 2. Validate passwords before touching the database
        if password != cpassword:
            flash("Password and confirm password do not match.", "error")
            return render_template('add_member.html', active_page='members')
            
        # Check if username or email already exists
        db = get_db()
        existing = db.execute(
            "SELECT id FROM members WHERE username = %s OR email = %s",
            username, email
        )
        if existing:
            flash("Username or email already taken. Please choose another.", "error")
            return render_template('add_member.html', active_page='members')

        # 3. Hash — never store raw text
        password_hash = generate_password_hash(password)

        # 4. Insert
        try:
            db = get_db()  # Get the CS50 SQL execution object
            
            # CS50 .execute() returns the auto-incremented ID on INSERT statements directly
            new_member_id = db.execute("""
                INSERT INTO members (
                    full_name, password_hash, username, phone, email, address, profile_photo
                ) VALUES (:full_name, :password_hash, :username, :phone, :email, :address, :profile)
            """, 
                full_name=full_name, password_hash=password_hash, username=username, 
                phone=phone, email=email, address=address, profile=profile
            )
            
            # Trigger the audit log tracking payload (passing CS50 db reference directly)
            log_audit(
                db=db, 
                action='create', 
                table_name='members', 
                record_id=new_member_id,
                description=f"New member account created for {full_name}",
                member_id=session.get('user_id')  # Tracks WHO did it
            )


            flash(f"Account created for {full_name}.", "success")
            return redirect(url_for('members.list_members'))

        except Exception as e:
            # CS50 wraps standard errors. We parse the error string to catch unique/integrity constraint drops.
            error_msg = str(e).lower()
            if "unique" in error_msg or "duplicate key" in error_msg:
                flash("Username or email already exists. Please choose another.", "error")
            else:
                flash(f"Database error: {str(e)}", "error")
                
            return render_template('add_member.html', active_page='members')

    return render_template('add_member.html', active_page='members')


# Handle Recording of New Contributions Workflow Pipeline
@members_bp.route('/contributions/record', methods=['GET', 'POST'])
@login_required
def record_contribution():
    db = get_db()  # Get the CS50 SQL execution object

    if request.method == 'POST':
        member_id = request.form.get('member_id')
        amount = float(request.form.get('amount') or 0)
        method = request.form.get('method', 'Bank Transfer')
        reference = request.form.get('reference', '').strip()
        notes = request.form.get('notes', '').strip()

        if not member_id or amount <= 0:
            flash("Invalid input. Please check the amount and member selection.", "error")
            return redirect(url_for('members.record_contribution'))

        try:
            # 1. Get member name for the transaction description
            res_member = db.execute("SELECT full_name FROM members WHERE id = :id", id=member_id)
            
            if not res_member:
                flash("Member not found.", "error")
                return redirect(url_for('members.record_contribution'))
            
            # Since CS50 always returns a dict, we extract directly by key name
            member_name = res_member[0]['full_name']

            # 2. Insert into contributions table
            # CS50 .execute() returns the auto-incremented ID on INSERT statements directly
            new_contribution_id = db.execute("""
                INSERT INTO contributions (
                    member_id, amount, payment_method, reference, notes, created_by
                ) VALUES (:member_id, :amount, :method, :reference, :notes, :creator)
            """, 
                member_id=member_id, amount=amount, method=method, 
                reference=reference, notes=notes, creator=session['user_id']
            )

            # 3. Log in transactions table
            db.execute("""
                INSERT INTO transactions (
                    transaction_type, amount, description,
                    reference_id, reference_table, created_by
                ) VALUES ('contribution', :amount, :desc, :ref_id, 'contributions', :creator)
            """, 
                amount=amount,
                desc=f"Contribution of ₦{amount:,.2f} via {method} by {member_name} — {reference}",
                ref_id=new_contribution_id,
                creator=session['user_id']
            )

            # 4. Trigger the audit log wrapper
            log_audit(
                db=db, 
                action='create', 
                table_name='contributions', 
                record_id=new_contribution_id,
                description=f"Contribution of ₦{amount:,.2f} recorded for member: {member_name} (ID: {member_id})",
                member_id=session.get('user_id')
            )
            
            # No conn.commit() needed; CS50 handles it automatically!

            flash("Contribution recorded successfully.", "success")
            return redirect(url_for('transactions.list_transactions'))

        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('members.record_contribution'))

    # GET REQUEST
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
