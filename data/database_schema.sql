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
    date DATE NOT NULL,
    market_cap FLOAT,
    ev_ebitda FLOAT,
    pe_ratio FLOAT,
    peg_ratio FLOAT,
    croci FLOAT,
    revenue_cagr FLOAT,
    dividend_growth_rate FLOAT,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, date)
);

-- 3. Price Data Table
CREATE TABLE IF NOT EXISTS price_data (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    date DATE NOT NULL,
    open_price FLOAT,
    high_price FLOAT,
    low_price FLOAT,
    close_price FLOAT,
    adjusted_close FLOAT,
    volume INTEGER,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, date)
);

-- 4. Technical Indicators Table
CREATE TABLE IF NOT EXISTS technical_indicators (
    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    date DATE NOT NULL,
    atr FLOAT,
    moving_average_50 FLOAT,
    moving_average_200 FLOAT,
    macd FLOAT,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, date)
);

-- 5. Risk Metrics Table
CREATE TABLE IF NOT EXISTS risk_metrics (
    risk_metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    date DATE NOT NULL,
    fama_french_alpha FLOAT,
    sortino_ratio FLOAT,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, date)
);

-- 6. Scoring System Table
CREATE TABLE IF NOT EXISTS scoring_system (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    date DATE NOT NULL,
    fundamental_score FLOAT,
    technical_score FLOAT,
    risk_adjusted_score FLOAT,
    overall_score FLOAT,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, date)
);

-- 7. Portfolio Allocation Table
CREATE TABLE IF NOT EXISTS portfolio_allocation (
    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    allocation_date DATE NOT NULL,
    allocation_weight FLOAT,
    method VARCHAR,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, allocation_date, method)
);

-- 8. Price Prediction Results Table
CREATE TABLE IF NOT EXISTS price_prediction_results (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    forecast_date DATE NOT NULL,
    model_type VARCHAR,
    predicted_price FLOAT,
    confidence_interval_upper FLOAT,
    confidence_interval_lower FLOAT,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, forecast_date, model_type)
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
    date_fetched DATE NOT NULL,
    api_name VARCHAR,
    response JSON,
    http_status_code INTEGER,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, date, api_name)
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_fundamental_data_fiscalDateEnding ON fundamental_data(stock_id,fiscalDateEnding);
CREATE INDEX IF NOT EXISTS idx_extracted_fundamental_data_fiscalDateEnding ON extracted_fundamental_data(stock_id, fiscalDateEnding);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_api_responses_date_fetched ON raw_api_responses(stock_id, date_fetched);