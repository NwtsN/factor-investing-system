# Company Information Fetching Implementation Guide

## Overview

This guide details how to add company information fetching (name, description, industry, sector, country) to the investment analysis system using Alpha Vantage's OVERVIEW endpoint.

### What We're Adding
- Fetch company metadata from Alpha Vantage's OVERVIEW endpoint
- Store company name, description, industry, sector, and country in the `stocks` table
- Update the data flow to handle this additional information

### Current vs. Future State

**Current State:**
```sql
-- stocks table currently populated as:
stock_id | ticker | company_name | description | industry | sector | country
---------|--------|--------------|-------------|----------|--------|--------
1        | AAPL   | AAPL         | NULL        | NULL     | NULL   | NULL
```

**Future State:**
```sql
-- stocks table will contain:
stock_id | ticker | company_name    | description                  | industry          | sector      | country
---------|--------|-----------------|------------------------------|-------------------|-------------|--------
1        | AAPL   | Apple Inc.      | Apple Inc. designs, manu...  | Consumer Electronics | Technology | USA
```

## Architecture Overview

### Data Flow
```
1. Alpha Vantage API → DataFetcher
   - Currently: 4 endpoints (INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS)
   - Adding: COMPANY_OVERVIEW endpoint
   
2. DataFetcher → DataManager (staging)
   - No changes needed - staging already handles arbitrary data
   
3. DataManager → DataInserter
   - Update to pass company data when creating/updating stock records
   
4. DataInserter → Database
   - Update stock record creation to include company fields
```

## Alpha Vantage Company Overview API

### Endpoint Details
- **Function**: `OVERVIEW`
- **URL**: `https://www.alphavantage.co/query?function=OVERVIEW&symbol={TICKER}&apikey={API_KEY}`
- **Rate Limit**: Counts as 1 API call (now 5 total per ticker)

### Key Fields We Need
```json
{
    "Symbol": "AAPL",
    "Name": "Apple Inc.",              // → company_name
    "Description": "Apple Inc...",      // → description
    "Industry": "Consumer Electronics", // → industry
    "Sector": "Technology",            // → sector
    "Country": "USA"                   // → country
}
```

## Implementation Steps

### Step 1: Add Company Overview Endpoint to DataFetcher

**File**: `src/database/fetch_data.py`  
**Location**: In `fetch_fundamentals` method, around line 183-188

Add the COMPANY_OVERVIEW endpoint:
```python
# Define endpoints (keys are local identifiers, not API function names)
endpoints = {
    "INCOME_STATEMENT": f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker}&apikey={used_api_key}",
    "BALANCE_SHEET": f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker}&apikey={used_api_key}",
    "CASH_FLOW": f"https://www.alphavantage.co/query?function=CASH_FLOW&symbol={ticker}&apikey={used_api_key}",
    "Earnings": f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker}&apikey={used_api_key}",
    "COMPANY_OVERVIEW": f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={used_api_key}",  # NEW
}
```

### Step 2: Update API Response Validation

**File**: `src/database/fetch_data.py`  
**Location**: In `_validate_api_response` method, around line 374-390

Add validation for COMPANY_OVERVIEW:
```python
def _validate_api_response(self, json_data: dict, endpoint_type: str) -> bool:
    """Enhanced API response validation."""
    if not isinstance(json_data, dict):
        return False
        
    # Check for API error messages
    if "Error Message" in json_data or "Note" in json_data:
        return False
        
    # Endpoint-specific validation
    if endpoint_type in ["INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW"]:
        return ("annualReports" in json_data and "quarterlyReports" in json_data and
                len(json_data.get("annualReports", [])) > 0 and
                len(json_data.get("quarterlyReports", [])) > 0)
    elif endpoint_type == "Earnings":
        return ("quarterlyEarnings" in json_data and 
                len(json_data.get("quarterlyEarnings", [])) >= 5)
    elif endpoint_type == "COMPANY_OVERVIEW":  # NEW
        # Company overview should have at least Symbol and Name
        return ("Symbol" in json_data and "Name" in json_data)
    
    return True
```

### Step 3: Extract Company Information in _extract_fundamentals

**File**: `src/database/fetch_data.py`  
**Location**: At the end of `_extract_fundamentals` method, before `return fundamentals`

