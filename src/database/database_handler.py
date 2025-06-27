#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Data Manager - Handles data freshness, querying, and determines which tickers need updating.

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
import uuid
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports  
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils.logging import Logger


class DataManager:
    """
    Manages data freshness, querying, and determines which tickers need updating.
    
    Responsibilities:
    - Query database for last fetch timestamps
    - Determine which tickers need fresh data based on earnings calendar
    - Manage data staging before database insertion
    - Track data lineage and update history
    """
    
    def __init__(self, db_connection: sqlite3.Connection, logger: Logger) -> None:
        self.conn = db_connection
        self.cursor = db_connection.cursor()
        self.logger = logger
        self.session_id = str(uuid.uuid4())
        
        # Staging area for fetched data before database insertion
        self.staging_cache: Dict[str, Dict[str, Any]] = {}
        
        # Configuration for data freshness
        self.min_refresh_days = 90  # Minimum days between fetches (quarterly reports)
        self.force_refresh_days = 365  # Force refresh after this many days regardless
        self.staging_cache_expiry_hours = 24  # Expire staged data after 24 hours
        
        # Cleanup management
        self.last_cleanup_time = datetime.now(timezone.utc)
        self.cleanup_interval_minutes = 5  # Run cleanup every 5 minutes
        
        # Clear any expired staging data on initialization
        self._clear_expired_staging_data()
        
    def _validate_connection(self) -> bool:
        """Validate database connection is still alive."""
        try:
            self.conn.execute("SELECT 1")
            return True
        except sqlite3.Error as e:
            self.logger.log("DataManager", 
                          f"Database connection error: {e}", 
                          level="ERROR")
            return False
    
    def _should_run_cleanup(self) -> bool:
        """Check if it's time to run expired data cleanup."""
        current_time = datetime.now(timezone.utc)
        time_since_cleanup = current_time - self.last_cleanup_time
        return time_since_cleanup >= timedelta(minutes=self.cleanup_interval_minutes)
    
    def _clear_expired_staging_data(self) -> None:
        """Clear staging cache entries older than expiry threshold."""
        if not self.staging_cache:
            # Don't update cleanup time if cache is empty
            return
            
        current_time = datetime.now(timezone.utc)
        
        # Remove expired entries
        expired_tickers = [
            ticker for ticker, data in self.staging_cache.items()
            if 'fetch_timestamp' in data and 
            (current_time - data['fetch_timestamp']) > timedelta(hours=self.staging_cache_expiry_hours)
        ]
        
        for ticker in expired_tickers:
            del self.staging_cache[ticker]
        
        # Always update cleanup time when we checked
        self.last_cleanup_time = current_time
        
        # Only log what remains if we cleaned something
        if expired_tickers:
            remaining_count = len(self.staging_cache)
            self.logger.log("DataManager", 
                          f"Cleanup complete: {remaining_count} entries remaining in staging cache", 
                          level="INFO")
    
    def force_cleanup_staging_data(self) -> int:
        """Force immediate cleanup of expired staging data, regardless of time interval.
        
        Returns:
            int: Number of expired entries that were removed
        """
        if not self.staging_cache:
            return 0
            
        current_time = datetime.now(timezone.utc)
        
        # Remove expired entries
        expired_tickers = [
            ticker for ticker, data in self.staging_cache.items()
            if 'fetch_timestamp' in data and 
            (current_time - data['fetch_timestamp']) > timedelta(hours=self.staging_cache_expiry_hours)
        ]
        
        for ticker in expired_tickers:
            del self.staging_cache[ticker]
        
        self.last_cleanup_time = current_time
        
        # Log what remains if we cleaned something
        if expired_tickers:
            remaining_count = len(self.staging_cache)
            self.logger.log("DataManager", 
                          f"Force cleanup complete: {remaining_count} entries remaining in staging cache", 
                          level="INFO")
        
        return len(expired_tickers)
    
    def get_staging_cache_status(self) -> Dict[str, Any]:
        """Get staging cache status without triggering cleanup.
        
        Returns:
            dict: Cache status including size, oldest entry age, etc.
        """
        if not self.staging_cache:
            return {
                'size': 0,
                'oldest_entry_age_hours': 0,
                'next_cleanup_in_minutes': max(0, self.cleanup_interval_minutes - 
                    (datetime.now(timezone.utc) - self.last_cleanup_time).total_seconds() / 60)
            }
        
        current_time = datetime.now(timezone.utc)
        oldest_age_hours = 0
        
        for data in self.staging_cache.values():
            if 'fetch_timestamp' in data:
                age_hours = (current_time - data['fetch_timestamp']).total_seconds() / 3600
                oldest_age_hours = max(oldest_age_hours, age_hours)
        
        time_since_cleanup = (current_time - self.last_cleanup_time).total_seconds() / 60
        next_cleanup_minutes = max(0, self.cleanup_interval_minutes - time_since_cleanup)
        
        return {
            'size': len(self.staging_cache),
            'oldest_entry_age_hours': round(oldest_age_hours, 2),
            'next_cleanup_in_minutes': round(next_cleanup_minutes, 1)
        }
    
    def get_tickers_needing_update(self, ticker_list: List[str]) -> tuple[List[str], List[str]]:
        """
        Analyze which tickers need fresh data vs which are up to date.
        
        Returns:
            tuple: (tickers_to_fetch, tickers_skipped)
        """
        if not self._validate_connection():
            self.logger.log("DataManager", 
                          "Database connection lost, attempting to reconnect", 
                          level="WARNING")
            # In production, implement reconnection logic here
            return ticker_list, []  # Fetch all if DB is down
        
        tickers_to_fetch = []
        tickers_skipped = []
        
        for ticker in ticker_list:
            last_fetch_info = self._get_last_fetch_info(ticker)
            
            if self._should_fetch_ticker(ticker, last_fetch_info):
                tickers_to_fetch.append(ticker)
                self.logger.log("DataManager", 
                              f"{ticker}: Needs update - {self._get_fetch_reason(ticker, last_fetch_info)}", 
                              level="INFO")
            else:
                tickers_skipped.append(ticker)
                reason = self._get_skip_reason(ticker, last_fetch_info)
                self.logger.log("DataManager", 
                              f"{ticker}: Skipping - {reason}", 
                              level="INFO")
        
        self.logger.log("DataManager", 
                       f"Analysis complete: {len(tickers_to_fetch)} to fetch, {len(tickers_skipped)} to skip", 
                       level="INFO")
        
        return tickers_to_fetch, tickers_skipped
    
    def _get_last_fetch_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get the last complete fetch information for a ticker"""
        try:
            # Query for dates where all 4 endpoints exist - ensures completeness
            query = """
            WITH complete_fetches AS (
                SELECT date_fetched
                FROM raw_api_responses 
                WHERE ticker = ? 
                    AND http_status_code = 200
                    AND endpoint_key IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW', 'Earnings')
                GROUP BY date_fetched
                HAVING COUNT(DISTINCT endpoint_key) = 4
            )
            SELECT MAX(date_fetched) as last_complete_fetch_date
            FROM complete_fetches
            """
            
            self.cursor.execute(query, (ticker,))
            result = self.cursor.fetchone()
            
            if result and result[0]:  # Check if we have a result and a valid date
                try:
                    # Since date_fetched is DATE type, it's always YYYY-MM-DD format
                    date_str = result[0]
                    last_fetch_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                        
                    return {
                        'ticker': ticker,
                        'last_fetch_date': last_fetch_date
                    }
                except ValueError as e:
                    self.logger.log("DataManager", 
                                  f"Unexpected date format for {ticker}: {date_str} - {e}", 
                                  level="ERROR")
                    return None
            else:
                return None
                
        except Exception as e:
            self.logger.log("DataManager", 
                          f"Error querying last fetch info for {ticker}: {e}", 
                          level="ERROR")
            return None
    
    def _should_fetch_ticker(self, ticker: str, last_fetch_info: Optional[Dict[str, Any]]) -> bool:
        """Determine if a ticker should be fetched based on last fetch date and business rules."""
        
        # Never fetched before - definitely fetch
        if not last_fetch_info or not last_fetch_info.get('last_fetch_date'):
            return True
        
        last_fetch_date = last_fetch_info['last_fetch_date']
        current_time = datetime.now(timezone.utc)
        days_since_fetch = (current_time - last_fetch_date).days
        
        # Force refresh if data is very old
        if days_since_fetch >= self.force_refresh_days:
            return True
        
        # Skip if recently fetched (less than minimum refresh period)
        if days_since_fetch < self.min_refresh_days:
            return False
        
        # For quarterly reports, check if we're in a new quarter
        # This is a simplified approach - in production you'd check actual earnings calendar
        current_quarter = self._get_current_quarter()
        last_fetch_quarter = self._get_quarter_from_date(last_fetch_date)
        
        if current_quarter != last_fetch_quarter:
            return True
        
        return False
    
    def _get_fetch_reason(self, ticker: str, last_fetch_info: Optional[Dict[str, Any]]) -> str:
        """Get human-readable reason why ticker needs fetching."""
        if not last_fetch_info:
            return "Never fetched before"
        
        last_fetch_date = last_fetch_info.get('last_fetch_date')
        if not last_fetch_date:
            return "No valid last fetch date"
        
        current_time = datetime.now(timezone.utc)
        days_since = (current_time - last_fetch_date).days
        
        if days_since >= self.force_refresh_days:
            return f"Data is {days_since} days old (force refresh)"
        
        current_quarter = self._get_current_quarter()
        last_quarter = self._get_quarter_from_date(last_fetch_date)
        
        if current_quarter != last_quarter:
            return f"New quarter: {last_quarter} -> {current_quarter}"
        
        return f"Regular refresh ({days_since} days since last fetch)"
    
    def _get_skip_reason(self, ticker: str, last_fetch_info: Optional[Dict[str, Any]]) -> str:
        """Get human-readable reason why ticker is being skipped."""
        if not last_fetch_info or not last_fetch_info.get('last_fetch_date'):
            return "No fetch info available"  # Shouldn't happen if skipping
        
        last_fetch_date = last_fetch_info['last_fetch_date']
        current_time = datetime.now(timezone.utc)
        days_since = (current_time - last_fetch_date).days
        
        if days_since < self.min_refresh_days:
            return f"Recently fetched ({days_since} days ago, minimum is {self.min_refresh_days})"
        
        return f"Data is current ({days_since} days old)"
    
    def _get_current_quarter(self) -> str:
        """Get current quarter in YYYY-Q format."""
        now = datetime.now(timezone.utc)
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{quarter}"
    
    def _get_quarter_from_date(self, date: datetime) -> str:
        """Get quarter from a given date in YYYY-Q format."""
        quarter = (date.month - 1) // 3 + 1
        return f"{date.year}-Q{quarter}"
    
    def stage_data(self, ticker: str, fundamentals: dict, raw_data: dict) -> None:
        """Stage fetched data before database insertion."""
        self.staging_cache[ticker] = {
            'fundamentals': fundamentals,
            'raw_data': raw_data,
            'fetch_timestamp': datetime.now(timezone.utc),
            'session_id': self.session_id
        }
        
        self.logger.log("DataManager", 
                       f"{ticker}: Data staged for insertion", 
                       level="INFO")
        
        # Clean expired entries if enough time has passed
        if self._should_run_cleanup():
            self._clear_expired_staging_data()
    
    def get_staged_data(self) -> Dict[str, Dict[str, Any]]:
        """Get all staged data ready for database insertion."""
        # Only clean if enough time has passed, like in stage_data
        if self._should_run_cleanup():
            self._clear_expired_staging_data()
        return self.staging_cache.copy()
    
    def clear_staged_data(self, ticker: str = None) -> None:
        """Clear staged data after successful database insertion."""
        if ticker:
            if ticker in self.staging_cache:
                del self.staging_cache[ticker]
                self.logger.log("DataManager", 
                              f"{ticker}: Staged data cleared after insertion", 
                              level="INFO")
        else:
            # Clear all staged data
            cleared_count = len(self.staging_cache)
            self.staging_cache.clear()
            self.logger.log("DataManager", 
                          f"All staged data cleared ({cleared_count} tickers)", 
                          level="INFO")
    
    def get_data_freshness_report(self, ticker_list: List[str]) -> Dict[str, Any]:
        """Generate a comprehensive report on data freshness for given tickers."""
        if not self._validate_connection():
            return {
                'error': 'Database connection lost',
                'total_tickers': len(ticker_list)
            }
            
        report = {
            'total_tickers': len(ticker_list),
            'never_fetched': [],
            'fresh_data': [],
            'stale_data': [],
            'very_old_data': [],
            'summary': {}
        }
        
        current_time = datetime.now(timezone.utc)
        
        for ticker in ticker_list:
            last_fetch_info = self._get_last_fetch_info(ticker)
            
            if not last_fetch_info or not last_fetch_info.get('last_fetch_date'):
                report['never_fetched'].append(ticker)
            else:
                days_since = (current_time - last_fetch_info['last_fetch_date']).days
                
                if days_since < 30:
                    report['fresh_data'].append({'ticker': ticker, 'days_old': days_since})
                elif days_since < 180:
                    report['stale_data'].append({'ticker': ticker, 'days_old': days_since})
                else:
                    report['very_old_data'].append({'ticker': ticker, 'days_old': days_since})
        
        report['summary'] = {
            'never_fetched_count': len(report['never_fetched']),
            'fresh_count': len(report['fresh_data']),
            'stale_count': len(report['stale_data']),
            'very_old_count': len(report['very_old_data'])
        }
        
        return report
    
    def set_refresh_policy(self, min_days: int = 90, force_days: int = 365) -> None:
        """Configure the data refresh policy."""
        self.min_refresh_days = min_days
        self.force_refresh_days = force_days
        
        self.logger.log("DataManager", 
                       f"Refresh policy updated: min={min_days} days, force={force_days} days", 
                       level="INFO") 