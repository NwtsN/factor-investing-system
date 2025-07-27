# Company Information Fetching Implementation Plan

## Overview

This plan details how to add company information fetching to the investment analysis system. We'll fetch company name, description, industry, sector, and country from Alpha Vantage's OVERVIEW API endpoint and integrate it throughout the data pipeline.

## Current State vs Target State

**Current State:**
- DataFetcher fetches from 4 Alpha Vantage endpoints (INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS)
- Stock records are created with only ticker symbol
- Company name defaults to ticker symbol
- Description, industry, sector, country fields remain NULL

**Target State:**
- DataFetcher will fetch from 5 endpoints (adding COMPANY_OVERVIEW)
- Stock records will be created with full company information
- All company fields will be populated when available

## Data Flow

```
1. Alpha Vantage API → DataFetcher (fetch_fundamentals)
   └── Add COMPANY_OVERVIEW endpoint
   
2. DataFetcher → DataManager (stage_data)
   └── Include company fields in fundamentals dict
   
3. DataManager → DataInserter (insert_staged_data)
   └── Extract company data and pass to stock creation
   
4. DataInserter → Database (stocks table)
   └── Create/update stock records with company info
```

## Implementation Steps

### Step 1: Add COMPANY_OVERVIEW Endpoint to DataFetcher

**File:** `src/database/fetch_data.py`

In the `fetch_fundamentals` method, locate the endpoints dictionary (around line 183) and add the COMPANY_OVERVIEW endpoint:

```python
# Define endpoints (keys are local identifiers, not API function names)
endpoints = {
    "INCOME_STATEMENT": f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker}&apikey={used_api_key}",
    "BALANCE_SHEET": f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker}&apikey={used_api_key}",
    "CASH_FLOW": f"https://www.alphavantage.co/query?function=CASH_FLOW&symbol={ticker}&apikey={used_api_key}",
    "Earnings": f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker}&apikey={used_api_key}",
    "COMPANY_OVERVIEW": f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={used_api_key}",
}
```

### Step 2: Update API Response Validation

**File:** `src/database/fetch_data.py`

Update the `_validate_api_response` method (around line 374) to handle COMPANY_OVERVIEW responses:

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
    elif endpoint_type == "COMPANY_OVERVIEW":
        # Company overview should have at least Symbol and Name
        return ("Symbol" in json_data and "Name" in json_data)
    
    return True
```

### Step 3: Extract Company Information in _extract_fundamentals

**File:** `src/database/fetch_data.py`

At the end of the `_extract_fundamentals` method (before the return statement), add company information extraction:

```python
        fundamentals = {
            "ticker": ticker,
            "fiscal_date_ending": most_recent_fiscal_date,
            "market_cap": np.nan,
            
            # ... (all existing fields) ...
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

### Step 4: Update DataInserter's _get_or_create_stock_id Method

**File:** `src/database/data_inserter.py`

Replace the entire `_get_or_create_stock_id` method (around line 177) with an enhanced version that handles company data:

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

### Step 5: Add _update_stock_info Helper Method

**File:** `src/database/data_inserter.py`

Add this new method after `_get_or_create_stock_id`:

```python
def _update_stock_info(self, stock_id: int, ticker: str, company_data: dict) -> None:
    """
    Update stock information with company overview data.
    Only updates if new data is more complete than existing data.
    
    Args:
        stock_id: The stock_id to update
        ticker: Ticker symbol for logging
        company_data: Dict with company information
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
                # Build update query dynamically based on what needs updating
                update_fields = []
                update_values = []
                
                if new_name and new_name != ticker:
                    update_fields.append("company_name = ?")
                    update_values.append(new_name)
                
                if new_desc:
                    update_fields.append("description = ?")
                    update_values.append(new_desc[:5000])  # Limit description length
                
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
                else:
                    self.logger.log("DataInserter", 
                                   f"No updates needed for {ticker} - existing data is complete", 
                                   level="DEBUG")
            else:
                self.logger.log("DataInserter", 
                               f"Skipping update for {ticker} - existing data is already complete", 
                               level="DEBUG")
                
    except Exception as e:
        self.logger.log("DataInserter", 
                       f"Failed to update company information for {ticker}: {e}", 
                       level="WARNING")
        # Don't raise - this is not critical enough to fail the entire insertion
```

### Step 6: Modify insert_staged_data to Pass Company Data

**File:** `src/database/data_inserter.py`

In the `insert_staged_data` method, find where stock_id is created (around line 122) and update it:

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

## API Response Example

The COMPANY_OVERVIEW endpoint returns data like this:

```json
{
    "Symbol": "AAPL",
    "Name": "Apple Inc.",
    "Description": "Apple Inc. designs, manufactures, and markets smartphones...",
    "Exchange": "NASDAQ",
    "Currency": "USD",
    "Country": "USA",
    "Sector": "Technology",
    "Industry": "Consumer Electronics",
    "MarketCapitalization": "2903329374208",
    // ... more fields ...
}
```

## Key Implementation Details

### Rate Limiting
- The COMPANY_OVERVIEW endpoint counts as 1 API call
- Each ticker now requires 5 API calls (up from 4)
- Free tier allows 5 calls/minute, so 1 ticker per minute max
- Existing rate limiting in DataFetcher handles this automatically

### Data Quality
- Company name falls back to ticker if not available
- Description is limited to 5000 characters (database field limit)
- Empty strings are used for missing fields (not NULL)
- Existing records are only updated if new data is better

### Error Handling
- Missing company data doesn't fail the entire fetch
- Update failures are logged but don't stop insertion
- API errors are handled gracefully with fallback values

## Verification

After implementation, new stock records will include company information:

```sql
-- Check a newly fetched stock
SELECT ticker, company_name, sector, industry, country 
FROM stocks 
WHERE ticker = 'AAPL';

-- Should show:
-- AAPL | Apple Inc. | Technology | Consumer Electronics | USA
```

## Performance Considerations

1. **API Calls**: Each ticker now requires 5 calls instead of 4
2. **Processing Time**: Minimal overhead for parsing company data
3. **Database Operations**: One additional SELECT when updating existing stocks
4. **Memory Usage**: Company data adds ~1KB per ticker (negligible)

## Summary

This implementation seamlessly integrates company information fetching into the existing data pipeline with minimal code changes:

1. **DataFetcher**: Add endpoint, validate response, extract fields
2. **DataInserter**: Accept company data, create/update stock records
3. **No Schema Changes**: Database already has all required fields
4. **Backward Compatible**: Works with existing code and data

The system will now automatically fetch and store company information whenever fundamental data is retrieved. 