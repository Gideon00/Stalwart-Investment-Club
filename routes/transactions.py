from flask import Blueprint, render_template
from helpers import get_db, login_required

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/transactions')
@login_required
def list_transactions():
    db = get_db()

    # Monthly stats — PostgreSQL date truncation
    res_stats = db.execute("""
        SELECT
            COALESCE(SUM(amount), 0) as total_volume,
            COUNT(*) as total_count
        FROM transactions
        WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
    """)
    stats = res_stats[0]

    # Monthly contribution stats
    res_contrib = db.execute("""
        SELECT
            COALESCE(SUM(amount), 0) as contribution_total,
            COUNT(*) as contribution_count
        FROM transactions
        WHERE transaction_type = 'contribution'
        AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
    """)
    contrib_stats = res_contrib[0]

    # Full transaction history
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

    # PostgreSQL returns datetime objects — format directly
    for txn in transactions:
        if txn['created_at']:
            if isinstance(txn['created_at'], str):
                from datetime import datetime
                txn['created_at'] = datetime.strptime(
                    txn['created_at'].split('.')[0], '%Y-%m-%d %H:%M:%S'
                ).strftime('%d-%m-%Y %H:%M')
            else:
                txn['created_at'] = txn['created_at'].strftime('%d-%m-%Y %H:%M')

    return render_template('transactions.html',
        transactions=transactions,
        stats=stats,
        contrib_stats=contrib_stats,
        active_page='transactions'
    )
