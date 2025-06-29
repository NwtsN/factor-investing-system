# Investment Analysis System - Database Module

## 📋 **Overview**

The database module provides a complete, intelligent pipeline for fetching, validating, and storing financial data from the Alpha Vantage API. It implements smart caching to avoid unnecessary API calls, maintains data freshness tracking, provides robust error handling, and supports configurable transaction modes for database operations.

## 🏗️ **Architecture**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Alpha Vantage │───▶│   DataFetcher    │───▶│   DataManager   │
│       API       │    │   (Fetch & Parse)│    │   (Staging)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                          │
┌─────────────────┐    ┌──────────────────┐              │
│   SQLite DB     │◀───│   DataInserter   │◀─────────────┘
│   (Storage)     │    │   (Insert Data)  │
└─────────────────┘    └──────────────────┘
```

## 🔧 **Components**

### **1. DataFetcher** (`fetch_data.py`)
**Primary responsibility**: Fetch and parse financial data from Alpha Vantage API

**Key Features:**
- ✅ Intelligent rate limiting (12 seconds between calls, exponential backoff)
- ✅ Retry logic with 3 attempts per endpoint
- ✅ Data quality validation (minimum 10 valid fields)
- ✅ Supports batch operations or standalone use
- ✅ Extracts 17+ financial metrics from 4 API endpoints
- ✅ Session-based performance tracking
- ✅ HTTP connection pooling for efficiency

**API Endpoints Used:**
- `INCOME_STATEMENT` - Revenue, EBITDA, tax data
- `BALANCE_SHEET` - Assets, debt, cash, working capital
- `CASH_FLOW` - Operating cash flow, working capital changes
- `EARNINGS` - Last 5 quarters of EPS data

### **2. DataManager** (`database_handler.py`)
**Primary responsibility**: Manage data freshness and staging before insertion

**Key Features:**
- ✅ Intelligent freshness checking (avoids unnecessary API calls)
- ✅ Configurable refresh policies (90 days min, 365 days force)
- ✅ Quarterly report cycle awareness
- ✅ In-memory staging cache with automatic expiration (24 hours)
- ✅ Time-based cleanup every 5 minutes
- ✅ Force cleanup option for immediate expiration
- ✅ Cache status monitoring without side effects
- ✅ Session-based tracking with unique IDs

**Staging Cache Management:**
- Data automatically expires after 24 hours
- Cleanup runs every 5 minutes during normal operations
- Can force immediate cleanup with `force_cleanup_staging_data()`
- Check cache status with `get_staging_cache_status()`

### **3. DataInserter** (`data_inserter.py`)
**Primary responsibility**: Insert staged data into database tables

**Key Features:**
- ✅ Transactional integrity with configurable modes
- ✅ All-or-nothing transaction mode (default)
- ✅ Individual commit mode for partial success
- ✅ Automatic stock record creation
- ✅ Handles multiple data types (fundamentals, EPS, raw responses)
- ✅ Context manager support for automatic cleanup
- ✅ Connection reuse for better performance

**Transaction Modes:**
- **all-or-nothing** (default): Single transaction for all tickers, rollback on any failure
- **individual**: Each ticker committed separately, allowing partial success

### **4. DatabaseManager** (`database_setup.py`)
**Primary responsibility**: Initialize database schema and provide logger instances

**Key Features:**
- ✅ Automatic schema creation from SQL file
- ✅ Table existence validation
- ✅ Logger instance management
- ✅ Database connection handling
- ✅ Context manager support

## 🗄️ **Database Schema**

### **Core Tables**

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `stocks` | Master ticker registry | `stock_id`, `ticker`, `company_name` |
| `fundamental_data` | Calculated financial ratios and metrics | `stock_id`, `fiscalDateEnding`, `calculated_timestamp`, `market_cap`, `ev_ebitda`, `pe_ratio`, `croci` |
| `extracted_fundamental_data` | Raw financial data from API | `stock_id`, `fiscalDateEnding`, `total_debt`, `cash_equiv`, `total_assets`, `ebitda_ttm`, `revenue_ttm`, `cash_flow_ops_ttm`, plus fallbacks |
| `eps_last_5_qs` | Quarterly EPS history | `stock_id`, `fiscalDateEnding`, `reportedEPS` |
| `raw_api_responses` | Complete API responses | `stock_id`, `ticker`, `date_fetched`, `endpoint_key`, `response`, `http_status_code`, `is_complete_session` |
| `logs` | System logging | `session_id`, `timestamp`, `module`, `log_level`, `message` |

### **Relationships**
- All tables link to `stocks` via `stock_id` (foreign key)
- `raw_api_responses` also stores `ticker` directly for fast queries
- Unique constraints prevent duplicate data per ticker/date/endpoint

## 🚀 **Quick Start**

### **1. Basic Setup**
```python
from database.database_setup import DatabaseManager
from database.database_handler import DataManager
from database.fetch_data import DataFetcher
from database.data_inserter import DataInserter