Add company data extraction:
```python
    fundamentals = {
        "ticker": ticker,
        "fiscal_date_ending": most_recent_fiscal_date,
        "market_cap": np.nan,
        
        # ... (all existing fields remain) ...
    }
    
    # Add company overview data if available
    if "COMPANY_OVERVIEW" in raw_data:
        overview = raw_data["COMPANY_OVERVIEW"]
        fundamentals['company_name'] = overview.get('Name', ticker)
        fundamentals['description'] = overview.get('Description', '')[:5000]  # Limit to 5000 chars
        fundamentals['industry'] = overview.get('Industry', '')
        fundamentals['sector'] = overview.get('Sector', '')
        fundamentals['country'] = overview.get('Country', '')
    else:
        # Fallback values if company overview is not available
        fundamentals['company_name'] = ticker
        fundamentals['description'] = ''
        fundamentals['industry'] = ''
        fundamentals['sector'] = ''
        fundamentals['country'] = ''

    return fundamentals
```

### Step 4: Update DataInserter to Handle Company Data

**File**: `src/database/data_inserter.py`  
**Location**: Replace the `_get_or_create_stock_id` method (around line 177-212)

Enhanced method that accepts and uses company data:
```python
def _get_or_create_stock_id(self, ticker: str, company_data: dict = None) -> int:
    """
    Get stock_id for ticker, creating stock record if necessary.
    Now also handles company information.
    
    Args:
        ticker: Stock ticker symbol
        company_data: Optional dict with company_name, description, industry, sector, country
    """
    # Validate ticker format (alphanumeric and common symbols only)
    if not ticker or not ticker.replace('.', '').replace('-', '').isalnum():
        raise ValueError(f"Invalid ticker format: {ticker}")
    
    # Validate ticker length (NYSE/NASDAQ tickers are typically 1-5 characters)
    if len(ticker) > 10:
        raise ValueError(f"Ticker too long (max 10 characters): {ticker}")
    
    # Check if stock exists
    self.cursor.execute("SELECT stock_id FROM stocks WHERE ticker = ?", (ticker,))
    result = self.cursor.fetchone()
    
    if result:
        stock_id = result[0]
        
        # Update company information if provided and not just placeholder data
        if company_data and company_data.get('company_name') != ticker:
            self._update_stock_info(stock_id, ticker, company_data)
        
        return stock_id
    
    # Create new stock record with company information
    try:
        # Extract company data or use defaults
        company_name = ticker  # Default
        description = ''
        industry = ''
        sector = ''
        country = ''
        
        if company_data:
            company_name = company_data.get('company_name', ticker)
            description = company_data.get('description', '')[:5000]  # Limit description length
            industry = company_data.get('industry', '')
            sector = company_data.get('sector', '')
            country = company_data.get('country', '')
        
        self.cursor.execute(
            """INSERT INTO stocks (ticker, company_name, description, industry, sector, country) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker, company_name, description, industry, sector, country)
        )
        stock_id = self.cursor.lastrowid
        
        # Log with company name if available
        if company_name != ticker:
            self.logger.log("DataInserter", 
                          f"Created new stock record for {ticker} ({company_name}) with ID {stock_id}", 
                          level="INFO")
        else:
            self.logger.log("DataInserter", 
                          f"Created new stock record for {ticker} with ID {stock_id}", 
                          level="INFO")
        
        return stock_id
        
    except sqlite3.IntegrityError as e:
        # Handle race condition where another process created the record
        self.logger.log("DataInserter", f"Stock creation race condition for {ticker}, retrying: {e}", level="WARNING")
        self.cursor.execute("SELECT stock_id FROM stocks WHERE ticker = ?", (ticker,))
        result = self.cursor.fetchone()
        if result:
            return result[0]
        raise
```

### Step 5: Add Stock Info Update Method

**File**: `src/database/data_inserter.py`  
**Location**: Add after `_get_or_create_stock_id` method

