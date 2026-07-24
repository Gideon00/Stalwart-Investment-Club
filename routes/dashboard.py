from datetime import date
from flask import Blueprint, render_template, session, redirect, url_for
from helpers import get_db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def view_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    db = get_db()

    # Total capital
    res_capital = db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM contributions")
    total_capital = res_capital[0]['total']

    # Active loans
    res_loans = db.execute("""
        SELECT
            COUNT(*) as count,
            COALESCE(SUM(principal), 0) as total_disbursed,
            COALESCE(AVG(interest_rate), 0) as avg_rate
        FROM loans WHERE status = 'active'
    """)
    loan_stats = res_loans[0]

    # Profit — all time
    res_profit = db.execute("""
        SELECT COALESCE(SUM(interest_amount), 0) as total
        FROM loans WHERE status IN ('active', 'completed')
    """)
    profit = res_profit[0]['total']

    # Profit this week — PostgreSQL interval syntax
    res_profit_week = db.execute("""
        SELECT COALESCE(SUM(interest_amount), 0) as total
        FROM loans
        WHERE status IN ('active', 'completed')
        AND created_at >= CURRENT_DATE - INTERVAL '7 days'
    """)
    profit_week = res_profit_week[0]['total']

    # Available cash
    res_available = db.execute("""
        SELECT
            -- Cash Inflows
            (SELECT COALESCE(SUM(amount), 0) FROM contributions) +
            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE transaction_type = 'repayment') -
            
            -- Cash Outflows (Loan Disbursements)
            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE transaction_type = 'loan_disbursement') -
            
            -- Cash Outflows (Non-refunded fee expenses borne by the group/organization)
            (SELECT COALESCE(SUM(amount), 0) FROM fees WHERE is_refunded = TRUE)
            
        AS available;
    """)
    available_cash = res_available[0]['available']

    # Liquidity %
    liquidity_pct = min(round((available_cash / total_capital * 100) if total_capital > 0 else 0), 100)

    # Overdue loans — PostgreSQL CURRENT_DATE
    res_overdue = db.execute("""
        SELECT COUNT(*) as count FROM loans
        WHERE status = 'active' AND due_date < CURRENT_DATE
    """)
    overdue_count = res_overdue[0]['count']

    # Recent activity
    recent_activity = db.execute("""
        SELECT
            t.transaction_type,
            t.amount,
            t.description,
            t.created_at,
            m.full_name as actor_name
        FROM transactions t
        LEFT JOIN members m ON t.created_by = m.id
        ORDER BY t.created_at DESC
        LIMIT 5
    """)

    # Format created_at — PostgreSQL returns a datetime object not a string
    formatted_activity = []
    for row in recent_activity:
        row = dict(row)
        if row['created_at']:
            # PostgreSQL returns datetime objects directly — no strptime needed
            row['created_at'] = row['created_at'].strftime('%d-%m-%Y')
        formatted_activity.append(row)

    # Member count
    res_members = db.execute("SELECT COUNT(*) as count FROM members WHERE status = 'active'")
    member_count = res_members[0]['count']

    return render_template('dashboard.html',
        total_capital=total_capital,
        loan_stats=loan_stats,
        profit=profit,
        profit_week=profit_week,
        available_cash=available_cash,
        liquidity_pct=liquidity_pct,
        overdue_count=overdue_count,
        recent_activity=formatted_activity,
        member_count=member_count,
        today=date.today().strftime('%B %d, %Y'),
        active_page='dashboard'
    )
