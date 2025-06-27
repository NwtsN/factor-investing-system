#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Data insertion into database tables.

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
import json
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add parent directory to path for imports  
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils.logging import Logger
from config import DB_PATH


class DataInserter:
    """Handles insertion of fetched data into the database."""
    
    def __init__(self, logger: Logger, db_path: str = None) -> None:
        self.logger = logger
        self.session_id: str = str(uuid.uuid4())
        self.db_path: str = db_path or DB_PATH
        self.conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        self.cursor: sqlite3.Cursor = self.conn.cursor()
        
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit with cleanup."""
        self.close()
        
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.logger.log("DataInserter", "Database connection closed", level="INFO")
    
    def insert_staged_data(self, staged_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert staged data from DataManager into the database.
        
        Args:
            staged_data: Dict with ticker as key and data dict as value
            
        Returns:
            Dict with insertion results
        """
        results = {
            'successful_inserts': [],
            'failed_inserts': [],
            'total_attempted': len(staged_data)
        }
        
        for ticker, data in staged_data.items():
            try:
                # Get or create stock_id
                stock_id = self._get_or_create_stock_id(ticker)
                
                # Insert fundamental data
                fundamentals = data['fundamentals']
                raw_api_data = data['raw_data']
                
                # Insert extracted fundamental data
                self._insert_extracted_fundamental_data(stock_id, fundamentals, data.get('fetch_timestamp'))
                
                # Insert EPS data
                self._insert_eps_data(stock_id, fundamentals.get('eps_last_5_qs', []), raw_api_data.get('Earnings', {}))
                
                # Insert raw API responses
                self._insert_raw_api_responses(stock_id, raw_api_data, data.get('fetch_timestamp'))
                
                self.conn.commit()
                results['successful_inserts'].append(ticker)
                self.logger.log("DataInserter", f"{ticker}: Data inserted successfully", level="INFO")
                
            except Exception as e:
                self.conn.rollback()
                results['failed_inserts'].append({'ticker': ticker, 'error': str(e)})
                self.logger.log("DataInserter", f"{ticker}: Insertion failed - {e}", level="ERROR")
        
        return results
    
    def _get_or_create_stock_id(self, ticker: str) -> int:
        """Get stock_id for ticker, creating stock record if necessary."""
        # Check if stock exists
        self.cursor.execute("SELECT stock_id FROM stocks WHERE ticker = ?", (ticker,))
        result = self.cursor.fetchone()
        
        if result:
            return result[0]
        
        # Create new stock record
        self.cursor.execute(
            "INSERT INTO stocks (ticker, company_name) VALUES (?, ?)",
            (ticker, ticker)  # Using ticker as company name for now
        )
        return self.cursor.lastrowid
    
    def _insert_extracted_fundamental_data(self, stock_id: int, fundamentals: dict, fetch_timestamp: datetime) -> None:
        """Insert extracted fundamental data."""
        # For Alpha Vantage, the fiscal date should come from the most recent quarterly report
        # This is a placeholder - in a real implementation, you'd pass the actual fiscal date
        # from the API response (e.g., from balance sheet quarterly reports)
        
        # Note: The actual fiscal date should be extracted from the raw_data in the calling method
        # For now, using fetch timestamp as a fallback
        fiscal_date = fetch_timestamp.date() if fetch_timestamp else datetime.now(timezone.utc).date()
        
        # Insert or update extracted fundamental data
        self.cursor.execute("""
            INSERT OR REPLACE INTO extracted_fundamental_data (
                stock_id, fiscalDateEnding, market_cap, total_debt, cash_equiv, 
                ebitda, cash_flow_ops, change_in_working_capital, interest_expense,
                total_assets, working_capital, effective_tax_rate, longTermInvestments, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stock_id,
            fiscal_date,
            fundamentals.get('market_cap'),
            fundamentals.get('total_debt'),
            fundamentals.get('cash_equiv'),
            fundamentals.get('ebitda'),
            fundamentals.get('cash_flow_ops'),
            fundamentals.get('change_in_working_capital'),
            fundamentals.get('interest_expense'),
            fundamentals.get('total_assets'),
            fundamentals.get('working_capital'),
            fundamentals.get('effective_tax_rate'),
            fundamentals.get('longTermInvestments'),
            'AlphaVantage'
        ))
    
    def _insert_eps_data(self, stock_id: int, eps_list: List[float], earnings_data: dict) -> None:
        """Insert EPS data for last 5 quarters."""
        quarterly_earnings = earnings_data.get('quarterlyEarnings', [])[:5]
        
        for i, earnings_q in enumerate(quarterly_earnings):
            fiscal_date = earnings_q.get('fiscalDateEnding')
            reported_eps = earnings_q.get('reportedEPS')
            
            if fiscal_date and reported_eps is not None:
                try:
                    eps_value = float(reported_eps)
                    self.cursor.execute("""
                        INSERT OR REPLACE INTO eps_last_5_qs (
                            stock_id, fiscalDateEnding, reportedEPS
                        ) VALUES (?, ?, ?)
                    """, (stock_id, fiscal_date, eps_value))
                except ValueError:
                    self.logger.log("DataInserter", 
                                  f"Invalid EPS value for {fiscal_date}: {reported_eps}", 
                                  level="WARNING")
    
    def _insert_raw_api_responses(self, stock_id: int, raw_data: dict, fetch_timestamp: datetime) -> None:
        """Insert raw API responses for each endpoint."""
        fetch_date = fetch_timestamp.date() if fetch_timestamp else datetime.now(timezone.utc).date()
        
        # Get ticker from fundamentals (passed in the calling method)
        # For now, we'll need to get it from the stock_id
        self.cursor.execute("SELECT ticker FROM stocks WHERE stock_id = ?", (stock_id,))
        ticker_result = self.cursor.fetchone()
        ticker = ticker_result[0] if ticker_result else "UNKNOWN"
        
        for endpoint_key, response_data in raw_data.items():
            self.cursor.execute("""
                INSERT OR REPLACE INTO raw_api_responses (
                    stock_id, ticker, date_fetched, endpoint_key, response, http_status_code
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                stock_id,
                ticker,
                fetch_date,
                endpoint_key,
                json.dumps(response_data),
                200  # Assuming successful responses
            )) 