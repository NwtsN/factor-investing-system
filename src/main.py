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
import argparse
import contextlib
from datetime import datetime
from typing import Optional

# Add src directory to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))

from database.database_setup import DatabaseManager
from database.fetch_data import DataFetcher
from database.database_handler import DataManager
from database.data_inserter import DataInserter
from utils.program_timer import Timeout
from config import CONFIG_FILE_PATH

# Optional: Load tickers from file or hardcode a few for testing
TICKERS = ["AAPL", "MSFT", "GOOGL", "TSLA"]  # You can swap in your full S&P 500 list later

def load_config() -> dict:
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load config file at {CONFIG_FILE_PATH}: {e}")
        sys.exit(1)

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Investment Analysis System - Fetch and analyze financial data",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=None,
        help="Maximum runtime in minutes before program stops (default: no timeout)"
    )
    
    parser.add_argument(
        "--transaction-mode",
        choices=["all-or-nothing", "individual"],
        default="individual",
        help="Database insertion mode: all-or-nothing (single transaction) or individual commits (default: individual)"
    )
    
    args = parser.parse_args()
    
    # Validate timeout argument
    if args.timeout is not None and args.timeout <= 0:
        parser.error("Timeout must be a positive number of minutes")
    
    return args

def check_timeout_safety(start_time: datetime, timeout_minutes: Optional[int], 
                        operation_name: str, estimated_minutes: float = 2.0) -> bool:
    """
    Check if there's enough time remaining before timeout to safely perform an operation.
    
    Args:
        start_time: When the program started
        timeout_minutes: Total timeout in minutes (None if no timeout)
        operation_name: Name of the operation to perform
        estimated_minutes: Estimated time in minutes for the operation
        
    Returns:
        True if safe to proceed, False if too close to timeout
    """
    if timeout_minutes is None:
        return True  # No timeout set
    
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    remaining = timeout_minutes - elapsed
    
    if remaining < estimated_minutes:
        print(f"\n[WARNING] Not enough time for {operation_name}")
        print(f"  Timeout in: {remaining:.1f} minutes")
        print(f"  Operation needs: {estimated_minutes:.1f} minutes")
        return False
    
    return True

def main(args: argparse.Namespace) -> None:
    """
    Intelligent data fetching with DataManager integration.
    Automatically checks database and skips tickers with recent data.
    
    Args:
        args: Parsed command line arguments
    """
    start_time = datetime.now()
    timeout_minutes = args.timeout
    
    # Determine transaction mode
    use_transaction = args.transaction_mode == "all-or-nothing"
    
    config = load_config()
    api_key = config.get("api_keys", {}).get("alpha_vantage")

    if not api_key or api_key.strip() == "" or api_key == "demo":
        print("[ERROR] Valid API key not found in config (found: '{}').".format(api_key if api_key else "None"))
        sys.exit(1)

    session_id = str(uuid.uuid4())
    print(f"[INFO] Starting intelligent data fetch session {session_id}")
    print(f"[INFO] Transaction mode: {args.transaction_mode}")

    # Use timeout context manager if timeout is specified
    timeout_context = Timeout(timeout_minutes) if timeout_minutes else None
    
    with (timeout_context if timeout_context else contextlib.nullcontext()):
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
                print(f"\n[INFO] Fetch Results:")
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
            
            # Step 3: Process staged data for database insertion
            staged_data = data_manager.get_staged_data()
            print(f"\n[INFO] {len(staged_data)} tickers staged for database insertion")
            
            if staged_data:
                # Check if we have enough time for database operations
                # Ensure minimum estimate of 0.1 minutes to avoid edge cases
                estimated_db_time = max(0.1, len(staged_data) * 0.5)  # Estimate 0.5 minutes per ticker
                if not check_timeout_safety(start_time, timeout_minutes, "database insertion", estimated_db_time):
                    logger.log("Main", "Skipping database insertion due to timeout risk", level="WARNING")
                    print("\n[WARNING] Staged data will remain in cache for next run")
                    # Still show cache status before returning
                    cache_status = data_manager.get_staging_cache_status()
                    print(f"\n[INFO] Staging cache status:")
                    print(f"  Entries preserved: {cache_status['size']}")
                    print(f"  Oldest entry age: {cache_status['oldest_entry_age_hours']:.1f} hours")
                    return
                
                # Log what we're about to insert
                for ticker in staged_data:
                    ticker_data = staged_data[ticker]
                    logger.log("Main", 
                              f"{ticker}: Ready to insert with {len(ticker_data['fundamentals'])} fields", 
                              level="INFO")
                
                # Step 4: Insert data into database using DataInserter with existing connection
                print(f"\n[INFO] Starting database insertion...")
                with DataInserter(logger, connection=db.conn) as inserter:
                    # Insert all staged data
                    insert_results = inserter.insert_staged_data(staged_data, use_transaction=use_transaction)
                    
                    # Report insertion results
                    print(f"\n[INFO] Database Insertion Results:")
                    print(f"  Successful inserts: {len(insert_results['successful_inserts'])}")
                    print(f"  Failed inserts: {len(insert_results['failed_inserts'])}")
                    
                    # Log successful insertions
                    if insert_results['successful_inserts']:
                        logger.log("Main", 
                                  f"Successfully inserted: {insert_results['successful_inserts']}", 
                                  level="INFO")
                        print(f"  Tickers inserted: {', '.join(insert_results['successful_inserts'])}")
                    
                    # Log and display failed insertions
                    if insert_results['failed_inserts']:
                        logger.log("Main", 
                                  f"Failed insertions: {insert_results['failed_inserts']}", 
                                  level="ERROR")
                        print("\n[ERROR] Failed insertions:")
                        for failure in insert_results['failed_inserts']:
                            print(f"  - {failure['ticker']}: {failure['error']}")
                    
                    # Clear staging cache for successfully inserted tickers
                    for ticker in insert_results['successful_inserts']:
                        data_manager.clear_staged_data(ticker)
                        logger.log("Main", 
                                  f"{ticker}: Cleared from staging cache after successful insertion", 
                                  level="INFO")
                
                # Final summary
                total_success = len(insert_results['successful_inserts'])
                total_failed = len(insert_results['failed_inserts'])
                
                logger.log("Main", 
                          f"Session complete: {total_success} tickers inserted, {total_failed} failed", 
                          level="INFO")
                print(f"\n[INFO] Session complete: {total_success} tickers successfully processed end-to-end")
                
            else:
                print("\n[INFO] No new data to insert - all tickers have recent data")
                logger.log("Main", "Session complete: No new data fetched (all tickers current)", level="INFO")
            
            # Display cache status at the end
            cache_status = data_manager.get_staging_cache_status()
            print(f"\n[INFO] Final staging cache status:")
            print(f"  Remaining entries: {cache_status['size']}")
            if cache_status['size'] > 0:
                print(f"  Oldest entry age: {cache_status['oldest_entry_age_hours']:.1f} hours")
                print(f"  (These entries failed insertion and remain in cache)")

if __name__ == "__main__":
    args = parse_arguments()
    main(args)