# Initialize database with context manager
with DatabaseManager() as db_manager:
    logger = db_manager.get_logger("my_session_123")
    
    # Use the existing connection
    with DataManager(db_manager.conn, logger) as data_manager:
        # Your data operations here
        pass
```

### **2. Fetch Single Ticker (Standalone)**
```python
api_key = os.environ.get('ALPHA_VANTAGE_API_KEY', 'demo')

with DataFetcher(logger, api_key=api_key) as fetcher:
    success, fundamentals, raw_data = fetcher.fetch_fundamentals('AAPL')
    
    if success:
        print(f"AAPL Total Assets: ${fundamentals['total_assets']:,.0f}")
        print(f"AAPL Working Capital: ${fundamentals['working_capital']:,.0f}")
        print(f"AAPL EPS (last 5 quarters): {fundamentals['eps_last_5_qs']}")
    else:
        print("Failed to fetch AAPL data")
```

### **3. Batch Fetch with Intelligence (Recommended)**
```python
# Initialize components with existing connection
with DatabaseManager() as db_manager:
    logger = db_manager.get_logger("batch_session_456")
    
    with DataManager(db_manager.conn, logger) as data_manager:
        api_key = os.environ.get('ALPHA_VANTAGE_API_KEY', 'demo')
        
        with DataFetcher(logger, data_manager, api_key) as fetcher:
            # Define tickers to fetch
            tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']
            
            # Intelligent fetching (skips recent data)
            results = fetcher.fetch_multiple_tickers(tickers, force_refresh=False)
            
            print(f"Successful: {results['successful_fetches']}")
            print(f"Failed: {results['failed_fetches']}")
            print(f"Skipped (recent): {results['skipped_tickers']}")
            print(f"API calls made: {results['api_calls_made']}")
            
            # Insert fetched data with transaction mode
            staged_data = data_manager.get_staged_data()
            if staged_data:
                # Use existing connection for DataInserter
                with DataInserter(logger, connection=db_manager.conn) as inserter:
                    # Choose transaction mode
                    use_transaction = True  # or False for individual commits
                    insert_results = inserter.insert_staged_data(staged_data, use_transaction=use_transaction)
                    print(f"Inserted: {insert_results['successful_inserts']}")
                    
                    # Clear staging cache after successful insertion
                    for ticker in insert_results['successful_inserts']:
                        data_manager.clear_staged_data(ticker)
```

### **4. Integration with Timeout**
```python
from utils.program_timer import Timeout

# Set a 30-minute timeout for the entire operation
with Timeout(minutes=30):
    with DatabaseManager() as db_manager:
        # Your data fetching and insertion operations
        pass
