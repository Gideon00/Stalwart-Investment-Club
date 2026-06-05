from datetime import date, datetime
from flask import Blueprint, render_template, session, redirect, url_for

from helpers import get_db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def view_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    with get_db() as conn:
        db = conn.cursor()

        # Total capital — sum of all contributions ever made
        db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM contributions")
        total_capital = db.fetchone()['total']

        # Active loans — count and total principal outstanding
        db.execute("""
            SELECT
                COUNT(*) as count,
                COALESCE(SUM(principal), 0) as total_disbursed,
                COALESCE(AVG(interest_rate), 0) as avg_rate
            FROM loans WHERE status = 'active'
        """)
        loan_stats = db.fetchone()

        # Profit — interest collected on active + completed loans
        db.execute("""
            SELECT COALESCE(SUM(interest_amount), 0) as total
            FROM loans WHERE status IN ('active', 'completed')
        """)
        profit = db.fetchone()['total']

        # Profit this week
        db.execute("""
            SELECT COALESCE(SUM(interest_amount), 0) as total
            FROM loans
            WHERE status IN ('active', 'completed')
            AND created_at >= date('now', '-7 days')
        """)
        profit_week = db.fetchone()['total']

        # Available cash — contributions minus active loan disbursements
        db.execute("""
            SELECT
                (SELECT COALESCE(SUM(amount), 0) FROM contributions) -
                (SELECT COALESCE(SUM(principal), 0) FROM loans WHERE status = 'active')
                as available
        """)
        available_cash = db.fetchone()['available']

        # Liquidity % — available / total capital
        # liquidity_pct = round((available_cash / total_capital * 100) if total_capital > 0 else 0)
        liquidity_pct = min(round((available_cash / total_capital * 100) if total_capital > 0 else 0), 100)
        # Overdue loans count
        db.execute("""
            SELECT COUNT(*) as count FROM loans
            WHERE status = 'active' AND due_date < date('now')
        """)
        overdue_count = db.fetchone()['count']

        # Recent activity — last 5 transactions with member name
        db.execute("""
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
        recent_activity = db.fetchall()
        
        # Convert date format for display
        recent_activity_list = []
        for m in recent_activity:
            m = dict(m)  # convert Row object to regular dict so it's mutable
            if m['created_at']:
                m['created_at'] = datetime.strptime(m['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d-%m-%Y')
            recent_activity_list.append(m)

        # Member count
        db.execute("SELECT COUNT(*) as count FROM members WHERE status = 'active'")
        member_count = db.fetchone()['count']

    return render_template('dashboard.html',
        total_capital=total_capital,
        loan_stats=loan_stats,
        profit=profit,
        profit_week=profit_week,
        available_cash=available_cash,
        liquidity_pct=liquidity_pct,
        overdue_count=overdue_count,
        recent_activity=recent_activity_list,
        member_count=member_count,
        today=date.today().strftime('%B %d, %Y'),
        active_page='dashboard'
    )
