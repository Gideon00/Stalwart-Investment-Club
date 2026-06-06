from datetime import date, datetime
from flask import Blueprint, render_template, session, redirect, url_for

from helpers import get_db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def view_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    # Get the CS50 SQL execution object
    db = get_db()

    # Total capital — sum of all contributions ever made
    # CS50 returns a list of dicts, so we append [0] to grab the first row
    res_capital = db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM contributions")
    total_capital = res_capital[0]['total']

    # Active loans — count and total principal outstanding
    res_loans = db.execute("""
        SELECT
            COUNT(*) as count,
            COALESCE(SUM(principal), 0) as total_disbursed,
            COALESCE(AVG(interest_rate), 0) as avg_rate
        FROM loans WHERE status = 'active'
    """)
    # Pass the dictionary directly to the template
    loan_stats = res_loans[0]

    # Profit — interest collected on active + completed loans
    res_profit = db.execute("""
        SELECT COALESCE(SUM(interest_amount), 0) as total
        FROM loans WHERE status IN ('active', 'completed')
    """)
    profit = res_profit[0]['total']

    # Profit this week (Assuming SQLite syntax based on your date string)
    res_profit_week = db.execute("""
        SELECT COALESCE(SUM(interest_amount), 0) as total
        FROM loans
        WHERE status IN ('active', 'completed')
        AND created_at >= date('now', '-7 days')
    """)
    profit_week = res_profit_week[0]['total']

    # Available cash — contributions minus active loan disbursements
    res_available = db.execute("""
        SELECT
            (SELECT COALESCE(SUM(amount), 0) FROM contributions) -
            (SELECT COALESCE(SUM(principal), 0) FROM loans WHERE status = 'active')
            as available
    """)
    available_cash = res_available[0]['available']

    # Liquidity % — available / total capital
    liquidity_pct = min(round((available_cash / total_capital * 100) if total_capital > 0 else 0), 100)
    
    # Overdue loans count
    res_overdue = db.execute("""
        SELECT COUNT(*) as count FROM loans
        WHERE status = 'active' AND due_date < date('now')
    """)
    overdue_count = res_overdue[0]['count']

    # Recent activity — last 5 transactions with member name
    # CS50 already returns mutable python dictionaries inside a list!
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
    
    # Convert date format for display
    for row in recent_activity:
        if row['created_at']:
            # No need to explicitly call dict(m) anymore
            row['created_at'] = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d-%m-%Y')

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
        recent_activity=recent_activity, # Passing the updated list directly
        member_count=member_count,
        today=date.today().strftime('%B %d, %Y'),
        active_page='dashboard'
    )
