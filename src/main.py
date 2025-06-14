#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Main entry point for the investment analysis system.

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
import yaml
import uuid

# Add src directory to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))

from database.database_setup import DatabaseManager
from database.fetch_data import DataFetcher, DataManager
from config import CONFIG_FILE_PATH

# Optional: Load tickers from file or hardcode a few for testing
TICKERS = ["AAPL", "MSFT", "GOOGL", "TSLA"]  # You can swap in your full S&P 500 list later

def load_config() -> dict:
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load config file at {CONFIG_FILE_PATH}: {e}")
        exit(1)

def main() -> None:
    """
    Intelligent data fetching with DataManager integration.
    Automatically checks database and skips tickers with recent data.
    """
    config = load_config()
    api_key = config.get("api_keys", {}).get("alpha_vantage")

    if not api_key:
        print("[ERROR] API key not found in config.")
        exit(1)

    session_id = str(uuid.uuid4())
    print(f"[INFO] Starting intelligent data fetch session {session_id}")

    with DatabaseManager() as db:
        logger = db.get_logger(session_id)
        data_manager = DataManager(db.conn, logger)
        
        # Step 1: Analyze data freshness
        print("[INFO] Analyzing data freshness...")
        freshness_report = data_manager.get_data_freshness_report(TICKERS)
        
        logger.log("Main", f"Data freshness analysis: {freshness_report['summary']}", level="INFO")
        print(f"  Total tickers: {freshness_report['total_tickers']}")
        print(f"  Never fetched: {freshness_report['summary']['never_fetched_count']}")
        print(f"  Fresh data (< 30 days): {freshness_report['summary']['fresh_count']}")
        print(f"  Stale data (30-180 days): {freshness_report['summary']['stale_count']}")
        print(f"  Very old data (> 180 days): {freshness_report['summary']['very_old_count']}")
        
        # Step 2: Smart fetching with DataManager
        with DataFetcher(logger, data_manager, api_key) as fetcher:
            print("[INFO] Starting intelligent fetch process...")
            
            # This automatically skips tickers with recent data!
            results = fetcher.fetch_multiple_tickers(TICKERS)
            
            # Report results
            print(f"[INFO] Fetch Results:")
            print(f"  Total requested: {results['total_requested']}")
            print(f"  Actually fetched: {results['total_fetched']}")
            print(f"  Skipped (recent data): {results['total_skipped']}")
            print(f"  Failed: {len(results['failed_fetches'])}")
            print(f"  API calls made: {results['api_calls_made']}")
            
            api_calls_saved = results['total_skipped'] * 4  # 4 endpoints per ticker
            print(f"  API calls saved: {api_calls_saved}")
            
            # Log detailed results
            if results['successful_fetches']:
                logger.log("Main", f"Successfully fetched: {results['successful_fetches']}", level="INFO")
            
            if results['skipped_tickers']:
                logger.log("Main", f"Skipped tickers (recent data): {results['skipped_tickers']}", level="INFO")
            
            if results['failed_fetches']:
                logger.log("Main", f"Failed tickers: {results['failed_fetches']}", level="WARNING")
        
        # Step 3: Get staged data for database insertion
        staged_data = data_manager.get_staged_data()
        print(f"[INFO] {len(staged_data)} tickers staged for database insertion")
        
        if staged_data:
            for ticker in staged_data:
                ticker_data = staged_data[ticker]
                logger.log("Main", 
                          f"{ticker}: Staged with {len(ticker_data['fundamentals'])} fields", 
                          level="INFO")
            
            logger.log("Main", f"Session complete: {len(staged_data)} tickers ready for database insertion", level="INFO")
        else:
            print("[INFO] No new data to insert - all tickers have recent data")
            logger.log("Main", "Session complete: No new data fetched (all tickers current)", level="INFO")
        
        # TODO: Later implement DataInserter to process staged_data
        # After successful insertion, clear staging cache:
        # data_manager.clear_staged_data()

if __name__ == "__main__":
    main()

