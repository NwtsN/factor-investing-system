import os
import sys
import time
import json
import uuid
import sqlite3
import requests
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Union

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
    def __init__(self, logger: 'Logger') -> None:
        self.logger = logger
        self.failed_tickers: list[str] = []

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
            json_data = self._fetch_with_retry(ticker, label, url)
            if json_data is None:
                self.failed_tickers.append(ticker)
                return False, {}, {}
            raw_data[label] = json_data

        # Step 2: Parse relevant fields
        try:
            fundamentals = self._extract_fundamentals(ticker, raw_data)
            self.logger.log("Fundamentals", f"{ticker}: extracted {len(fundamentals)} fields", level="INFO")
            return True, fundamentals, raw_data
        except Exception as e:
            self.logger.log("Fundamentals", f"{ticker}: parsing error - {e}", level="ERROR")
            self.failed_tickers.append(ticker)
            return False, {}, {}

    def _fetch_with_retry(self, ticker: str, label: str, url: str) -> Optional[dict]:
        for attempt in range(2):
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    json_data = response.json()
                    # Very basic structure check
                    if "annualReports" in json_data or "quarterlyReports" in json_data:
                        preview = str(json_data)[:60]
                        self.logger.log(f"API:{label}", f"{ticker} - Success on attempt {attempt+1}. Preview: {preview}", level="INFO")
                        return json_data
                    else:
                        raise ValueError("Unexpected JSON structure.")
                elif response.status_code == 429:
                    self.logger.log(f"API:{label}", f"{ticker} - Rate limit hit, sleeping 60s", level="WARNING")
                    time.sleep(60)
                else:
                    raise Exception(f"Status code {response.status_code}")
            except Exception as e:
                self.logger.log(f"API:{label}", f"{ticker} - Attempt {attempt+1} failed: {e}", level="WARNING")
                time.sleep(5)
        return None



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

        if not (income_q and income_a and balance_q and balance_a and cash_q and cash_a and earnings_last5_qs):
            raise ValueError("Missing one or more report sets.")

        def safe_get(report, field):
            try:
                return float(report.get(field, np.nan))
            except Exception:
                return np.nan
            
        def extract_eps_list(earnings_list, count=5):
            """
            Extracts the most recent 'count' diluted EPS values from Alpha Vantage's EARNINGS endpoint.
            Returns a list of floats (or np.nan if parsing fails).
            """
            eps_values = []
            for i in range(count):
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