```

## 📊 **Extracted Financial Metrics**

The system extracts 17 key financial metrics:

| Metric | Source | Description |
|--------|--------|-------------|
| `market_cap` | To be filled by price fetcher | Market capitalization |
| `total_debt` | Balance Sheet (Quarterly) | Total liabilities |
| `cash_equiv` | Balance Sheet (Quarterly) | Cash and cash equivalents |
| `total_assets` | Balance Sheet (Quarterly) | Total assets |
| `working_capital` | Calculated | Current assets - current liabilities |
| `longTermInvestments` | Balance Sheet (Quarterly) | Long-term investments |
| `ebitda_ttm` | Income Statement (4Q Rolling) | Trailing twelve months EBITDA |
| `revenue_ttm` | Income Statement (4Q Rolling) | Trailing twelve months revenue |
| `interest_expense_ttm` | Income Statement (4Q Rolling) | Trailing twelve months interest expense |
| `cash_flow_ops_ttm` | Cash Flow (4Q Rolling) | Trailing twelve months operating cash flow |
| `cash_flow_ops_q` | Cash Flow (Quarterly) | Most recent quarter operating cash flow |
| `change_in_working_capital` | Cash Flow (Quarterly) | Quarter-over-quarter working capital change |
| `interest_expense_q` | Income Statement (Quarterly) | Most recent quarter interest expense |
| `effective_tax_rate` | Calculated | Smart tax rate with fallbacks |
| `eps_last_5_qs` | Earnings endpoint | Last 5 quarters of reported EPS |
| `ebitda_annual` | Income Statement (Annual) | Annual EBITDA (fallback if quarterly unavailable) |
| `total_debt_annual` | Balance Sheet (Annual) | Annual total liabilities (fallback if quarterly unavailable) |

## ⚙️ **Configuration Options**

### **Rate Limiting**
```python
# DataFetcher rate limiting (modify in __init__)
self.min_interval_seconds = 12.0      # 5 calls per minute
self.max_backoff = 300.0               # 5 minutes max backoff
```

### **Data Freshness Policy**
```python
# DataManager refresh policy
data_manager.set_refresh_policy(
    min_days=90,    # Minimum days between fetches
    force_days=365  # Force refresh after this many days
)
```

### **Data Quality Thresholds**
```python
# DataFetcher quality validation (modify in __init__)
self.min_required_fields = 10  # Minimum non-null fields required (59% of 17 fields)
# Ensures core balance sheet, profitability, cash flow, and EPS data are present
```

### **Transaction Modes**
```python
# DataInserter transaction modes
inserter.insert_staged_data(staged_data, use_transaction=True)   # All-or-nothing
inserter.insert_staged_data(staged_data, use_transaction=False)  # Individual commits
```

## 🗂️ **Managing Staging Cache**

### **Monitor Cache Status**
```python
# Check cache status without triggering cleanup
status = data_manager.get_staging_cache_status()
print(f"Cache size: {status['size']} entries")
print(f"Oldest entry: {status['oldest_entry_age_hours']} hours old")
print(f"Next cleanup in: {status['next_cleanup_in_minutes']} minutes")
```

### **Manual Cache Management**
```python
# Force immediate cleanup of expired entries
removed = data_manager.force_cleanup_staging_data()
print(f"Removed {removed} expired entries")

# Clear specific ticker after successful insertion
data_manager.clear_staged_data('AAPL')

# Clear all staged data
data_manager.clear_staged_data()
```

### **Automatic Cleanup Behavior**
- Expired data (>24 hours old) is automatically cleaned every 5 minutes
- Cleanup runs when calling `stage_data()` or `get_staged_data()`
- Empty cache doesn't trigger cleanup timer reset

## 🔍 **Data Quality & Validation**

### **Automatic Quality Checks**
- ✅ Minimum 10 non-null fundamental fields (59% of total)
- ✅ Positive total assets validation
- ✅ At least 1 quarter of EPS data required
- ✅ API response structure validation
- ✅ Effective tax rate calculation with sensible fallbacks

### **Smart Tax Rate Calculation**
```python
# Handles edge cases in corporate tax data:
if company_profit > 0:
    if taxes_paid >= 0:
        use_actual_rate()
    else:  # Tax refund case
        use_21_percent_default()
else:  # Company lost money
    if still_paid_taxes:
        use_0_percent()  # Losses shouldn't be taxed
    else:
        use_21_percent_default()
