-- Add user_payment table for tracking payment status

CREATE TABLE IF NOT EXISTS user_payment (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    amount_due FLOAT NOT NULL,
    amount_paid FLOAT DEFAULT 0.0,
    is_paid BOOLEAN DEFAULT FALSE,
    paid_at TIMESTAMP,
    payment_reference VARCHAR(200),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES "order"(id) ON DELETE CASCADE,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE,
    CONSTRAINT unique_order_user_payment UNIQUE (order_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_payment_order ON user_payment(order_id);
CREATE INDEX IF NOT EXISTS idx_payment_user ON user_payment(user_id);