```python
def _update_stock_info(self, stock_id: int, ticker: str, company_data: dict) -> None:
    """
    Update stock information with company overview data.
    Only updates if new data is more complete than existing data.
    """
    try:
        # First, check what data currently exists
        self.cursor.execute(
            """SELECT company_name, description, industry, sector, country 
               FROM stocks WHERE stock_id = ?""",
            (stock_id,)
        )
        existing = self.cursor.fetchone()
        
        if existing:
            existing_name, existing_desc, existing_industry, existing_sector, existing_country = existing
            
            # Only update if we have better data
            needs_update = False
            
            new_name = company_data.get('company_name', '')
            new_desc = company_data.get('description', '')
            new_industry = company_data.get('industry', '')
            new_sector = company_data.get('sector', '')
            new_country = company_data.get('country', '')
            
            # Check if new data is better than existing data
            if new_name and new_name != ticker and (not existing_name or existing_name == ticker):
                needs_update = True
            if new_desc and (not existing_desc or existing_desc == ''):
                needs_update = True
            if new_industry and (not existing_industry or existing_industry == ''):
                needs_update = True
            if new_sector and (not existing_sector or existing_sector == ''):
                needs_update = True
            if new_country and (not existing_country or existing_country == ''):
                needs_update = True
            
            if needs_update:
                # Build update query dynamically
                update_fields = []
                update_values = []
                
                if new_name and new_name != ticker:
                    update_fields.append("company_name = ?")
                    update_values.append(new_name)
                
                if new_desc:
                    update_fields.append("description = ?")
                    update_values.append(new_desc[:5000])
                
                if new_industry:
                    update_fields.append("industry = ?")
                    update_values.append(new_industry)
                
                if new_sector:
                    update_fields.append("sector = ?")
                    update_values.append(new_sector)
                
                if new_country:
                    update_fields.append("country = ?")
                    update_values.append(new_country)
                
                if update_fields:
                    update_values.append(stock_id)
                    query = f"UPDATE stocks SET {', '.join(update_fields)} WHERE stock_id = ?"
                    
                    self.cursor.execute(query, update_values)
                    
                    if self.cursor.rowcount > 0:
                        self.logger.log("DataInserter", 
                                       f"Updated company information for {ticker} (stock_id: {stock_id})", 
                                       level="INFO")
                
    except Exception as e:
        self.logger.log("DataInserter", 
                       f"Failed to update company information for {ticker}: {e}", 
                       level="WARNING")
        # Don't raise - this is not critical enough to fail the entire insertion
```

### Step 6: Update insert_staged_data Method

**File**: `src/database/data_inserter.py`  
**Location**: In `insert_staged_data` method, around line 122-127

Modify to extract and pass company data:
```python
# Extract company data from fundamentals
fundamentals = data['fundamentals']
company_data = {
    'company_name': fundamentals.get('company_name'),
    'description': fundamentals.get('description'),
    'industry': fundamentals.get('industry'),
    'sector': fundamentals.get('sector'),
    'country': fundamentals.get('country')
}

# Get or create stock_id with company data
stock_id = self._get_or_create_stock_id(ticker, company_data)

# Continue with fundamental data insertion
raw_api_data = data['raw_data']
```

## How It All Works Together

### 1. Data Fetching Flow
```
DataFetcher.fetch_fundamentals(ticker)
├── Fetches 5 endpoints (including new COMPANY_OVERVIEW)
├── Validates each response
├── Extracts fundamentals + company info
└── Returns (success, fundamentals_dict, raw_data)
```

### 2. Data Staging Flow
```
DataManager.stage_data(ticker, fundamentals, raw_data)
├── Stores in staging cache
└── Company info is part of fundamentals dict
```

### 3. Data Insertion Flow
```
DataInserter.insert_staged_data(staged_data)
├── Extracts company_data from fundamentals
├── Calls _get_or_create_stock_id(ticker, company_data)
│   ├── If new stock: Creates with full company info
│   └── If exists: Updates if better data available
└── Continues with financial data insertion
```

## Key Design Decisions

### 1. Smart Updates
- Only updates existing records if new data is better
- Prevents overwriting good data with empty fields
- Logs all update decisions for transparency

### 2. Graceful Degradation
- If COMPANY_OVERVIEW fails, other data still processes
- Uses ticker as company_name fallback
- Empty strings for missing fields (not NULL)

### 3. Data Validation
- Limits description to 5000 characters
- Validates ticker format before database operations
- Handles race conditions in multi-process scenarios

### 4. Performance Considerations
- One additional API call per ticker (20% increase)
- Company data is small (~1-2KB per ticker)
- No significant memory or storage impact

## Summary

This implementation adds company information fetching with minimal changes:

1. **DataFetcher**: Add 1 endpoint, update validation, extract fields
2. **DataInserter**: Accept company data, create/update stock records
3. **No changes needed**: DataManager, database schema, other components

The system now automatically fetches and stores company information for every ticker processed, enhancing data quality and enabling sector/industry-based analysis. 