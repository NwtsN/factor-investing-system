# Company Info Implementation - Quick Reference

## 🚀 Quick Start Order

### Phase 1: DataFetcher (fetch_data.py)
1. **Line ~188**: Add `"COMPANY_OVERVIEW": f"...OVERVIEW..."` to endpoints
2. **Line ~390**: Add `elif endpoint_type == "COMPANY_OVERVIEW":` validation
3. **Line ~545**: Add company field extraction before `return fundamentals`

### Phase 2: DataInserter (data_inserter.py)  
4. **Line ~178**: Replace `_get_or_create_stock_id` method (add company_data param)
5. **After #4**: Add new `_update_stock_info` helper method
6. **Line ~124**: Extract company data and pass to `_get_or_create_stock_id`

## 📝 Code Snippets

### Task 1: Add Endpoint
```python
"COMPANY_OVERVIEW": f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={used_api_key}",
```

### Task 2: Validation
```python
elif endpoint_type == "COMPANY_OVERVIEW":
    return ("Symbol" in json_data and "Name" in json_data)
```

### Task 3: Extract Fields
```python
if "COMPANY_OVERVIEW" in raw_data:
    overview = raw_data["COMPANY_OVERVIEW"]
    fundamentals['company_name'] = overview.get('Name', ticker)
    fundamentals['description'] = overview.get('Description', '')[:5000]
    fundamentals['industry'] = overview.get('Industry', '')
    fundamentals['sector'] = overview.get('Sector', '')
    fundamentals['country'] = overview.get('Country', '')
else:
    fundamentals['company_name'] = ticker
    fundamentals['description'] = ''
    fundamentals['industry'] = ''
    fundamentals['sector'] = ''
    fundamentals['country'] = ''
```

### Task 6: Connect Flow
```python
fundamentals = data['fundamentals']
company_data = {
    'company_name': fundamentals.get('company_name'),
    'description': fundamentals.get('description'),
    'industry': fundamentals.get('industry'),
    'sector': fundamentals.get('sector'),
    'country': fundamentals.get('country')
}
stock_id = self._get_or_create_stock_id(ticker, company_data)
```

## ✅ Verification Commands

```bash
# After Phase 1 - Check if company data is fetched
python -c "from src.database.fetch_data import DataFetcher; print('Check fundamentals dict for company fields')"

# After Phase 2 - Check database
sqlite3 data/invsys.db "SELECT ticker, company_name, sector, industry FROM stocks WHERE ticker='AAPL';"
```

## ⚠️ Remember
- Each ticker now uses 5 API calls (was 4)
- Free tier: 1 ticker per minute max
- Company data has fallbacks if unavailable
- Description limited to 5000 chars 