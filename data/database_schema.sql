-- 1. Stocks (Master Table)
CREATE TABLE IF NOT EXISTS stocks (
    stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    industry TEXT,
    sector TEXT,
    country TEXT
);

-- 2. Fundamental Data Tables
CREATE TABLE IF NOT EXISTS fundamental_data (
    fundamental_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    fiscalDateEnding DATE NOT NULL,
    calculated_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    market_cap FLOAT,
    ev_ebitda FLOAT,
    pe_ratio FLOAT,
    peg_ratio FLOAT,
    croci FLOAT,
    revenue_cagr FLOAT,
    dividend_growth_rate FLOAT,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, fiscalDateEnding)
);

CREATE TABLE IF NOT EXISTS extracted_fundamental_data (
    extracted_fundamental_data_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    fiscalDateEnding DATE NOT NULL,
    market_cap FLOAT,
    total_debt FLOAT,
    cash_equiv FLOAT,
    ebitda FLOAT,
    cash_flow_ops FLOAT,
    change_in_working_capital FLOAT,
    interest_expense FLOAT,
    total_assets FLOAT,
    working_capital FLOAT,
    effective_tax_rate FLOAT,
    longTermInvestments FLOAT,
    data_source VARCHAR,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, fiscalDateEnding, data_source)
); 

CREATE TABLE IF NOT EXISTS eps_last_5_qs (
    eps_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    fiscalDateEnding DATE NOT NULL,
    reportedEPS FLOAT,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, fiscalDateEnding)
);

-- 3. Price Data Table

-- 4. all other tables still to do...

-- Logging table
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR,
    timestamp TIMESTAMP NOT NULL,
    module VARCHAR,
    log_level VARCHAR,
    message TEXT
);

-- Raw API Responses Table
CREATE TABLE IF NOT EXISTS raw_api_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    ticker VARCHAR NOT NULL,
    date_fetched DATE NOT NULL,
    endpoint_key VARCHAR,
    response JSON,
    http_status_code INTEGER,
    is_complete_session BOOLEAN DEFAULT FALSE,  -- TRUE if all 4 endpoints succeeded for this date/ticker
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, date_fetched, endpoint_key)
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_fundamental_data_fiscalDateEnding ON fundamental_data(stock_id, fiscalDateEnding);
CREATE INDEX IF NOT EXISTS idx_extracted_fundamental_data_fiscalDateEnding ON extracted_fundamental_data(stock_id, fiscalDateEnding);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_api_responses_date_fetched ON raw_api_responses(stock_id, date_fetched);