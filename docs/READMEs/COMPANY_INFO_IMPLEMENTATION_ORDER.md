# Company Information Feature - Implementation Order

## Overview
This document outlines the optimal order for implementing the company information fetching feature, with quick notes on what, why, and how for each task.

## Implementation Order

### Phase 1: DataFetcher Modifications (fetch_data.py)
*These changes enable fetching company data from the API*

#### Task 1: Add COMPANY_OVERVIEW Endpoint
**What**: Add the 5th API endpoint to the endpoints dictionary in `fetch_fundamentals` method  
**Why**: Need to call Alpha Vantage's OVERVIEW API to get company information  
**How**: Add one line to the endpoints dict: `"COMPANY_OVERVIEW": f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={used_api_key}"`  
**Location**: Line ~188 in fetch_data.py  

#### Task 2: Update API Response Validation
**What**: Modify `_validate_api_response` to handle COMPANY_OVERVIEW responses  
**Why**: OVERVIEW API returns different JSON structure than financial endpoints  
**How**: Add elif branch checking for "Symbol" and "Name" fields  
**Location**: Line ~390 in fetch_data.py  

#### Task 3: Extract Company Fields
**What**: Add company field extraction to `_extract_fundamentals` method  
**Why**: Need to pull name, description, industry, sector, country from API response  
**How**: Check if COMPANY_OVERVIEW exists in raw_data, extract fields with fallbacks  
**Location**: End of `_extract_fundamentals` method before return statement  

### Phase 2: DataInserter Modifications (data_inserter.py)
*These changes enable storing company data in the database*

#### Task 4: Enhance Stock Creation Method
**What**: Update `_get_or_create_stock_id` to accept and use company data  
**Why**: Currently only creates stocks with ticker as company name  
**How**: Add company_data parameter, use it in INSERT statement, call update helper for existing records  
**Location**: Replace entire method starting at line ~178  

#### Task 5: Add Update Helper Method
**What**: Create new `_update_stock_info` method  
**Why**: Need intelligent updating - only update if new data is better than existing  
**How**: Check existing values, build dynamic UPDATE query for non-empty new values  
**Location**: Add after `_get_or_create_stock_id` method  

#### Task 6: Connect Data Flow
**What**: Modify `insert_staged_data` to extract and pass company data  
**Why**: Need to bridge the data from DataFetcher to DataInserter  
**How**: Extract company fields from fundamentals dict, pass to stock creation  
**Location**: Line ~124 where `_get_or_create_stock_id` is called  

## Quick Implementation Checklist

```
□ Task 1: Add endpoint URL (1 line change)
□ Task 2: Add validation branch (5 lines)
□ Task 3: Add extraction logic (15 lines)
□ Task 4: Replace stock creation method (~50 lines)
□ Task 5: Add update helper method (~60 lines)
□ Task 6: Extract and pass company data (8 lines)
```

## Testing Points

After each phase:
1. **After Phase 1**: Check that fetcher gets company data in fundamentals dict
2. **After Phase 2**: Verify database has company information in stocks table

## Key Considerations

- **Order Matters**: Must modify DataFetcher first so data is available for DataInserter
- **Backward Compatible**: All changes maintain compatibility with existing data
- **Rate Limits**: No special handling needed - existing rate limiter handles 5th call
- **Error Handling**: Each component has fallbacks if company data unavailable

## Estimated Time

- Phase 1 (DataFetcher): ~30 minutes
- Phase 2 (DataInserter): ~45 minutes
- Testing: ~15 minutes
- **Total**: ~1.5 hours

## Why This Order?

1. **Data Flow**: Follow the natural flow of data (API → Fetcher → Inserter → Database)
2. **Dependencies**: DataInserter changes depend on DataFetcher providing the data
3. **Testability**: Can test Phase 1 independently before moving to Phase 2
4. **Risk Mitigation**: If issues arise, easier to debug when implementing in data flow order 