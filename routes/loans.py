import os
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from helpers import admin_required, get_db, login_required

loans_bp = Blueprint('loans', __name__)


def resolve_loan_status(amount_paid, total_repayable, due_date):
    """
    Accepts either a date object or string — PostgreSQL returns date objects.
    """
    balance = total_repayable - amount_paid

    # <= 0 covers exact payment and floating point overshoot
    if balance <= 0:
        return 'completed'

    if isinstance(due_date, str):
        due = datetime.strptime(due_date, '%Y-%m-%d').date()
    else:
        due = due_date

    today = date.today()

    if today > due:
        days_overdue = (today - due).days
        return 'defaulted' if days_overdue > 33 else 'overdue'

    return 'active'


def fmt_date(value, fmt='%d-%m-%Y'):
    """Safely format a date or datetime — handles both objects and strings."""
    if not value:
        return ''
    if isinstance(value, (date, datetime)):
        return value.strftime(fmt)
    try:
        return datetime.strptime(str(value).split('.')[0], '%Y-%m-%d %H:%M:%S').strftime(fmt)
    except ValueError:
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').strftime(fmt)
        except ValueError:
            return str(value)


@loans_bp.route('/loans')
@login_required
def view_loans():
    try:
        db = get_db()

        raw_loans = db.execute("""
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

        res_portfolio = db.execute("""
            SELECT COALESCE(SUM(balance_remaining), 0.0) as total_portfolio
            FROM loans WHERE status != 'completed'
        """)
        total_portfolio_sum = res_portfolio[0]['total_portfolio']

        processed_portfolio = []

        for loan_dict in raw_loans:
            correct_status = resolve_loan_status(
                loan_dict['amount_paid'],
                loan_dict['total_repayable'],
                loan_dict['due_date']  # PostgreSQL date object — handled in resolve_loan_status
            )

            if correct_status != loan_dict['status']:
                db.execute(
                    "UPDATE loans SET status = %s WHERE id = %s",
                    correct_status, loan_dict['loan_id']
                )
                loan_dict['status'] = correct_status

            status_lower = loan_dict['status'].lower()
            principal = loan_dict['principal']
            amount_paid = loan_dict['amount_paid']
            total_repayable = loan_dict['total_repayable']

            progress_percentage = (
                min(100, max(0, int((amount_paid / total_repayable) * 100)))
                if total_repayable > 0 else 0
            )

            # PostgreSQL returns date objects — use fmt_date helper
            due_formatted = fmt_date(loan_dict['due_date'])

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
                "raw_id": loan_dict['loan_id'],
                "id": f"STW-{loan_dict['loan_id']:04d}-LO",
                "name": loan_dict['borrower_name'],
                "status": loan_dict['status'].title(),
                "amount": principal,
                "paid": amount_paid,
                "balance": loan_dict['balance_remaining'],
                "rate": f"{loan_dict['interest_rate']}% APR",
                "progress": f"{progress_percentage}%",
                "border_color": border_color,
                "status_class": status_class,
                "progress_class": progress_class,
                "icon": icon,
                "date_label": date_label
            })

        processed_portfolio.sort(
            key=lambda x: (
                # 1. Primary Sort: Push 'Paid' (True/1) below 'Due' (False/0)
                x['date_label'].startswith('Paid:'),
                
                # 2. Secondary Sort: Extract and parse the string date into an actual datetime object
                datetime.strptime(x['date_label'].split(': ')[1], '%d-%m-%Y')
            )
        )

        return render_template(
            'loans.html',
            active_page='loans',
            loans=processed_portfolio,
            total_balance=total_portfolio_sum
        )

    except Exception as e:
        flash(f"Failed to load loans: {str(e)}", "error")
        return render_template('loans.html', active_page='loans', loans=[], total_balance=0.0)


@loans_bp.route('/loans/add', methods=['GET', 'POST'])
@admin_required
def add_loan():
    db = get_db()

    if request.method == 'POST':
        is_existing = request.form.get('is_existing') == 'true'
        principal = float(request.form.get('principal') or 0)
        interest_rate = float(request.form.get('interest_rate') or 0)

        if principal <= 0:
            flash("Invalid principal amount.", "error")
            return redirect(url_for('loans.add_loan'))

        try:
            # START DATABASE TRANSACTION IF APPLICABLE (e.g. db.begin() or connection context)
            
            # -----------------------------------------------------------------
            # STEP 1: RESOLVE BORROWER & PREVENT CONCURRENT LOANS
            # -----------------------------------------------------------------
            if is_existing:
                borrower_id = request.form.get('borrower_id', type=int)
                if not borrower_id:
                    flash("Please select a borrower.", "error")
                    return redirect(url_for('loans.add_loan'))

                res_borrower = db.execute(
                    "SELECT full_name FROM borrowers WHERE id = %s", borrower_id
                )
                if not res_borrower:
                    flash("Selected borrower does not exist.", "error")
                    return redirect(url_for('loans.add_loan'))

                borrower_name = res_borrower[0]['full_name']
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

                # IDEMPOTENCY CHECK 2: Catch duplicate new borrower creation by phone within same session
                if phone:
                    existing_by_phone = db.execute(
                        "SELECT id FROM borrowers WHERE phone = %s", phone
                    )
                    if existing_by_phone:
                        flash("A borrower with this phone number already exists.", "error")
                        return redirect(url_for('loans.add_loan'))

                borrower_id = db.execute("""
                    INSERT INTO borrowers (
                        full_name, phone, address, occupation, guarantor_name, guarantor_phone
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, borrower_name, phone, address, occupation, guarantor_name, guarantor_phone)

            # -----------------------------------------------------------------
            # STEP 2: FINANCIAL CALCULATIONS
            # -----------------------------------------------------------------
            interest_amount = principal * (interest_rate / 100)
            total_repayable = principal + interest_amount
            loan_start_date = date.today()
            due_date = loan_start_date + timedelta(days=30)
            user_id = session.get('user_id')

            # -----------------------------------------------------------------
            # STEP 3: INSERT LOAN RECORD
            # -----------------------------------------------------------------
            new_loan_id = db.execute("""
                INSERT INTO loans (
                    borrower_id, principal, interest_rate, interest_amount,
                    total_repayable, balance_remaining,
                    loan_start_date, due_date, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, borrower_id, principal, interest_rate, interest_amount,
                total_repayable, total_repayable,
                loan_start_date, due_date, user_id
            )

            # -----------------------------------------------------------------
            # STEP 4: LOG TRANSACTION
            # -----------------------------------------------------------------
            db.execute("""
                INSERT INTO transactions (
                    transaction_type, amount, description, reference_id, reference_table, created_by
                ) VALUES ('loan_disbursement', %s, %s, %s, 'loans', %s)
            """,
                principal,
                f"Loan of ₦{principal:,.2f} disbursed to {borrower_name} at {interest_rate}% APR.",
                new_loan_id,
                user_id
            )

            # -----------------------------------------------------------------
            # STEP 5: UPDATE BORROWER LOAN METRICS
            # -----------------------------------------------------------------
            db.execute(
                "UPDATE borrowers SET total_loan = total_loan + 1 WHERE id = %s", borrower_id
            )

            # -----------------------------------------------------------------
            # STEP 6: APPLY STAMP DUTY FEE
            # -----------------------------------------------------------------
            if principal > 9999:
                db.execute("""
                    INSERT INTO fees (loan_id, fee_type, amount, payer_type, payer_id)
                    VALUES (%s, 'stamp duty', 50.0, 'borrower', %s)
                """, new_loan_id, borrower_id)

            # COMMIT TRANSACTION HERE (e.g. db.commit())

            flash(f"Loan disbursed successfully for {borrower_name}.", "success")
            return redirect(url_for('loans.view_loans'))

        except Exception as e:
            # ROLLBACK TRANSACTION HERE (e.g. db.rollback())
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('loans.add_loan'))

    # GET REQUEST
    try:
        historical_borrowers_list = db.execute(
            "SELECT id, full_name, phone, address, occupation FROM borrowers ORDER BY full_name ASC"
        )
    except Exception:
        historical_borrowers_list = []

    return render_template('add_loan.html', active_page='loans', existing_borrowers=historical_borrowers_list)

@loans_bp.route('/loans/<int:loan_id>/repayment', methods=['GET', 'POST'])
@admin_required
def record_repayment(loan_id):
    db = get_db()

    if request.method == 'POST':
        payment = float(request.form.get('payment_amount') or 0)
        payment_method = request.form.get('payment_method', 'Bank Transfer')
        notes = request.form.get('notes', '').strip()

        if payment <= 0:
            flash("Payment amount must be greater than zero.", "error")
            return redirect(url_for('loans.record_repayment', loan_id=loan_id))

        try:
            res_loan = db.execute("""
                SELECT 
                    l.id, l.principal, l.total_repayable, l.amount_paid,
                    l.balance_remaining, l.due_date, l.status,
                    b.full_name as borrower_name, l.borrower_id
                FROM loans l
                JOIN borrowers b ON l.borrower_id = b.id
                WHERE l.id = %s
            """, loan_id)

            loan = res_loan[0] if res_loan else None

            if not loan:
                flash("Loan record not found.", "error")
                return redirect(url_for('loans.view_loans'))

            if loan['status'] == 'completed':
                flash("This loan is already fully repaid.", "error")
                return redirect(url_for('loans.view_loans'))

            # Accept the full payment — no cap
            new_amount_paid = loan['amount_paid'] + payment

            # Overpayment amount — could be a tip, penalty, or overdue charge
            overpayment = max(0.0, new_amount_paid - loan['total_repayable'])

            # Balance floors at 0 — never goes negative in the DB
            new_balance = max(0.0, loan['total_repayable'] - new_amount_paid)

            new_status = resolve_loan_status(
                new_amount_paid, loan['total_repayable'], loan['due_date']
            )

            db.execute("""
                UPDATE loans 
                SET amount_paid = %s, balance_remaining = %s, status = %s
                WHERE id = %s
            """, new_amount_paid, new_balance, new_status, loan_id)

            # Build description — note overpayment if present
            if overpayment > 0:
                extra_note = (f" Includes ₦{overpayment:,.2f} above total repayable "
                            f"(tip/penalty/overdue charge).")
            else:
                extra_note = ""

            db.execute("""
                INSERT INTO transactions (
                    transaction_type, amount, description, 
                    reference_id, reference_table, created_by
                ) VALUES ('repayment', %s, %s, %s, 'loans', %s)
            """, 
                payment,
                (f"Repayment of ₦{payment:,.2f} on loan #{loan_id:04d} "
                f"by {loan['borrower_name']} via {payment_method}. "
                f"Balance: ₦{new_balance:,.2f}. Status → {new_status}."
                + extra_note
                + (f" Note: {notes}" if notes else "")),
                loan_id,
                session.get('user_id')
            )

            status_msg = " Loan marked as completed!" if new_status == 'completed' else ""
            overpay_msg = f" ₦{overpayment:,.2f} recorded as extra payment." if overpayment > 0 else ""
            flash(
                f"Repayment of ₦{payment:,.2f} recorded for {loan['borrower_name']}.{status_msg}{overpay_msg}",
                "success"
            )
            return redirect(url_for('loans.view_loans'))

        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('loans.record_repayment', loan_id=loan_id))

    # --- GET REQUEST HANDLER (Fix for 500 error) ---
    # --- GET Request Handler ---
    res_loan = db.execute("""
        SELECT 
            l.id, l.principal, l.total_repayable, l.amount_paid,
            l.balance_remaining, l.due_date, l.status,
            b.full_name as borrower_name, b.occupation, b.phone,
            l.loan_start_date, l.interest_rate, l.borrower_id
        FROM loans l
        JOIN borrowers b ON l.borrower_id = b.id
        WHERE l.id = %s
    """, loan_id)

    loan = res_loan[0] if res_loan else None

    if not loan:
        flash("Loan record not found.", "error")
        return redirect(url_for('loans.view_loans'))

    # Fetch repayment history using your exact transactions schema
    repayment_history = db.execute("""
        SELECT amount, created_at, description
        FROM transactions
        WHERE reference_id = %s 
          AND reference_table = 'loans' 
          AND transaction_type = 'repayment'
        ORDER BY created_at DESC
    """, loan_id)

    return render_template('record_repayment.html', loan=loan, repayment_history=repayment_history)
