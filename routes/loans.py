import os
import sqlite3
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from helpers import admin_required, get_db, log_audit, login_required


loans_bp = Blueprint('loans', __name__)

def resolve_loan_status(amount_paid, total_repayable, due_date_str):
    """Derives correct status from financials and date. Call anywhere."""
    balance = total_repayable - amount_paid

    if balance <= 0:
        return 'completed'

    due = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    today = date.today()

    if today > due:
        days_overdue = (today - due).days
        return 'defaulted' if days_overdue > 33 else 'overdue'

    return 'active'


@loans_bp.route('/loans')
@login_required
def view_loans():
    try:
        with get_db() as conn:
            # Crucial: ensure rows can be accessed via key-name lookups
            conn.row_factory = sqlite3.Row
            db = conn.cursor()

            db.execute("""
                SELECT
                    l.id AS loan_id,
                    b.full_name AS borrower_name,
                    l.principal,
                    l.interest_rate,
                    l.total_repayable,
                    l.amount_paid,
                    l.balance_remaining,
                    l.due_date,
                    l.status
                FROM loans l
                JOIN borrowers b ON l.borrower_id = b.id
                ORDER BY l.id DESC
            """)
            raw_loans = db.fetchall()

            db.execute("SELECT SUM(balance_remaining) FROM loans WHERE status != 'completed'")
            total_portfolio_sum = db.fetchone()[0] or 0.0

            # Convert rows to mutable dictionaries so we can modify stale statuses on the fly
            processed_loans_data = []

            for row in raw_loans:
                loan_dict = dict(row)
                correct_status = resolve_loan_status(
                    loan_dict['amount_paid'], loan_dict['total_repayable'], loan_dict['due_date']
                )
                
                # If the status in the DB is wrong, update the DB AND our active dictionary tracking object
                if correct_status != loan_dict['status']:
                    db.execute(
                        "UPDATE loans SET status = ? WHERE id = ?",
                        (correct_status, loan_dict['loan_id'])
                    )
                    loan_dict['status'] = correct_status  # <-- Fixes the in-memory lag instantly
                
                processed_loans_data.append(loan_dict)
                
            conn.commit()
            
        processed_portfolio = []
        # Loop over our fresh, updated array data instead of the old raw_loans cursor footprint
        for row in processed_loans_data:
            status_lower = row['status'].lower()
            principal = row['principal']
            amount_paid = row['amount_paid']
            total_repayable = row['total_repayable']

            progress_percentage = min(100, max(0, int((amount_paid / total_repayable) * 100))) if principal > 0 else 0
            
            # Format date to "Due: DD-MM-YYYY" or "Paid: DD-MM-YYYY" based on status
            due_formatted = datetime.strptime(row['due_date'], '%Y-%m-%d').strftime('%d-%m-%Y')

            if status_lower == 'overdue':
                border_color = "border-error"
                status_class = "bg-error-container text-on-error-container border-error/20"
                progress_class = "bg-error"
                icon = "warning"
                date_label = f"Due: {due_formatted}"
            elif status_lower == 'completed':
                border_color = "border-secondary"
                status_class = "bg-secondary-container text-on-secondary-container border-secondary/20"
                progress_class = "bg-secondary"
                icon = "check_circle"
                date_label = f"Paid: {due_formatted}"
            elif status_lower == 'defaulted':
                border_color = "border-outline"
                status_class = "bg-inverse-surface text-inverse-on-surface"
                progress_class = "bg-outline"
                icon = "gavel"
                date_label = f"Breached: {due_formatted}"
            else:
                border_color = "border-primary"
                status_class = "bg-primary-fixed text-primary border-primary/20"
                progress_class = "bg-primary"
                icon = "account_balance_wallet"
                date_label = f"Due: {due_formatted}"

            processed_portfolio.append({
                "raw_id": row['loan_id'],
                "id": f"STW-{row['loan_id']:04d}-LO",
                "name": row['borrower_name'],
                "status": row['status'].title(), # Now guaranteed to reflect the fresh status updates
                "amount": principal,
                "paid": amount_paid,
                "balance": row['balance_remaining'],
                "rate": f"{row['interest_rate']}% APR",
                "progress": f"{progress_percentage}%",
                "border_color": border_color,
                "status_class": status_class,
                "progress_class": progress_class,
                "icon": icon,
                "date_label": date_label
            })

        processed_portfolio.sort(key=lambda x: x['date_label'])

        return render_template(
            'loans.html',
            active_page='loans',
            loans=processed_portfolio,
            total_balance=total_portfolio_sum
        )

    except sqlite3.Error as e:
        flash(f"Failed to load loans: {str(e)}", "error")
        return render_template('loans.html', active_page='loans', loans=[], total_balance=0.0)


