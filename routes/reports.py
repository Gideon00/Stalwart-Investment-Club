import csv
import io
from datetime import datetime, date
from flask import Blueprint, render_template, request, Response, flash
from helpers import get_db, login_required

reports_bp = Blueprint('reports', __name__)


def get_month_range(month_str):
    """Convert 'YYYY-MM' string to first and last day of that month."""
    dt = datetime.strptime(month_str, '%Y-%m')
    # First day
    first_day = dt.date().replace(day=1)
    # Last day — go to next month then subtract one day
    if first_day.month == 12:
        last_day = first_day.replace(year=first_day.year + 1, month=1, day=1)
    else:
        last_day = first_day.replace(month=first_day.month + 1, day=1)
    return first_day, last_day


@reports_bp.route('/reports')
@login_required
def view_reports():
    db = get_db()

    # Default to current month if no param provided
    month_str = request.args.get('month', date.today().strftime('%Y-%m'))

    try:
        first_day, last_day = get_month_range(month_str)
    except ValueError:
        flash("Invalid month format.", "error")
        month_str = date.today().strftime('%Y-%m')
        first_day, last_day = get_month_range(month_str)

    # ── Summary cards ──

    res_contributions = db.execute("""
        SELECT
            COALESCE(SUM(amount), 0) as total,
            COUNT(*) as count
        FROM contributions
        WHERE contribution_date >= %s AND contribution_date < %s
    """, first_day, last_day)
    contrib_summary = res_contributions[0]

    res_disbursed = db.execute("""
        SELECT
            COALESCE(SUM(principal), 0) as total,
            COUNT(*) as count
        FROM loans
        WHERE loan_start_date >= %s AND loan_start_date < %s
    """, first_day, last_day)
    disbursed_summary = res_disbursed[0]

    res_repayments = db.execute("""
        SELECT
            COALESCE(SUM(amount), 0) as total,
            COUNT(*) as count
        FROM transactions
        WHERE transaction_type = 'repayment'
        AND created_at >= %s AND created_at < %s
    """, first_day, last_day)
    repayment_summary = res_repayments[0]

    res_interest = db.execute("""
        SELECT COALESCE(SUM(interest_amount), 0) as total
        FROM loans
        WHERE loan_start_date >= %s AND loan_start_date < %s
    """, first_day, last_day)
    interest_earned = res_interest[0]['total']

    res_fees = db.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM fees
        WHERE created_at >= %s AND created_at < %s
    """, first_day, last_day)
    fees_collected = res_fees[0]['total']

    net_movement = (
        float(contrib_summary['total']) +
        float(repayment_summary['total']) -
        float(disbursed_summary['total'])
    )

    # ── Contributions breakdown ──
    contributions = db.execute("""
        SELECT
            m.full_name as member_name,
            c.amount,
            c.payment_method,
            c.reference,
            c.contribution_date,
            c.notes
        FROM contributions c
        JOIN members m ON c.member_id = m.id
        WHERE c.contribution_date >= %s AND c.contribution_date < %s
        ORDER BY c.contribution_date DESC
    """, first_day, last_day)

    for row in contributions:
        if row['contribution_date']:
            row['contribution_date'] = (
                row['contribution_date'].strftime('%d-%m-%Y')
                if not isinstance(row['contribution_date'], str)
                else row['contribution_date']
            )

    # ── Loans disbursed ──
    loans_disbursed = db.execute("""
        SELECT
            b.full_name as borrower_name,
            l.principal,
            l.interest_rate,
            l.interest_amount,
            l.total_repayable,
            l.balance_remaining,
            l.loan_start_date,
            l.due_date,
            l.status
        FROM loans l
        JOIN borrowers b ON l.borrower_id = b.id
        WHERE l.loan_start_date >= %s AND l.loan_start_date < %s
        ORDER BY l.loan_start_date DESC
    """, first_day, last_day)

    for row in loans_disbursed:
        for col in ['loan_start_date', 'due_date']:
            if row[col]:
                row[col] = (
                    row[col].strftime('%d-%m-%Y')
                    if not isinstance(row[col], str)
                    else row[col]
                )

    # ── Repayments ──
    repayments = db.execute("""
        SELECT
            b.full_name as borrower_name,
            t.amount,
            t.description,
            t.created_at,
            l.balance_remaining,
            l.status
        FROM transactions t
        JOIN loans l ON t.reference_id = l.id
        JOIN borrowers b ON l.borrower_id = b.id
        WHERE t.transaction_type = 'repayment'
        AND t.reference_table = 'loans'
        AND t.created_at >= %s AND t.created_at < %s
        ORDER BY t.created_at DESC
    """, first_day, last_day)

    for row in repayments:
        if row['created_at']:
            row['created_at'] = (
                row['created_at'].strftime('%d-%m-%Y %H:%M')
                if not isinstance(row['created_at'], str)
                else row['created_at']
            )

    # Build list of last 12 months for the month selector
    today = date.today()
    month_options = []
    for i in range(12):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_options.append({
            'value': f'{y}-{m:02d}',
            'label': datetime(y, m, 1).strftime('%B %Y')
        })

    return render_template('reports.html',
        active_page='reports',
        month_str=month_str,
        month_label=datetime.strptime(month_str, '%Y-%m').strftime('%B %Y'),
        month_options=month_options,
        contrib_summary=contrib_summary,
        disbursed_summary=disbursed_summary,
        repayment_summary=repayment_summary,
        interest_earned=interest_earned,
        fees_collected=fees_collected,
        net_movement=net_movement,
        contributions=contributions,
        loans_disbursed=loans_disbursed,
        repayments=repayments
    )


# ── CSV Download endpoints ──

@reports_bp.route('/reports/download/contributions')
@login_required
def download_contributions():
    db = get_db()
    month_str = request.args.get('month', date.today().strftime('%Y-%m'))
    first_day, last_day = get_month_range(month_str)
    month_label = datetime.strptime(month_str, '%Y-%m').strftime('%B_%Y')

    rows = db.execute("""
        SELECT
            m.full_name as member_name,
            c.amount,
            c.payment_method,
            c.reference,
            c.contribution_date,
            c.notes
        FROM contributions c
        JOIN members m ON c.member_id = m.id
        WHERE c.contribution_date >= %s AND c.contribution_date < %s
        ORDER BY c.contribution_date DESC
    """, first_day, last_day)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Member Name', 'Amount (₦)', 'Payment Method', 'Reference', 'Date', 'Notes'])
    for row in rows:
        writer.writerow([
            row['member_name'],
            row['amount'],
            row['payment_method'] or '',
            row['reference'] or '',
            str(row['contribution_date']),
            row['notes'] or ''
        ])

    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename=contributions_{month_label}.csv"}
    )


@reports_bp.route('/reports/download/loans')
@login_required
def download_loans():
    db = get_db()
    month_str = request.args.get('month', date.today().strftime('%Y-%m'))
    first_day, last_day = get_month_range(month_str)
    month_label = datetime.strptime(month_str, '%Y-%m').strftime('%B_%Y')

    rows = db.execute("""
        SELECT
            b.full_name as borrower_name,
            l.principal,
            l.interest_rate,
            l.interest_amount,
            l.total_repayable,
            l.balance_remaining,
            l.loan_start_date,
            l.due_date,
            l.status
        FROM loans l
        JOIN borrowers b ON l.borrower_id = b.id
        WHERE l.loan_start_date >= %s AND l.loan_start_date < %s
        ORDER BY l.loan_start_date DESC
    """, first_day, last_day)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Borrower', 'Principal (₦)', 'Interest Rate (%)',
        'Interest (₦)', 'Total Repayable (₦)', 'Balance (₦)',
        'Start Date', 'Due Date', 'Status'
    ])
    for row in rows:
        writer.writerow([
            row['borrower_name'],
            row['principal'],
            row['interest_rate'],
            row['interest_amount'],
            row['total_repayable'],
            row['balance_remaining'],
            str(row['loan_start_date']),
            str(row['due_date']),
            row['status']
        ])

    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename=loans_{month_label}.csv"}
    )


@reports_bp.route('/reports/download/repayments')
@login_required
def download_repayments():
    db = get_db()
    month_str = request.args.get('month', date.today().strftime('%Y-%m'))
    first_day, last_day = get_month_range(month_str)
    month_label = datetime.strptime(month_str, '%Y-%m').strftime('%B_%Y')

    rows = db.execute("""
        SELECT
            b.full_name as borrower_name,
            t.amount,
            t.created_at,
            l.balance_remaining,
            l.status
        FROM transactions t
        JOIN loans l ON t.reference_id = l.id
        JOIN borrowers b ON l.borrower_id = b.id
        WHERE t.transaction_type = 'repayment'
        AND t.reference_table = 'loans'
        AND t.created_at >= %s AND t.created_at < %s
        ORDER BY t.created_at DESC
    """, first_day, last_day)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Borrower', 'Amount Paid (₦)', 'Date', 'Remaining Balance (₦)', 'Loan Status'])
    for row in rows:
        writer.writerow([
            row['borrower_name'],
            row['amount'],
            str(row['created_at']),
            row['balance_remaining'],
            row['status']
        ])

    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename=repayments_{month_label}.csv"}
    )
