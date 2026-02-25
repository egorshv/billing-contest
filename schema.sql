CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount > 0),
  payment_status VARCHAR(20) NOT NULL,
  created_at DATETIME NOT NULL
);

CREATE TABLE payments (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  payment_type VARCHAR(20) NOT NULL,
  amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
  refunded_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (refunded_amount >= 0 AND refunded_amount <= amount),
  status VARCHAR(32) NOT NULL,
  external_payment_id VARCHAR(128) UNIQUE,
  paid_at DATETIME,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE INDEX ix_payments_order_id ON payments(order_id);

CREATE TABLE bank_payment_states (
  id INTEGER PRIMARY KEY,
  payment_id INTEGER NOT NULL UNIQUE REFERENCES payments(id) ON DELETE CASCADE,
  bank_payment_id VARCHAR(128) NOT NULL UNIQUE,
  bank_amount NUMERIC(12, 2),
  bank_status VARCHAR(20) NOT NULL,
  bank_paid_at DATETIME,
  last_checked_at DATETIME,
  last_error TEXT
);

CREATE INDEX ix_bank_payment_states_bank_payment_id ON bank_payment_states(bank_payment_id);
