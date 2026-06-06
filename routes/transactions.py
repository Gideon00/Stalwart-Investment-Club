from flask import Blueprint, render_template
from helpers import get_db, login_required

transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/transactions')
@login_required
def list_transactions():
    # Get the CS50 SQL execution object
    db = get_db()

    # Monthly General Stats
    # CS50 returns a list of dicts; append [0] to extract the single aggregate row
    res_stats = db.execute("""
        SELECT
            COALESCE(SUM(amount), 0) as total_volume,
            COUNT(*) as total_count
        FROM transactions
        WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    """)
    stats = res_stats[0]

    # Monthly Contribution Stats
    res_contrib = db.execute("""
        SELECT
            COALESCE(SUM(amount), 0) as contribution_total,
            COUNT(*) as contribution_count
        FROM transactions
        WHERE transaction_type = 'contribution'
        AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    """)
    contrib_stats = res_contrib[0]

    # Full Transaction History List
    # CS50 automatically retrieves all matching rows into a ready-to-use list of dicts
    transactions = db.execute("""
        SELECT
            t.id,
            t.transaction_type,
            t.amount,
            t.description,
            t.reference_id,
            t.reference_table,
            t.created_at,
            m.full_name as created_by_name,
            m.username as created_by_username
        FROM transactions t
        LEFT JOIN members m ON t.created_by = m.id
        ORDER BY t.created_at DESC
    """)

    return render_template('transactions.html',
        transactions=transactions,
        stats=stats,
        contrib_stats=contrib_stats,
        active_page='transactions'
    )