@loans_bp.route('/loans/add', methods=['GET', 'POST'])
@admin_required
def add_loan():
    if request.method == 'POST':
        is_existing = request.form.get('is_existing') == 'true'
        principal = request.form.get('principal', 0, type=float)

        if principal <= 0:
            flash("Invalid principal amount.", "error")
            return redirect(url_for('loans.add_loan'))

        try:
            with get_db() as conn:
                db = conn.cursor()

                # STEP 1: RESOLVE BORROWER
                if is_existing:
                    borrower_id = request.form.get('borrower_id', type=int)
                    if not borrower_id:
                        flash("Please select a borrower.", "error")
                        return redirect(url_for('loans.add_loan'))
                    db.execute("SELECT full_name FROM borrowers WHERE id = ?", (borrower_id,))
                    row = db.fetchone()
                    borrower_name = row[0] if row else "Existing Borrower"
                else:
                    borrower_name = request.form.get('full_name', '').strip().title()
                    phone = request.form.get('phone', '').strip()
                    address = request.form.get('address', '').strip()
                    occupation = request.form.get('occupation', '').strip()
                    guarantor_name = request.form.get('guarantor_name', '').strip().title()
                    guarantor_phone = request.form.get('guarantor_phone', '').strip()

                    if not borrower_name:
                        flash("Borrower name is required.", "error")
                        return redirect(url_for('loans.add_loan'))

                    db.execute("""
                        INSERT INTO borrowers (
                            full_name, phone, address, occupation, guarantor_name, guarantor_phone
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (borrower_name, phone, address, occupation, guarantor_name, guarantor_phone))
                    borrower_id = db.lastrowid

                # STEP 2: CALCULATE
                interest_rate = request.form.get('interest_rate', 0, type=float)
                interest_amount = principal * (interest_rate / 100)
                total_repayable = principal + interest_amount
                loan_start_date = date.today()
                due_date = loan_start_date + timedelta(days=30)

                # STEP 3: INSERT LOAN
                db.execute("""
                    INSERT INTO loans (
                        borrower_id, principal, interest_rate, interest_amount,
                        total_repayable, balance_remaining,
                        loan_start_date, due_date, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    borrower_id, principal, interest_rate, interest_amount,
                    total_repayable, total_repayable,
                    loan_start_date, due_date, session['user_id']
                ))
                new_loan_id = db.lastrowid

                # STEP 4: LOG TRANSACTION
                db.execute("""
                    INSERT INTO transactions (
                        transaction_type, amount, description, reference_id, reference_table, created_by
                    ) VALUES ('loan_disbursement', ?, ?, ?, 'loans', ?)
                """, (
                    principal,
                    f"Loan of ₦{principal:,.2f} disbursed to {borrower_name} at {interest_rate}% APR.",
                    new_loan_id,
                    session.get('user_id')
                ))

                # Update borrowers table with total_loan count
                db.execute("UPDATE borrowers SET total_loan = total_loan + 1 WHERE id = ?", (borrower_id,))

                # STEP 6: STAMP DUTY
                if principal > 10000:
                    db.execute("""
                        INSERT INTO fees (loan_id, fee_type, amount, payer_type, payer_id)
                        VALUES (?, 'stamp duty', 50.0, 'borrower', ?)
                    """, (new_loan_id, borrower_id))

                conn.commit()

            flash(f"Loan disbursed successfully for {borrower_name}.", "success")
            return redirect(url_for('loans.view_loans'))

        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('loans.add_loan'))

    # GET
    try:
        with get_db() as conn:
            db = conn.cursor()
            db.execute("SELECT id, full_name, phone, address, occupation FROM borrowers ORDER BY full_name ASC")
            historical_borrowers_list = db.fetchall()
    except sqlite3.Error:
        historical_borrowers_list = []

    return render_template('add_loan.html', active_page='loans', existing_borrowers=historical_borrowers_list)


