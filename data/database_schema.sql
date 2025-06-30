-- 1. Stocks (Master Table)
CREATE TABLE IF NOT EXISTS stocks (
    stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    description TEXT, 
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
    fiscalDateEnding DATE NOT NULL,  -- Most recent quarterly report date
    market_cap FLOAT,
    
    -- Balance Sheet items (point-in-time from most recent quarter)
    total_debt FLOAT,  -- Total liabilities from most recent quarter
    cash_equiv FLOAT,  -- Cash and cash equivalents from most recent quarter
    total_assets FLOAT,  -- Total assets from most recent quarter
    working_capital FLOAT,  -- Current assets minus current liabilities
    longTermInvestments FLOAT,  -- Long-term investments from most recent quarter
    
    -- TTM (Trailing Twelve Months) Flow Metrics - sum of last 4 quarters
    ebitda_ttm FLOAT,  -- TTM EBITDA (sum of last 4 quarters)
    revenue_ttm FLOAT,  -- TTM revenue (sum of last 4 quarters)
    cash_flow_ops_ttm FLOAT,  -- TTM operating cash flow
    interest_expense_ttm FLOAT,  -- TTM interest expense
    
    -- Quarterly Metrics - most recent quarter only
    cash_flow_ops_q FLOAT,  -- Most recent quarter operating cash flow
    interest_expense_q FLOAT,  -- Most recent quarter interest expense
    change_in_working_capital FLOAT,  -- Quarter-over-quarter change in working capital
    
    -- Annual Fallback Metrics - used if TTM calculation fails
    ebitda_annual FLOAT,  -- Most recent annual EBITDA (fallback)
    total_debt_annual FLOAT,  -- Most recent annual total debt (fallback)
    
    -- Legacy columns for backward compatibility (will store TTM or fallback values)
    ebitda FLOAT,  -- Stores ebitda_ttm or ebitda_annual
    cash_flow_ops FLOAT,  -- Stores cash_flow_ops_ttm or cash_flow_ops_q
    interest_expense FLOAT,  -- Stores interest_expense_ttm or interest_expense_q
    
    -- Other metrics
    effective_tax_rate FLOAT,  -- Calculated from most recent quarter
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