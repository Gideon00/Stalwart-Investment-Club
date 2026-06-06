# setup_db.py
from helpers import get_db

db = get_db()

# =====================================================
# MEMBERS TABLE
# =====================================================
db.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id SERIAL PRIMARY KEY,
        full_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        username TEXT NOT NULL UNIQUE,
        phone TEXT,
        email TEXT,
        address TEXT,
        profile_photo TEXT,
        date_joined DATE DEFAULT CURRENT_DATE,
        contributions REAL NOT NULL DEFAULT 0,
        role TEXT NOT NULL DEFAULT 'staff',
        status TEXT NOT NULL DEFAULT 'active'
    )
""")

# =====================================================
# CONTRIBUTIONS TABLE
# =====================================================
db.execute("""
    CREATE TABLE IF NOT EXISTS contributions (
        id SERIAL PRIMARY KEY,
        member_id INTEGER NOT NULL REFERENCES members(id),
        amount REAL NOT NULL CHECK(amount > 0),
        contribution_date DATE NOT NULL DEFAULT CURRENT_DATE,
        payment_method TEXT,
        reference TEXT,
        notes TEXT,
        created_by INTEGER REFERENCES members(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# =====================================================
# BORROWERS TABLE
# =====================================================
db.execute("""
    CREATE TABLE IF NOT EXISTS borrowers (
        id SERIAL PRIMARY KEY,
        full_name TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        occupation TEXT,
        total_loan INTEGER NOT NULL DEFAULT 0,
        guarantor_name TEXT,
        guarantor_phone TEXT,
        date_registered DATE DEFAULT CURRENT_DATE
    )
""")

# =====================================================
# LOANS TABLE
# =====================================================
db.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        id SERIAL PRIMARY KEY,
        borrower_id INTEGER NOT NULL REFERENCES borrowers(id),
        principal REAL NOT NULL CHECK(principal > 0),
        interest_rate REAL NOT NULL CHECK(interest_rate >= 0),
        interest_amount REAL NOT NULL DEFAULT 0,
        total_repayable REAL NOT NULL DEFAULT 0,
        amount_paid REAL NOT NULL DEFAULT 0,
        balance_remaining REAL NOT NULL DEFAULT 0,
        loan_start_date DATE NOT NULL,
        due_date DATE NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_by INTEGER REFERENCES members(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# =====================================================
# FEES TABLE
# =====================================================
db.execute("""
    CREATE TABLE IF NOT EXISTS fees (
        id SERIAL PRIMARY KEY,
        loan_id INTEGER NOT NULL REFERENCES loans(id),
        fee_type TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount >= 0),
        payer_type TEXT NOT NULL,
        payer_id INTEGER,
        is_refunded INTEGER NOT NULL DEFAULT 0,
        refund_date TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# =====================================================
# TRANSACTIONS TABLE
# =====================================================
db.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        transaction_type TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        description TEXT,
        reference_id INTEGER,
        reference_table TEXT,
        created_by INTEGER REFERENCES members(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# =====================================================
# AUDIT LOGS TABLE
# =====================================================
db.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        member_id INTEGER REFERENCES members(id),
        action TEXT NOT NULL,
        table_name TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

print("All tables created successfully.")
