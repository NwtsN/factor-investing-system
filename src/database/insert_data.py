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

class DataInserter:
    def __init__(self) -> None:
        self.session_id: str = str(uuid.uuid4())
        self.db_path: str = DB_PATH
        self.conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        self.cursor: sqlite3.Cursor = self.conn.cursor()


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

    def fetch_fundamentals(self, ticker: str, api_key: str) -> tuple[bool, dict, dict]:
        """
        Fetches and parses fundamental data for a given ticker.
        Returns a tuple: (success, cleaned_fundamentals_dict, raw_api_data)
        """

        # Define endpoints
        endpoints = {
            "INCOME_STATEMENT": f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker}&apikey={api_key}",
            "BALANCE_SHEET": f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker}&apikey={api_key}",
            "CASH_FLOW": f"https://www.alphavantage.co/query?function=CASH_FLOW&symbol={ticker}&apikey={api_key}",
            "Earnings": f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker}&apikey={api_key}",
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
            self.logger.log("Fundamentals", f"{ticker}: parsing error - {e}", level="ERROR")
            self.failed_tickers.append(ticker)
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


        fundamentals = {
            "ticker": ticker,
            "market_cap": np.nan,  # to be filled via price fetcher
            "total_debt": safe_get(balance_a[0], "totalLiabilities"),
            "cash_equiv": safe_get(balance_a[0], "cashAndCashEquivalentsAtCarryingValue"),
            "ebitda": safe_get(income_a[0], "ebitda"),
            "eps_last_5_qs": extract_eps_list(earnings_last5_qs),
            "cash_flow_ops": safe_get(cash_q[0], "operatingCashflow"),
            "change_in_working_capital": safe_get(cash_q[0], "changeInWorkingCapital"),
            "interest_expense": safe_get(income_q[0], "interestExpense"),
            "total_assets": safe_get(balance_q[0], "totalAssets"),
            "working_capital": safe_get(balance_q[0], "totalCurrentAssets") - safe_get(balance_q[0], "totalCurrentLiabilities"),
            "gross_assets": safe_get(balance_q[0], "totalAssets")  # proxy for now
        }

        return fundamentals

class DataManager:
    """this class should be able to query raw_api_responses for each ticker's last timestamp, 
    Compare that to the expected next report date (e.g., quarterly earnings calendar), 
    Flag stale or outdated tickers"""
    def __init__(self) -> None:
        self.session_id: str = str(uuid.uuid4())


