-- 1. Stocks (Master Table)
CREATE TABLE IF NOT EXISTS stocks (
    stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    industry TEXT,
    sector TEXT,
    country TEXT
);

-- 2. Fundamental Data Table
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

-- 9. Risk Management Table
CREATE TABLE IF NOT EXISTS risk_management (
    risk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    strategy_date DATE NOT NULL,
    stop_loss_level FLOAT,
    take_profit_level FLOAT,
    atr FLOAT,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, strategy_date)
);

-- 10. Portfolio Performance & Backtesting Table
CREATE TABLE IF NOT EXISTS portfolio_performance (
    performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_date DATE NOT NULL,
    portfolio_return FLOAT,
    portfolio_volatility FLOAT,
    sharpe_ratio FLOAT,
    sortino_ratio FLOAT,
    benchmark_return FLOAT,
    benchmark VARCHAR,
    UNIQUE(portfolio_date, benchmark)
);

-- 11. Log Table
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR,
    timestamp TIMESTAMP NOT NULL,
    module VARCHAR,
    log_level VARCHAR,
    message TEXT
);

-- 12. Raw API Responses Table
CREATE TABLE IF NOT EXISTS raw_api_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    date DATE NOT NULL,
    api_name VARCHAR,
    response JSON,
    http_status_code INTEGER,
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    UNIQUE(stock_id, date, api_name)
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_fundamental_data_stock_date ON fundamental_data(stock_id, date);
CREATE INDEX IF NOT EXISTS idx_price_data_stock_date ON price_data(stock_id, date);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_stock_date ON technical_indicators(stock_id, date);
CREATE INDEX IF NOT EXISTS idx_risk_metrics_stock_date ON risk_metrics(stock_id, date);
CREATE INDEX IF NOT EXISTS idx_scoring_system_stock_date ON scoring_system(stock_id, date);
CREATE INDEX IF NOT EXISTS idx_portfolio_allocation_stock_date ON portfolio_allocation(stock_id, allocation_date);
CREATE INDEX IF NOT EXISTS idx_price_prediction_stock_date ON price_prediction_results(stock_id, forecast_date);
CREATE INDEX IF NOT EXISTS idx_risk_management_stock_date ON risk_management(stock_id, strategy_date);
