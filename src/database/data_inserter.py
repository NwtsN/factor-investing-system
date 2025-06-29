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
import sqlite3
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports  
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils.logging import Logger
from config import DB_PATH


class DataInserter:
    """Handles insertion of fetched data into the database."""
    
    def __init__(self, logger: Logger, connection: sqlite3.Connection = None, db_path: str = None) -> None:
        """
        Initialize DataInserter with either an existing connection or a path to create a new one.
        
        Args:
            logger: Logger instance for logging
            connection: Existing SQLite connection (preferred)
            db_path: Path to database file (only used if connection is None)
        """
        self.logger = logger
        
        # Prefer existing connection over creating a new one
        if connection:
            self.conn: sqlite3.Connection = connection
            self.owns_connection: bool = False  # Don't close connection we don't own
            self.logger.log("DataInserter", "Using existing database connection", level="INFO")
        else:
            # Fallback to creating new connection
            self.db_path: str = db_path or DB_PATH
            self.conn: sqlite3.Connection = sqlite3.connect(self.db_path)
            self.owns_connection: bool = True  # We created it, we should close it
            self.logger.log("DataInserter", f"Created new database connection to {self.db_path}", level="INFO")
            
        self.cursor: sqlite3.Cursor = self.conn.cursor()
        
        # Validate connection is usable (but don't commit to avoid breaking transactions)
        try:
            self.cursor.execute("SELECT 1")
            self.cursor.fetchone()
        except sqlite3.Error as e:
            self.logger.log("DataInserter", f"Database connection validation failed: {e}", level="ERROR")
            raise RuntimeError(f"Database connection is not usable: {e}")
        
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit with cleanup."""
        self.close()
        
    def close(self) -> None:
        """Close database connection only if we created it."""
        if self.owns_connection and self.conn:
            self.conn.close()
            self.logger.log("DataInserter", "Database connection closed", level="INFO")
    
    def insert_staged_data(self, staged_data: Dict[str, Dict[str, Any]], use_transaction: bool = True) -> Dict[str, Any]:
        """
        Insert staged data from DataManager into the database.
        
        Args:
            staged_data: Dict with ticker as key and data dict as value
            use_transaction: If True, wrap all inserts in a single transaction
            
        Returns:
            Dict with insertion results
        """
        results = {
            'successful_inserts': [],
            'failed_inserts': [],
            'total_attempted': len(staged_data)
        }
        
        # Validate input data structure
        if not staged_data:
            self.logger.log("DataInserter", "No data to insert", level="WARNING")
            return results
        
        if use_transaction:
            # Start transaction for all-or-nothing insertion
            self.logger.log("DataInserter", "Starting transaction for batch insertion", level="INFO")
        
        try:
            for ticker, data in staged_data.items():
                try:
                    # Validate data structure
                    if not isinstance(data, dict):
                        raise ValueError(f"Invalid data structure for {ticker}: expected dict, got {type(data)}")
                    
                    if 'fundamentals' not in data or 'raw_data' not in data:
                        raise ValueError(f"Missing required fields for {ticker}: need 'fundamentals' and 'raw_data'")
                    
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
                    
                    # Only commit per-ticker if not using transaction mode
                    if not use_transaction:
                        self.conn.commit()
                        
                    results['successful_inserts'].append(ticker)
                    self.logger.log("DataInserter", f"{ticker}: Data inserted successfully", level="INFO")
                    
                except Exception as e:
                    if not use_transaction:
                        self.conn.rollback()
                    results['failed_inserts'].append({'ticker': ticker, 'error': str(e)})
                    self.logger.log("DataInserter", f"{ticker}: Insertion failed - {e}", level="ERROR")
                    
                    # In transaction mode, one failure should fail all
                    if use_transaction:
                        raise e
            
            # Commit all changes at once if using transaction
            if use_transaction:
                self.conn.commit()
                self.logger.log("DataInserter", 
                              f"Transaction committed successfully - {len(results['successful_inserts'])} tickers inserted", 
                              level="INFO")
        
        except Exception as transaction_error:
            # Rollback entire transaction on any failure
            if use_transaction:
                self.conn.rollback()
                self.logger.log("DataInserter", 
                              f"Transaction rolled back due to error: {transaction_error}", 
                              level="ERROR")
                # Reset results for transaction mode - it's all or nothing
                # Preserve the original error for the ticker that caused the failure
                error_msg = f"Transaction rolled back: {str(transaction_error)}"
                results['failed_inserts'] = [{'ticker': t, 'error': error_msg} for t in staged_data.keys()]
                results['successful_inserts'] = []
        
        return results
    
    def _get_or_create_stock_id(self, ticker: str) -> int:
        """Get stock_id for ticker, creating stock record if necessary."""
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
            return result[0]
        
        # Create new stock record
        try:
            self.cursor.execute(
                "INSERT INTO stocks (ticker, company_name) VALUES (?, ?)",
                (ticker, ticker)  # Using ticker as company name for now
            )
            stock_id = self.cursor.lastrowid
            self.logger.log("DataInserter", f"Created new stock record for {ticker} with ID {stock_id}", level="INFO")
            return stock_id
        except sqlite3.IntegrityError as e:
            # Handle race condition where another process created the record
            self.logger.log("DataInserter", f"Stock creation race condition for {ticker}, retrying: {e}", level="WARNING")
            self.cursor.execute("SELECT stock_id FROM stocks WHERE ticker = ?", (ticker,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            raise
    
    def _insert_extracted_fundamental_data(self, stock_id: int, fundamentals: dict, fetch_timestamp: Optional[datetime]) -> None:
        """Insert extracted fundamental data."""
        # Get the fiscal date from the fundamentals data
        fiscal_date_str = fundamentals.get('fiscal_date_ending')
        
        if fiscal_date_str:
            try:
                # Parse the fiscal date string (format: YYYY-MM-DD)
                fiscal_date = datetime.strptime(fiscal_date_str, '%Y-%m-%d').date()
            except ValueError:
                self.logger.log("DataInserter", 
                              f"Invalid fiscal date format: {fiscal_date_str}, using fetch timestamp", 
                              level="WARNING")
                fiscal_date = fetch_timestamp.date() if fetch_timestamp else datetime.now(timezone.utc).date()
        else:
            # Fallback to fetch timestamp if no fiscal date available
            self.logger.log("DataInserter", 
                          "No fiscal date in fundamentals, using fetch timestamp", 
                          level="WARNING")
            fiscal_date = fetch_timestamp.date() if fetch_timestamp else datetime.now(timezone.utc).date()
        
        # Insert or update extracted fundamental data
        # Note: Storing both specific metrics (TTM, quarterly, annual) and legacy columns for compatibility
        self.cursor.execute("""
            INSERT OR REPLACE INTO extracted_fundamental_data (
                stock_id, fiscalDateEnding, market_cap, 
                -- Balance sheet items
                total_debt, cash_equiv, total_assets, working_capital, longTermInvestments,
                -- TTM metrics
                ebitda_ttm, revenue_ttm, cash_flow_ops_ttm, interest_expense_ttm,
                -- Quarterly metrics
                cash_flow_ops_q, interest_expense_q, change_in_working_capital,
                -- Annual fallbacks
                ebitda_annual, total_debt_annual,
                -- Legacy columns (for backward compatibility)
                ebitda, cash_flow_ops, interest_expense,
                -- Other
                effective_tax_rate, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stock_id,
            fiscal_date,
            fundamentals.get('market_cap'),
            # Balance sheet items
            fundamentals.get('total_debt'),
            fundamentals.get('cash_equiv'),
            fundamentals.get('total_assets'),
            fundamentals.get('working_capital'),
            fundamentals.get('longTermInvestments'),
            # TTM metrics
            fundamentals.get('ebitda_ttm'),
            fundamentals.get('revenue_ttm'),
            fundamentals.get('cash_flow_ops_ttm'),
            fundamentals.get('interest_expense_ttm'),
            # Quarterly metrics
            fundamentals.get('cash_flow_ops_q'),
            fundamentals.get('interest_expense_q'),
            fundamentals.get('change_in_working_capital'),
            # Annual fallbacks
            fundamentals.get('ebitda_annual'),
            fundamentals.get('total_debt_annual'),
            # Legacy columns (populated with TTM or fallback values for compatibility)
            fundamentals.get('ebitda_ttm') or fundamentals.get('ebitda_annual'),
            fundamentals.get('cash_flow_ops_ttm') or fundamentals.get('cash_flow_ops_q'),
            fundamentals.get('interest_expense_ttm') or fundamentals.get('interest_expense_q'),
            # Other
            fundamentals.get('effective_tax_rate'),
            'AlphaVantage'
        ))
    
    def _insert_eps_data(self, stock_id: int, eps_list: List[Dict[str, Any]], earnings_data: dict) -> None:
        """Insert EPS data for last 5 quarters using the structured eps_list."""
        # Use the eps_list which already contains fiscalDateEnding and reportedEPS
        # This avoids re-extracting from raw data and ensures consistency
        
        # Validate eps_list is actually a list
        if not isinstance(eps_list, list):
            self.logger.log("DataInserter", 
                          f"Invalid eps_list type: expected list, got {type(eps_list)}", 
                          level="WARNING")
            return
        
        for eps_item in eps_list:
            fiscal_date = eps_item.get('fiscalDateEnding')
            eps_value = eps_item.get('eps_value')  # Use the pre-parsed float value
            
            if fiscal_date and not (isinstance(eps_value, float) and np.isnan(eps_value)):
                try:
                    self.cursor.execute("""
                        INSERT OR REPLACE INTO eps_last_5_qs (
                            stock_id, fiscalDateEnding, reportedEPS
                        ) VALUES (?, ?, ?)
                    """, (stock_id, fiscal_date, eps_value))
                except Exception as e:
                    self.logger.log("DataInserter", 
                                  f"Error inserting EPS for {fiscal_date}: {e}", 
                                  level="WARNING")
    
    def _insert_raw_api_responses(self, stock_id: int, raw_data: dict, fetch_timestamp: Optional[datetime]) -> None:
        """Insert raw API responses for each endpoint."""
        fetch_date = fetch_timestamp.date() if fetch_timestamp else datetime.now(timezone.utc).date()
        
        # Get ticker from fundamentals (passed in the calling method)
        # For now, we'll need to get it from the stock_id
        self.cursor.execute("SELECT ticker FROM stocks WHERE stock_id = ?", (stock_id,))
        ticker_result = self.cursor.fetchone()
        ticker = ticker_result[0] if ticker_result else "UNKNOWN"
        
        # Since we only reach this point with complete data (all 4 endpoints),
        # we can safely mark all rows as complete as by this point we have all 4 endpoints
        for endpoint_key, response_data in raw_data.items():
            try:
                # Serialize JSON data with error handling
                json_data = json.dumps(response_data)
            except (TypeError, ValueError) as e:
                self.logger.log("DataInserter", 
                              f"Failed to serialize {endpoint_key} data: {e}", 
                              level="ERROR")
                # Store error message instead of failing completely
                json_data = json.dumps({"error": f"Serialization failed: {str(e)}"})
            
            self.cursor.execute("""
                INSERT OR REPLACE INTO raw_api_responses (
                    stock_id, ticker, date_fetched, endpoint_key, response, http_status_code, is_complete_session
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                stock_id,
                ticker,
                fetch_date,
                endpoint_key,
                json_data,
                200,  # Assuming successful responses
                1  # Always complete since DataFetcher is all-or-nothing (1 = True in SQLite)
            )) 