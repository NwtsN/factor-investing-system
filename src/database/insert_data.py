#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Data fetching and processing from Alpha Vantage API.

Copyright (C) 2025 Neil Donald Watson

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import sys
import time
import json
import uuid
import sqlite3
import requests
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Union, Dict, Any, List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add parent directory to path for imports  
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils.logging import Logger
from config import DB_PATH
from database.database_handler import DataManager


class DataInserter:
    """Handles insertion of fetched data into the database."""
    def __init__(self, logger: Logger, db_path: str = None) -> None:
        self.logger = logger
        self.session_id: str = str(uuid.uuid4())
        self.db_path: str = db_path or DB_PATH
        self.conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        self.cursor: sqlite3.Cursor = self.conn.cursor()
        # TODO: Implement data insertion methods


class DataFetcher:
    """
    Enhanced data fetcher that works with DataManager for intelligent fetching.
    Uses database-driven caching and staging for database insertion.
    
    Can be used standalone (one ticker at a time) or with DataManager for batch operations.
    """
    
    def __init__(self, logger: Logger, data_manager: DataManager = None, api_key: str = None) -> None:
        self.logger = logger
        self.data_manager = data_manager  # Optional for standalone use
        self.api_key = api_key
        self.failed_tickers: set[str] = set()  # Use set to avoid duplicates
        self.success_count: int = 0
        self.api_calls_made: int = 0
        self.fetch_start_time: Optional[datetime] = None
        
        # HTTP session with optimized settings
        self.session: Optional[requests.Session] = None
        self._setup_session()
        
        # Rate limiting state
        self.last_api_call: Optional[datetime] = None
        self.min_interval_seconds: float = 12.0  # Alpha Vantage: ~5 calls per minute
        self.current_backoff: float = 1.0
        self.max_backoff: float = 300.0  # 5 minutes max
        
        # Data quality thresholds
        self.min_required_fields = 6  # Reduced from 8 for more flexibility
        
    def _setup_session(self) -> None:
        """Configure HTTP session with retry strategy and connection pooling."""
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            respect_retry_after_header=True
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set common headers
        self.session.headers.update({
            'User-Agent': 'invsys/1.0 Financial Data Fetcher',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        })

    def __enter__(self):
        """Context manager entry."""
        self.fetch_start_time = datetime.now(timezone.utc)
        self.logger.log("DataFetcher", "Session started", level="INFO")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit with cleanup and metrics logging."""
        self.close()
        if self.fetch_start_time:
            duration = datetime.now(timezone.utc) - self.fetch_start_time
            self._log_session_metrics(duration)

    def close(self) -> None:
        """Clean up resources."""
        if self.session:
            self.session.close()
            self.session = None
        self.logger.log("DataFetcher", "Session closed and resources cleaned up", level="INFO")

    def fetch_multiple_tickers(self, ticker_list: List[str], force_refresh: bool = False) -> Dict[str, Any]:
        """
        Intelligently fetch data for multiple tickers, skipping those with recent data.
        Requires DataManager to be initialized.
        
        Args:
            ticker_list: List of ticker symbols to fetch
            force_refresh: If True, fetch all tickers regardless of last fetch date
            
        Returns:
            Dict with fetch results and summary
        """
        if not self.data_manager:
            raise ValueError("DataManager required for batch operations")
            
        if force_refresh:
            tickers_to_fetch = ticker_list
            tickers_skipped = []
            self.logger.log("DataFetcher", "Force refresh requested - fetching all tickers", level="INFO")
        else:
            tickers_to_fetch, tickers_skipped = self.data_manager.get_tickers_needing_update(ticker_list)
        
        results = {
            'successful_fetches': [],
            'failed_fetches': [],
            'skipped_tickers': tickers_skipped,
            'total_requested': len(ticker_list),
            'total_fetched': 0,
            'total_skipped': len(tickers_skipped),
            'api_calls_made': 0
        }
        
        # Fetch data for tickers that need updating
        for ticker in tickers_to_fetch:
            success, fundamentals, raw_data = self.fetch_fundamentals(ticker)
            
            if success:
                # Stage the data with DataManager instead of local caching
                self.data_manager.stage_data(ticker, fundamentals, raw_data)
                results['successful_fetches'].append(ticker)
            else:
                results['failed_fetches'].append(ticker)
        
        results['total_fetched'] = len(results['successful_fetches'])
        results['api_calls_made'] = self.api_calls_made
        
        self.logger.log("DataFetcher", 
                       f"Batch fetch complete: {results['total_fetched']} successful, "
                       f"{len(results['failed_fetches'])} failed, {results['total_skipped']} skipped", 
                       level="INFO")
        
        return results

    def fetch_fundamentals(self, ticker: str, api_key: str = None) -> tuple[bool, dict, dict]:
        """
        Fetches and parses fundamental data for a given ticker.
        Returns a tuple: (success, cleaned_fundamentals_dict, raw_api_data)
        """
        # Use instance API key if not provided
        used_api_key = api_key or self.api_key
        if not used_api_key:
            self.logger.log("API Key", f"{ticker}: No API key provided", level="ERROR")
            self.failed_tickers.add(ticker)
            return False, {}, {}

        # Define endpoints
        endpoints = {
            "INCOME_STATEMENT": f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker}&apikey={used_api_key}",
            "BALANCE_SHEET": f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker}&apikey={used_api_key}",
            "CASH_FLOW": f"https://www.alphavantage.co/query?function=CASH_FLOW&symbol={ticker}&apikey={used_api_key}",
            "Earnings": f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker}&apikey={used_api_key}",
        }

        raw_data = {}

        # Step 1: Fetch and validate all endpoints
        for label, url in endpoints.items():
            self._enforce_rate_limit()
            json_data = self._fetch_with_retry(ticker, label, url)
            if json_data is None:
                self.failed_tickers.add(ticker)
                return False, {}, {}
            raw_data[label] = json_data
            self.api_calls_made += 1

        # Step 2: Parse relevant fields
        try:
            fundamentals = self._extract_fundamentals(ticker, raw_data)
            
            # Data quality validation
            if not self._validate_data_quality(ticker, fundamentals):
                self.failed_tickers.add(ticker)
                return False, {}, {}
            
            self.success_count += 1
            self._adjust_backoff(True)
            
            self.logger.log("Fundamentals", 
                          f"{ticker}: extracted {len(fundamentals)} fields", 
                          level="INFO")
            return True, fundamentals, raw_data
            
        except Exception as e:
            self.logger.log("Fundamentals", 
                          f"{ticker}: parsing error - {e}", 
                          level="ERROR")
            self.failed_tickers.add(ticker)
            self._adjust_backoff(False)
            return False, {}, {}

    def _enforce_rate_limit(self) -> None:
        """Intelligent rate limiting with exponential backoff."""
        if self.last_api_call is None:
            self.last_api_call = datetime.now(timezone.utc)
            return
            
        time_since_last = (datetime.now(timezone.utc) - self.last_api_call).total_seconds()
        required_wait = self.min_interval_seconds * self.current_backoff
        
        if time_since_last < required_wait:
            sleep_time = required_wait - time_since_last
            self.logger.log("RateLimit", 
                          f"Sleeping {sleep_time:.1f}s (backoff: {self.current_backoff:.1f}x)", 
                          level="INFO")
            time.sleep(sleep_time)
        
        self.last_api_call = datetime.now(timezone.utc)

    def _adjust_backoff(self, success: bool) -> None:
        """Adjust backoff based on success/failure."""
        if success:
            # Reset to normal on success
            if self.current_backoff > 1.0:
                self.logger.log("RateLimit", 
                              f"Resetting backoff from {self.current_backoff:.1f}x to 1.0x after success", 
                              level="INFO")
            self.current_backoff = 1.0
        else:
            # Double backoff on failure, up to max
            old_backoff = self.current_backoff
            self.current_backoff = min(self.max_backoff, self.current_backoff * 2.0)
            if self.current_backoff != old_backoff:
                self.logger.log("RateLimit", 
                              f"Increasing backoff from {old_backoff:.1f}x to {self.current_backoff:.1f}x after failure", 
                              level="WARNING")

    def _validate_data_quality(self, ticker: str, fundamentals: dict) -> bool:
        """Comprehensive data quality validation."""
        # Check minimum required fields
        non_nan_fields = sum(1 for key, value in fundamentals.items() 
                           if key != 'ticker' and not (isinstance(value, float) and np.isnan(value)))
        
        if non_nan_fields < self.min_required_fields:
            self.logger.log("DataQuality", 
                          f"{ticker}: Insufficient data quality - only {non_nan_fields} valid fields", 
                          level="WARNING")
            return False
        
        # Additional business logic validations
        validations = [
            ("total_assets", lambda x: x > 0, "Total assets should be positive"),
            ("eps_last_5_qs", lambda x: isinstance(x, list) and len(x) >= 1, "Need at least 1 quarter of EPS data")
        ]
        
        for field, validator, message in validations:
            if field in fundamentals:
                try:
                    if not validator(fundamentals[field]):
                        self.logger.log("DataQuality", 
                                      f"{ticker}: {message}", 
                                      level="WARNING")
                        return False
                except Exception as e:
                    self.logger.log("DataQuality", 
                                  f"{ticker}: Validation error for {field}: {e}", 
                                  level="WARNING")
                    continue  # Skip this validation but don't fail entirely
        
        return True

    def _fetch_with_retry(self, ticker: str, label: str, url: str) -> Optional[dict]:
        """Enhanced fetch with retry logic and better error handling."""
        for attempt in range(3):  # Increased to 3 attempts
            try:
                response = self.session.get(url, timeout=15)  # Increased timeout
                
                if response.status_code == 200:
                    json_data = response.json()
                    
                    # Enhanced structure validation
                    if self._validate_api_response(json_data, label):
                        preview = str(json_data)[:60]
                        self.logger.log(f"API:{label}", 
                                      f"{ticker} - Success on attempt {attempt+1}. Preview: {preview}", 
                                      level="INFO")
                        return json_data
                    else:
                        raise ValueError("Invalid API response structure")
                        
                elif response.status_code == 401:
                    # Invalid API key - don't retry
                    self.logger.log(f"API:{label}", 
                                  f"{ticker} - Invalid API key (401)", 
                                  level="ERROR")
                    return None
                    
                elif response.status_code == 403:
                    # Forbidden - don't retry
                    self.logger.log(f"API:{label}", 
                                  f"{ticker} - Access forbidden (403)", 
                                  level="ERROR")
                    return None
                    
                elif response.status_code == 429:
                    wait_time = min(60 * (2 ** attempt), 300)  # Exponential backoff up to 5 minutes
                    self.logger.log(f"API:{label}", 
                                  f"{ticker} - Rate limit hit, sleeping {wait_time}s", 
                                  level="WARNING")
                    time.sleep(wait_time)
                    continue
                    
                elif response.status_code >= 500:
                    # Server error - retry with backoff
                    wait_time = min(5 * (2 ** attempt), 30)
                    self.logger.log(f"API:{label}", 
                                  f"{ticker} - Server error {response.status_code}, waiting {wait_time}s", 
                                  level="WARNING")
                    if attempt < 2:
                        time.sleep(wait_time)
                    continue
                    
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text[:100]}")
                    
            except Exception as e:
                wait_time = min(5 * (2 ** attempt), 30)  # Exponential backoff for retries
                self.logger.log(f"API:{label}", 
                              f"{ticker} - Attempt {attempt+1} failed: {e}. Waiting {wait_time}s", 
                              level="WARNING")
                if attempt < 2:  # Don't sleep on the last attempt
                    time.sleep(wait_time)
                    
        return None

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
        
        return True

    def _log_session_metrics(self, duration: timedelta) -> None:
        """Log comprehensive session metrics."""
        metrics = {
            "duration_seconds": duration.total_seconds(),
            "successful_fetches": self.success_count,
            "failed_tickers": len(self.failed_tickers),
            "api_calls_made": self.api_calls_made
        }
        
        self.logger.log("DataFetcher Metrics", 
                       f"Session completed: {json.dumps(metrics)}", 
                       level="INFO")

    def _extract_fundamentals(self, ticker: str, raw_data: dict) -> dict:
        """
        Extracts and transforms relevant fields from raw Alpha Vantage response.
        """
        income_q = raw_data["INCOME_STATEMENT"].get("quarterlyReports", [])
        income_a = raw_data["INCOME_STATEMENT"].get("annualReports", [])
        balance_q = raw_data["BALANCE_SHEET"].get("quarterlyReports", [])
        balance_a = raw_data["BALANCE_SHEET"].get("annualReports", [])
        cash_q = raw_data["CASH_FLOW"].get("quarterlyReports", [])
        cash_a = raw_data["CASH_FLOW"].get("annualReports", [])
        earnings_last5_qs = raw_data["Earnings"].get("quarterlyEarnings", [])[:5]

        # Check if we have at least some data
        if not any([income_q, income_a, balance_q, balance_a, cash_q, cash_a]):
            raise ValueError("No report data available in any endpoint")

        def safe_get(report_list, index, field):
            """Safely get a field from a report at given index."""
            try:
                if report_list and len(report_list) > index:
                    return float(report_list[index].get(field, np.nan))
                return np.nan
            except (ValueError, TypeError):
                return np.nan
            
        def extract_eps_list(earnings_list, count=5):
            """
            Extracts the most recent 'count' diluted EPS values from Alpha Vantage's EARNINGS endpoint.
            Returns a list of floats (or np.nan if parsing fails).
            """
            eps_values = []
            for i in range(min(count, len(earnings_list))):  # Don't exceed available data
                try:
                    eps_str = earnings_list[i].get("reportedEPS", "nan")
                    eps = float(eps_str)
                except Exception:
                    eps = np.nan
                eps_values.append(eps)
            return eps_values

        # Calculate working capital with safety checks
        total_current_assets = safe_get(balance_q, 0, "totalCurrentAssets")
        total_current_liabilities = safe_get(balance_q, 0, "totalCurrentLiabilities")
        working_capital = total_current_assets - total_current_liabilities if not np.isnan(total_current_assets) and not np.isnan(total_current_liabilities) else np.nan

        # calculate effective tax rate
        ite = safe_get(income_q, 0, "incomeTaxExpense")
        ibt = safe_get(income_q, 0, "incomeBeforeTax")
        effective_tax_rate = ite / ibt
        statutory_US_rate, loss_tax_rate = 0.21, 0.00
        # clean up effective tax rate
        etr_clean = np.where(
            ibt > 0,
            np.where(ite >= 0, effective_tax_rate, statutory_US_rate),
            np.where(ite > 0, loss_tax_rate, statutory_US_rate) 
        )

        fundamentals = {
            "ticker": ticker,
            "market_cap": np.nan,  # to be filled via price fetcher
            "total_debt": safe_get(balance_a, 0, "totalLiabilities"), # most recent annual balance sheet
            "cash_equiv": safe_get(balance_a, 0, "cashAndCashEquivalentsAtCarryingValue"), # most recent annual balance sheet
            "ebitda": safe_get(income_a, 0, "ebitda"), # most recent annual income statement
            "eps_last_5_qs": extract_eps_list(earnings_last5_qs), # most recent 5 quarters of earnings
            "cash_flow_ops": safe_get(cash_q, 0, "operatingCashflow"), # most recent quarterly operating cash flow
            "change_in_working_capital": safe_get(cash_q, 0, "changeInWorkingCapital"), # QoQ change in working capital
            "interest_expense": safe_get(income_q, 0, "interestExpense"), # most recent reported quarterly interest expense
            "total_assets": safe_get(balance_q, 0, "totalAssets"), # most recent total assets (reported quarterly) - used for gross assets in CROCI calculation
            "working_capital": working_capital, # most recent working capital (reported quarterly)
            "effective_tax_rate": etr_clean, # AV does not offer ETR so we have to compute it with sensible fallbacks 
            #in case of tax benefits on +ve earnings, company losing money and still paying tax, etc.
            "longTermInvestments": safe_get(balance_q, 0, "longTermInvestments") # proxy for investments in associates in CROCI calculation - biasing calculation 
            # downward to mitigate affect of hidden or under-reported capital
        }

        return fundamentals
    
    def get_performance_metrics(self) -> dict:
        """Get current performance metrics."""
        return {
            "successful_fetches": self.success_count,
            "failed_tickers": len(self.failed_tickers),
            "api_calls_made": self.api_calls_made,
            "current_backoff_multiplier": self.current_backoff
        }
    
    def get_failed_tickers(self) -> List[str]:
        """Get list of tickers that failed to fetch."""
        return list(self.failed_tickers)
    
    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.success_count = 0
        self.api_calls_made = 0
        self.failed_tickers.clear()
        self.current_backoff = 1.0


