-- =====================================================
-- MINI LOAN + INVESTMENT SYSTEM (SQLite Schema)
-- Clean CS50-style structure
-- =====================================================

PRAGMA foreign_keys = ON;

-- =====================================================
-- MEMBERS TABLE (Investors / Contributors)
-- =====================================================

CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    phone TEXT,
    email TEXT,
    address TEXT,
    date_joined DATE DEFAULT CURRENT_DATE,
    contributions REAL NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'staff', -- admin / staff
    status TEXT NOT NULL DEFAULT 'active' -- active / inactive
);


-- =====================================================
-- CONTRIBUTIONS TABLE
-- Tracks money members contribute into the fund pool
-- =====================================================

CREATE TABLE contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    contribution_date DATE NOT NULL DEFAULT CURRENT_DATE,
    payment_method TEXT, -- cash / transfer / POS
    reference TEXT,
    notes TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (created_by) REFERENCES members(id)
);


-- =====================================================
-- BORROWERS TABLE
-- People collecting loans (not necessarily members)
-- =====================================================

CREATE TABLE borrowers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    occupation TEXT,
    total_loan INTEGER NOT NULL DEFAULT 0,
    guarantor_name TEXT,
    guarantor_phone TEXT,
    date_registered DATE DEFAULT CURRENT_DATE
);


-- =====================================================
-- LOANS TABLE
-- Main loan agreement record
-- =====================================================

CREATE TABLE loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    borrower_id INTEGER NOT NULL,

    principal REAL NOT NULL CHECK(principal > 0),
    interest_rate REAL NOT NULL CHECK(interest_rate >= 0),
    interest_amount REAL NOT NULL DEFAULT 0,

    total_repayable REAL NOT NULL DEFAULT 0,
    amount_paid REAL NOT NULL DEFAULT 0,
    balance_remaining REAL NOT NULL DEFAULT 0,

    loan_start_date DATE NOT NULL,
    due_date DATE NOT NULL,

    status TEXT NOT NULL DEFAULT 'active',
    -- active / completed / defaulted / overdue

    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (borrower_id) REFERENCES borrowers(id),
    FOREIGN KEY (created_by) REFERENCES members(id)
);


-- =====================================================
-- FEES TABLE
-- Stamp duty, transfer fees, bank charges, etc.
-- =====================================================

CREATE TABLE fees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL,

    fee_type TEXT NOT NULL,
    -- stamp duty / transfer fee / bank charge / processing fee

    amount REAL NOT NULL CHECK(amount >= 0),

    payer_type TEXT NOT NULL,
    -- member / borrower / admin

    payer_id INTEGER,
    is_refunded INTEGER NOT NULL DEFAULT 0,
    -- 0 = False, 1 = True

    refund_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (loan_id) REFERENCES loans(id)
);


-- =====================================================
-- TRANSACTIONS TABLE
-- Master financial history table
-- EVERYTHING enters here
-- =====================================================

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    transaction_type TEXT NOT NULL,
    -- contribution / loan_disbursement / repayment
    -- refund / withdrawal / expense / bank_charge

    amount REAL NOT NULL CHECK(amount > 0),

    description TEXT,

    reference_id INTEGER,
    reference_table TEXT,
    -- loans / fees / contributions / withdrawals

    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (created_by) REFERENCES members(id)
);


-- =====================================================
-- AUDIT LOG TABLE
-- Tracks edits/deletes for accountability
-- =====================================================

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    member_id INTEGER,
    action TEXT NOT NULL,
    -- create / update / delete / refund

    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,

    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (member_id) REFERENCES members(id)
);
