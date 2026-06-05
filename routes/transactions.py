from flask import Blueprint, render_template
from helpers import get_db, login_required

transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/transactions')
@login_required
def list_transactions():
    with get_db() as conn:
        
        db = conn.cursor()

        db.execute("""
            SELECT
                COALESCE(SUM(amount), 0) as total_volume,
                COUNT(*) as total_count
            FROM transactions
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        """)
        stats = db.fetchone()

        db.execute("""
            SELECT
                COALESCE(SUM(amount), 0) as contribution_total,
                COUNT(*) as contribution_count
            FROM transactions
            WHERE transaction_type = 'contribution'
            AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        """)
        contrib_stats = db.fetchone()

        db.execute("""
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
        transactions = db.fetchall()

    return render_template('transactions.html',
        transactions=transactions,
        stats=stats,
        contrib_stats=contrib_stats,
        active_page='transactions'
    )