@loans_bp.route('/loans/<int:loan_id>/repayment', methods=['GET', 'POST'])
@admin_required
def record_repayment(loan_id):
    if request.method == 'POST':
        payment = float(request.form.get('payment_amount') or 0)
        payment_method = request.form.get('payment_method', 'Bank Transfer')
        notes = request.form.get('notes', '').strip()

        if payment <= 0:
            flash("Payment amount must be greater than zero.", "error")
            return redirect(url_for('loans.record_repayment', loan_id=loan_id))

        try:
            with get_db() as conn:
                db = conn.cursor()

                db.execute("""
                    SELECT
                        l.id, l.principal, l.total_repayable, l.amount_paid,
                        l.balance_remaining, l.due_date, l.status,
                        b.full_name as borrower_name, l.borrower_id
                    FROM loans l
                    JOIN borrowers b ON l.borrower_id = b.id
                    WHERE l.id = ?
                """, (loan_id,))
                loan = db.fetchone()

                if not loan:
                    flash("Loan record not found.", "error")
                    return redirect(url_for('loans.view_loans'))

                if loan['status'] == 'completed':
                    flash("This loan is already fully repaid.", "error")
                    return redirect(url_for('loans.view_loans'))

                # Cap payment at remaining balance
                actual_payment = min(payment, loan['balance_remaining'])
                new_amount_paid = loan['amount_paid'] + actual_payment
                new_balance = loan['total_repayable'] - new_amount_paid
                new_status = resolve_loan_status(
                    new_amount_paid, loan['total_repayable'], loan['due_date']
                )

                db.execute("""
                    UPDATE loans
                    SET amount_paid = ?, balance_remaining = ?, status = ?
                    WHERE id = ?
                """, (new_amount_paid, new_balance, new_status, loan_id))

                db.execute("""
                    INSERT INTO transactions (
                        transaction_type, amount, description,
                        reference_id, reference_table, created_by
                    ) VALUES ('repayment', ?, ?, ?, 'loans', ?)
                """, (
                    actual_payment,
                    f"Repayment of ₦{actual_payment:,.2f} on loan #{loan_id:04d} "
                    f"by {loan['borrower_name']} via {payment_method}. "
                    f"Balance: ₦{new_balance:,.2f}. Status → {new_status}."
                    + (f" Note: {notes}" if notes else ""),
                    loan_id,
                    session.get('user_id')
                ))

                log_audit(db, 'update', 'loans', loan_id,
                    f"Repayment of ₦{actual_payment:,.2f}. "
                    f"Status → '{new_status}'. Balance: ₦{new_balance:,.2f}.",
                    member_id=session.get('user_id')
                )

                conn.commit()

            status_msg = " Loan marked as completed!" if new_status == 'completed' else ""
            flash(f"Repayment of ₦{actual_payment:,.2f} recorded for {loan['borrower_name']}.{status_msg}", "success")
            return redirect(url_for('loans.view_loans'))

        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('loans.record_repayment', loan_id=loan_id))

    # GET
    try:
        with get_db() as conn:
            # Crucial: ensure rows can be accessed via key-name lookups
            conn.row_factory = sqlite3.Row 
            db = conn.cursor()
            
            db.execute("""
                SELECT
                    l.id, l.principal, l.interest_rate, l.total_repayable,
                    l.amount_paid, l.balance_remaining, l.due_date,
                    l.loan_start_date, l.status,
                    b.full_name as borrower_name, b.phone, b.occupation
                FROM loans l
                JOIN borrowers b ON l.borrower_id = b.id
                WHERE l.id = ?
            """, (loan_id,))
            raw_loan = db.fetchone()

            if not raw_loan:
                flash("Loan not found.", "error")
                return redirect(url_for('loans.view_loans'))

            # Convert to a mutable dictionary so we can overwrite string dates dynamically
            loan = dict(raw_loan)
            
            # Helper function to convert "YYYY-MM-DD" text into "Oct 24, 2023"
            def clean_date(date_str):
                if not date_str:
                    return ""
                try:
                    return datetime.strptime(str(date_str), "%Y-%m-%d").strftime("%b %d, %Y")
                except ValueError:
                    return date_str # Fallback to raw string if format variant mismatches

            # Update dates safely inline
            loan['due_date'] = clean_date(loan.get('due_date'))
            loan['loan_start_date'] = clean_date(loan.get('loan_start_date'))

            # Fetch transaction histories
            db.execute("""
                SELECT amount, description, created_at
                FROM transactions
                WHERE reference_table = 'loans'
                AND reference_id = ?
                AND transaction_type = 'repayment'
                ORDER BY created_at DESC
            """, (loan_id,))
            raw_history = db.fetchall()
            
            # Reformat the timestamp string on history lists if necessary
            repayment_history = []
            for row in raw_history:
                item = dict(row)
                # SQLite TIMESTAMP defaults to "YYYY-MM-DD HH:MM:SS"
                if item.get('created_at'):
                    try:
                        ts = datetime.strptime(item['created_at'].split('.')[0], "%Y-%m-%d %H:%M:%S")
                        item['created_at'] = ts.strftime("%b %d, %Y %I:%M %p")
                    except ValueError:
                        pass
                repayment_history.append(item)

    except sqlite3.Error as e:
        flash(f"Database error: {str(e)}", "error")
        return redirect(url_for('loans.view_loans'))

    return render_template('record_repayment.html',
        active_page='loans',
        loan=loan,
        repayment_history=repayment_history
    )