```

## 🛠️ **Error Handling**

### **API Errors**
- **401/403**: Invalid API key - no retry
- **429**: Rate limit - exponential backoff (up to 5 minutes)
- **500+**: Server error - retry with backoff
- **Timeout**: 15-second timeout with retries

### **Database Errors**
- **Transaction rollback** on insertion failures
- **Connection validation** before operations
- **Comprehensive logging** of all errors

### **Data Errors**
- **Failed tickers tracking** for reporting
- **Data quality validation** before storage
- **Graceful degradation** for partial failures

## 🔧 **Troubleshooting**

### **Common Issues**

**1. "No API key provided"**
```bash
export ALPHA_VANTAGE_API_KEY="your_key_here"
# or set in code:
api_key = "your_key_here"
```

**2. "Rate limit hit"**
- Normal behavior with free API keys (5 calls/minute)
- System automatically waits and retries
- Consider premium API key for faster fetching

**3. "Insufficient data quality"**
- Ticker may not exist or have limited financial data
- Check Alpha Vantage directly: `https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol=TICKER&apikey=demo`
- Some tickers (ETFs, small caps) have incomplete data

**4. "Database connection lost"**
- Check if database file exists: `data/invsys_database.db`
- Ensure proper file permissions
- Try reinitializing with `DatabaseManager()`

**5. "Transaction rollback"**
- Check logs for specific ticker that caused failure
- Consider using individual commit mode for partial success
- Validate ticker symbols before batch operations

### **Debugging Tips**

**1. Enable Detailed Logging**
```python
# Check logs table for detailed operation history
cursor.execute("SELECT * FROM logs WHERE log_level = 'ERROR' ORDER BY timestamp DESC LIMIT 10")
errors = cursor.fetchall()
for error in errors:
    print(f"{error[2]} - {error[4]}: {error[5]}")
```

**2. Check Data Freshness**
```python
freshness_report = data_manager.get_data_freshness_report(['AAPL', 'MSFT'])
print(f"Never fetched: {freshness_report['never_fetched']}")
print(f"Fresh data: {freshness_report['fresh_data']}")
```

**3. Manual API Testing**
```bash
curl "https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol=AAPL&apikey=demo"
```

## 📈 **Performance Metrics**

The system tracks and reports:
- **Successful vs failed fetches**
- **API calls made vs tickers processed**
- **Current backoff multiplier**
- **Session duration and throughput**
- **Transaction success rates**

```python
metrics = fetcher.get_performance_metrics()
print(f"Success rate: {metrics['successful_fetches']}/{metrics['api_calls_made']}")
print(f"Failed tickers: {fetcher.get_failed_tickers()}")
```

## 🔮 **Future Enhancements**

- [ ] Add company name fetching from Alpha Vantage overview
- [ ] Implement parallel fetching with rate limiting
- [ ] Add support for other data providers (Yahoo Finance, Quandl)
- [ ] Create data validation rules engine
- [ ] Add automated retry queue for failed tickers
- [ ] Support for incremental data updates
- [ ] Database migration system for schema updates

## 📚 **API Reference**

### **DataFetcher Methods**
- `fetch_fundamentals(ticker)` → `(success, fundamentals, raw_data)`
- `fetch_multiple_tickers(ticker_list, force_refresh=False)` → `results_dict`
- `get_performance_metrics()` → `metrics_dict`
- `get_failed_tickers()` → `List[str]`

### **DataManager Methods**
- `get_tickers_needing_update(ticker_list)` → `(to_fetch, to_skip)`
- `stage_data(ticker, fundamentals, raw_data)` → `None`
- `get_staged_data()` → `Dict[ticker, data]`
- `clear_staged_data(ticker=None)` → `None`
- `force_cleanup_staging_data()` → `int` (number of expired entries removed)
- `get_staging_cache_status()` → `Dict` (cache size, oldest entry age, next cleanup time)
- `get_data_freshness_report(ticker_list)` → `report_dict`
- `set_refresh_policy(min_days, force_days)` → `None`

### **DataInserter Methods**
- `insert_staged_data(staged_data, use_transaction=True)` → `results_dict`

### **DatabaseManager Methods**
- `get_logger(session_id)` → `Logger`

## 📝 **Notes**

- **Demo API Key**: Limited to 5 calls per minute, 500 calls per day
- **Production API Key**: Required for real-time usage
- **SQLite Database**: Suitable for development, consider PostgreSQL for production
- **Memory Usage**: Staging cache automatically expires after 24 hours with cleanup every 5 minutes
- **Transaction Mode**: Default is all-or-nothing, use individual mode for fault tolerance

## 📄 **License**

GNU Affero General Public License v3.0 - See LICENSE file for details.

## 📁 **File Structure**

```
src/database/
├── __init__.py            # Module initialization
├── database_setup.py      # Database initialization and schema management
├── database_handler.py    # DataManager class for freshness and staging
├── fetch_data.py          # DataFetcher class for API data retrieval
├── data_inserter.py       # DataInserter class for database insertion
└── README.md             # This documentation
``` 