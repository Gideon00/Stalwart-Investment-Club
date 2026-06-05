-- =====================================================
-- MINI LOAN + INVESTMENT SYSTEM (PostgreSQL Schema)
-- =====================================================

-- Note: PostgreSQL enables Foreign Key checks by default. 
-- No PRAGMA statements are required.

-- =====================================================
-- MEMBERS TABLE (Investors / Contributors)
-- =====================================================

CREATE TABLE members (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(50),
    email VARCHAR(255),
    address TEXT,
    profile_photo TEXT,
    date_joined DATE DEFAULT CURRENT_DATE,
    contributions NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    role VARCHAR(50) NOT NULL DEFAULT 'staff', -- admin / staff
    status VARCHAR(50) NOT NULL DEFAULT 'active' -- active / inactive
);


-- =====================================================
-- CONTRIBUTIONS TABLE
-- Tracks money members contribute into the fund pool
-- =====================================================

CREATE TABLE contributions (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL,
    amount NUMERIC(15, 2) NOT NULL CHECK(amount > 0),
    contribution_date DATE NOT NULL DEFAULT CURRENT_DATE,
    payment_method VARCHAR(50), -- cash / transfer / POS
    reference VARCHAR(100),
    notes TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fk_contributions_member FOREIGN KEY (member_id) REFERENCES members(id),
    CONSTRAINT fk_contributions_creator FOREIGN KEY (created_by) REFERENCES members(id)
);


-- =====================================================
-- BORROWERS TABLE
-- People collecting loans (not necessarily members)
-- =====================================================

CREATE TABLE borrowers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    address TEXT,
    occupation VARCHAR(100),
    total_loan NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    guarantor_name VARCHAR(255),
    guarantor_phone VARCHAR(50),
    date_registered DATE DEFAULT CURRENT_DATE
);


-- =====================================================
-- LOANS TABLE
-- Main loan agreement record
-- =====================================================

CREATE TABLE loans (
    id SERIAL PRIMARY KEY,
    borrower_id INTEGER NOT NULL,

    principal NUMERIC(15, 2) NOT NULL CHECK(principal > 0),
    interest_rate NUMERIC(5, 2) NOT NULL CHECK(interest_rate >= 0),
    interest_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,

    total_repayable NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    amount_paid NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    balance_remaining NUMERIC(15, 2) NOT NULL DEFAULT 0.00,

    loan_start_date DATE NOT NULL,
    due_date DATE NOT NULL,

    status VARCHAR(50) NOT NULL DEFAULT 'active',
    -- active / completed / defaulted / overdue

    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fk_loans_borrower FOREIGN KEY (borrower_id) REFERENCES borrowers(id),
    CONSTRAINT fk_loans_creator FOREIGN KEY (created_by) REFERENCES members(id)
);


-- =====================================================
-- FEES TABLE
-- Stamp duty, transfer fees, bank charges, etc.
-- =====================================================

CREATE TABLE fees (
    id SERIAL PRIMARY KEY,
    loan_id INTEGER NOT NULL,

    fee_type VARCHAR(100) NOT NULL,
    -- stamp duty / transfer fee / bank charge / processing fee

    amount NUMERIC(15, 2) NOT NULL CHECK(amount >= 0),

    payer_type VARCHAR(50) NOT NULL,
    -- member / borrower / admin

    payer_id INTEGER,
    is_refunded BOOLEAN NOT NULL DEFAULT FALSE, -- Converted from integer to native BOOLEAN
    
    refund_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fk_fees_loan FOREIGN KEY (loan_id) REFERENCES loans(id)
);


-- =====================================================
-- TRANSACTIONS TABLE
-- Master financial history table
-- =====================================================

CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,

    transaction_type VARCHAR(100) NOT NULL,
    -- contribution / loan_disbursement / repayment
    -- refund / withdrawal / expense / bank_charge

    amount NUMERIC(15, 2) NOT NULL CHECK(amount > 0),

    description TEXT,

    reference_id INTEGER,
    reference_table VARCHAR(100),
    -- loans / fees / contributions / withdrawals

    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fk_transactions_creator FOREIGN KEY (created_by) REFERENCES members(id)
);


-- =====================================================
-- AUDIT LOG TABLE
-- Tracks edits/deletes for accountability
-- =====================================================

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,

    member_id INTEGER,
    action VARCHAR(100) NOT NULL,
    -- create / update / delete / refund

    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER NOT NULL,

    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fk_audit_member FOREIGN KEY (member_id) REFERENCES members(id)
);
